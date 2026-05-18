import os
import time
import json
import logging
import requests
import fdb
import schedule
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configurações do Firebird
FB_HOST = os.getenv("FB_HOST", "127.0.0.1")
FB_PORT = int(os.getenv("FB_PORT", 3050))
FB_DATABASE = os.getenv("FB_DATABASE")
FB_USER = os.getenv("FB_USER", "SYSDBA")
FB_PASS = os.getenv("FB_PASS", "masterkey")
FB_CLIENT_PATH = os.getenv("FB_CLIENT_PATH")

# Configurações da API
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
API_TOKEN = os.getenv("API_TOKEN")
COMPANY_CNPJ = os.getenv("COMPANY_CNPJ")
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL_MINUTES", 5))

if FB_CLIENT_PATH:
    try:
        fdb.load_api(FB_CLIENT_PATH)
        logger.info(f"DLL do Firebird carregada de: {FB_CLIENT_PATH}")
    except Exception as e:
        logger.error(f"Erro ao carregar DLL do Firebird: {e}")

def get_db_connection():
    return fdb.connect(
        host=FB_HOST,
        port=FB_PORT,
        database=FB_DATABASE,
        user=FB_USER,
        password=FB_PASS,
        charset='WIN1252'
    )

def fetch_table_data(table_name, columns, filter_sql=""):
    """Busca dados de uma tabela específica do Firebird"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        col_string = ", ".join(columns)
        sql = f"SELECT {col_string} FROM {table_name}"
        if filter_sql:
            sql += f" WHERE {filter_sql}"
            
        cur.execute(sql)
        
        rows = []
        for row in cur.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                val = row[i]
                # Conversão de tipos para JSON
                if isinstance(val, (datetime, date)):
                    val = val.isoformat()
                elif hasattr(val, '__float__'): # Handle Decimal
                    f_val = float(val)
                    if f_val == int(f_val):
                        val = int(f_val)
                    else:
                        val = f_val
                
                row_dict[col] = val
            rows.append(row_dict)
            
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Erro ao buscar tabela {table_name}: {e}")
        return []

def send_to_dashboard(data_type, content):
    """Envia os dados capturados para a API Central"""
    if not COMPANY_CNPJ or not API_TOKEN:
        logger.error("CNPJ ou API_TOKEN não configurados")
        return False

    payload = {
        "cnpj": COMPANY_CNPJ,
        "type": data_type,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        url = f"{API_BASE_URL}/sync"
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        
        if response.status_code == 200:
            logger.info(f"[OK] {data_type} sincronizado ({len(content)} registros)")
            return True
        else:
            logger.error(f"[ERRO] {data_type}: API {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        logger.error(f"[ERRO] Falha ao enviar {data_type}: {e}")
        return False

def run_sync():
    logger.info("=== Iniciando Sincronismo Detalhado ===")
    
    state_file = "sync_state.json"
    is_first_run = not os.path.exists(state_file)
    
    if is_first_run:
        # Carga Histórica: Ano Anterior + Ano Atual
        data_corte = "2025-01-01"
        logger.info(f"MODO: CARGA HISTÓRICA (Desde {data_corte})")
    else:
        # Carga Incremental: Últimos 30 dias para pegar alterações de status
        data_corte = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        logger.info(f"MODO: INCREMENTAL (Desde {data_corte})")

    tables_to_sync = [
        ("TB_EMPRESA", ["EMP_ID", "EMP_FANTASIA", "EMP_RAZAO_SOCIAL", "EMP_CNPJ"]),
        ("TB_PEDIDO_VENDA", ["PEV_ID", "PEV_EMPRESA", "PEV_CLIENTE", "PEV_VENDEDOR", "PEV_DT_EMISSAO", "PEV_DT_FATURAMENTO", "PEV_DT_LANCAMENTO", "PEV_VALOR_TOTAL", "PEV_STATUS"], f"PEV_DT_LANCAMENTO >= '{data_corte}'"),
        ("TB_PEDIDO_VENDA_ITEM", ["PEVI_ID", "PEVI_PEDIDO_VENDA", "PEVI_EMPRESA", "PEVI_PRODUTO", "PEVI_QUANTIDADE", "PEVI_VALOR_UNITARIO", "PEVI_VALOR_CUSTO_UNITARIO", "PEVI_VALOR_TOTAL"], f"PEVI_PEDIDO_VENDA IN (SELECT PEV_ID FROM TB_PEDIDO_VENDA WHERE PEV_DT_LANCAMENTO >= '{data_corte}')"),
        ("TB_PESSOA", ["PES_ID", "PES_RSOCIAL_NOME", "PES_FANTASIA_APELIDO", "PES_CIDADE", "PES_DT_CADASTRO", "PES_EMAIL", "PES_TELEFONE", "PES_CELULAR", "PES_VENDEDOR"], f"PES_DT_CADASTRO >= '{data_corte}'" if not is_first_run else ""),
        ("TB_CLIENTE", ["CLI_PESSOA", "CLI_EMPRESA"]),
        ("TB_VENDEDOR", ["VDR_PESSOA"]),
        ("TB_CIDADE", ["CID_ID", "CID_NOME"]),
        ("TB_PRODUTO", ["PRD_ID", "PRD_EMPRESA", "PRD_DESCRICAO", "PRD_GRUPO", "PRD_MARCA", "PRD_STATUS", "PRD_ESTOQUE_MINIMO", "PRD_PRECO_VENDA", "PRD_PRECO_CUSTO"]),
        ("TB_USUARIO", ["USU_ID", "USU_LOGIN", "USU_NOME"]),
        ("TB_RECEBIMENTO", ["REC_ID", "REC_EMPRESA", "REC_PESSOA", "REC_DT_EMISSAO", "REC_DT_VENCIMENTO", "REC_VALOR", "REC_STATUS", "REC_ABERTO"], f"REC_DT_EMISSAO >= '{data_corte}'"),
        ("TB_PAGAMENTO", ["PAG_ID", "PAG_EMPRESA", "PAG_PESSOA", "PAG_DT_VENCIMENTO", "PAG_VALOR", "PAG_STATUS", "PAG_ABERTO"], f"PAG_DT_VENCIMENTO >= '{data_corte}'"),
        ("TB_PRODUTO_ESTOQUE", ["PRDE_PRODUTO", "PRDE_EMPRESA", "PRDE_ESTOQUE"]),
        ("TB_PROD_GRUPO", ["PGRU_ID", "PGRU_DESCRICAO"]),
        ("TB_PROD_MARCA", ["PMAR_ID", "PMAR_DESCRICAO"]),
        ("TB_ESPECIE_MOEDA", ["ESP_ID", "ESP_DESCRICAO"]),
        ("TB_PEDIDO_VENDA_FIN", ["PEVF_PEDIDO_VENDA", "PEVF_ID", "PEVF_EMPRESA", "PEVF_ESPECIE_MOEDA", "PEVF_VALOR"], f"PEVF_PEDIDO_VENDA IN (SELECT PEV_ID FROM TB_PEDIDO_VENDA WHERE PEV_DT_LANCAMENTO >= '{data_corte}')"),
        ("TB_COLABORADOR", ["COL_PESSOA", "COL_EMPRESA", "COL_CARGO", "COL_STATUS"]),
        ("TB_AUDITORIA", ["AUD_EMPRESA", "AUD_TABELA", "AUD_ID_REGISTRO", "AUD_SEQUENCIA", "AUD_ACAO", "AUD_DT_LANCAMENTO", "AUD_DT_ACAO", "AUD_USUARIO", "AUD_TABELA_DESC", "AUD_DESC_REGISTRO"], f"AUD_DT_LANCAMENTO >= '{data_corte}'")
    ]

    success_all = True
    for table_name, columns, *filter_sql in tables_to_sync:
        f_sql = filter_sql[0] if filter_sql else ""
        data = fetch_table_data(table_name, columns, f_sql)
        
        if data:
            # Envia em lotes (chunks) de 1000 registros para ser mais seguro
            chunk_size = 1000
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                if not send_to_dashboard(table_name, chunk):
                    success_all = False
                time.sleep(0.2) # Pequeno intervalo para não afogar o servidor no login
        else:
            logger.info(f"[AVISO] Tabela {table_name} sem dados novos para o filtro.")

    if success_all and is_first_run:
        with open(state_file, "w") as f:
            json.dump({"last_full_sync": datetime.now().isoformat(), "initial_load_complete": True}, f)
        logger.info("-> Carga Histórica Finalizada e Registrada.")

    logger.info("=== Ciclo de Sincronismo Finalizado ===")

def start_agent():
    logger.info("AGENTE SAAS ATIVO - MODO MIRROR")
    run_sync()
    schedule.every(SYNC_INTERVAL).minutes.do(run_sync)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    start_agent()
