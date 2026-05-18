import fdb
import requests
import json
import time
import os
from datetime import datetime, date

# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================
FB_DLL_PATH = r"C:\Program Files (x86)\Firebird\Firebird_5_0\fbclient.dll"
API_BASE_URL = "http://localhost:3000/api"
API_TOKEN = "test-token-123"
CONFIG_FILE = "companies.json"

# Carrega a DLL do Firebird
try:
    fdb.load_api(FB_DLL_PATH)
except Exception as e:
    print(f"Erro ao carregar DLL do Firebird: {e}")

def load_companies():
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_sales_data(company):
    """ Busca faturamento do mês na base específica da empresa """
    conn = None
    try:
        conn = fdb.connect(
            host="127.0.0.1",
            port=company['port'],
            database=company['db_path'],
            user=company['user'],
            password=company['pass'],
            charset='WIN1252'
        )
        cur = conn.cursor()
        
        today = date.today()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        
        sql = f"""
            SELECT 
                SUM(CAST(COALESCE(PEV_VALOR_TOTAL, 0) AS NUMERIC(18,2))) as TOTAL,
                COUNT(*) as PEDIDOS
            FROM TB_PEDIDO_VENDA
            WHERE PEV_DT_LANCAMENTO BETWEEN '{start_date}' AND '{end_date}'
              AND COALESCE(PEV_STATUS, '') <> 'CANCELADO'
        """
        
        cur.execute(sql)
        result = cur.fetchone()
        
        return {
            "cnpj": company['cnpj'],
            "type": "VENDAS",
            "content": {
                "faturamento_mes": float(result[0] or 0),
                "total_pedidos": int(result[1] or 0),
                "razao_social": company.get('razao_social', 'N/A'),
                "periodo": f"{start_date} ate {end_date}",
                "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    except Exception as e:
        print(f"[{company['cnpj']}] Erro ao ler Firebird: {e}")
        return None
    finally:
        if conn: conn.close()

def check_remote_commands(company):
    """ 
    Verifica se a API Central tem algum pedido de informação 
    ex: 'O backend pede e o agente pesquisa'
    """
    cnpj = company['cnpj']
    token = company.get('api_token', API_TOKEN)
    try:
        url = f"{API_BASE_URL}/remote-tasks?cnpj={cnpj}"
        headers = {"Authorization": f"Bearer {token}"}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            tasks = res.json()
            for task in tasks:
                execute_task(company, task)
    except Exception as e:
        print(f"[{cnpj}] Erro ao buscar tarefas remotas: {e}")

def execute_task(company, task):
    """ Executa um comando no Firebird e devolve o resultado para a API """
    cnpj = company['cnpj']
    task_id = task['id']
    command = task['command']
    params = json.loads(task['params']) if task['params'] else {}
    
    print(f"[{cnpj}] Executando tarefa #{task_id}: {command}")
    
    conn = None
    try:
        conn = fdb.connect(
            host="127.0.0.1",
            port=company['port'],
            database=company['db_path'],
            user=company['user'],
            password=company['pass'],
            charset='WIN1252'
        )
        cur = conn.cursor()
        
        # Exemplo: Executar SQL genérico enviado pelo backend
        if command == "EXECUTE_SQL":
            sql = params.get("sql")
            cur.execute(sql)
            columns = [col[0] for col in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            result_data = rows
        
        # Exemplo: Buscar estoque de um produto
        elif command == "GET_STOCK":
            prod_id = params.get("product_id")
            cur.execute("SELECT PRO_ESTOQUE FROM TB_PRODUTO WHERE PRO_ID = ?", (prod_id,))
            row = cur.fetchone()
            result_data = {"stock": float(row[0] if row else 0)}
        
        else:
            result_data = {"error": "Comando desconhecido"}

        # Enviar resultado de volta
        update_url = f"{API_BASE_URL}/remote-tasks/{task_id}"
        update_payload = {
            "status": "COMPLETED",
            "result": result_data
        }
        requests.patch(update_url, json=update_payload, headers={"Authorization": f"Bearer {API_TOKEN}"})
        print(f"[{cnpj}] Tarefa #{task_id} finalizada com sucesso.")

    except Exception as e:
        print(f"[{cnpj}] Erro na tarefa #{task_id}: {e}")
        update_url = f"{API_BASE_URL}/remote-tasks/{task_id}"
        requests.patch(update_url, json={"status": "ERROR", "result": {"error": str(e)}}, headers={"Authorization": f"Bearer {API_TOKEN}"})
    finally:
        if conn: conn.close()

def sync_all():
    companies = load_companies()
    if not companies:
        print("Nenhuma empresa configurada para sincronização.")
        return

    for company in companies:
        print(f"\n--- Iniciando Sincronismo: {company.get('razao_social', company['cnpj'])} ---")
        
        # 1. Enviar dados automáticos (Push)
        data = get_sales_data(company)
        token = company.get('api_token', API_TOKEN)
        
        if data:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            try:
                res = requests.post(f"{API_BASE_URL}/sync", json=data, headers=headers)
                if res.status_code == 200:
                    print(f"[{company['cnpj']}] Sucesso: Dados de vendas enviados.")
                else:
                    print(f"[{company['cnpj']}] Erro API: {res.status_code} - {res.text}")
            except Exception as e:
                print(f"[{company['cnpj']}] Erro conexão API: {e}")

        # 2. Verificar pedidos do backend (Pull)
        check_remote_commands(company)

if __name__ == "__main__":
    # Loop infinito para rodar a cada X minutos ou uma única vez
    # Para testes, vamos rodar uma vez
    sync_all()
