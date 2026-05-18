from sqlalchemy import text
from sqlalchemy.orm import Session
import re
import os
import json

def limpar(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def listar_empresas_erp(db: Session = None):
    print("\n[DEBUG EMPRESAS] --- INICIO DA CHAMADA ---")
    from app.database.erp_connection import current_cnpj
    cnpjs_ativos = set()
    
    # 1. Tentar Admin System
    try:
        import requests
        response = requests.get("http://127.0.0.1:3001/api/companies", timeout=1)
        if response.status_code == 200:
            for c in response.json():
                if c.get("status") == "ATIVO":
                    cnpjs_ativos.add(re.sub(r"\D", "", str(c.get("cnpj", ""))))
            print(f"[DEBUG EMPRESAS] Admin ON. Ativos: {len(cnpjs_ativos)}")
    except:
        print("[DEBUG EMPRESAS] Admin OFF.")

    empresas = []

    # 2. Tentar Banco de Dados Local (se houver)
    if db:
        try:
            sql = text("SELECT EMP_ID, EMP_FANTASIA, EMP_RAZAO_SOCIAL, EMP_CNPJ, EMP_CIDADE FROM TB_EMPRESA ORDER BY EMP_ID")
            rows = db.execute(sql).mappings().all()
            print(f"[DEBUG EMPRESAS] Banco Local encontrou {len(rows)} registros.")
            
            for row in rows:
                # Firebird dialect usually returns lowercase keys in mappings
                empresa_id = row.get("EMP_ID") or row.get("emp_id")
                cnpj_raw = row.get("EMP_CNPJ") or row.get("emp_cnpj")
                cnpj_limpo = re.sub(r"\D", "", limpar(cnpj_raw))
                
                # Filtro de licença
                if cnpjs_ativos and cnpj_limpo not in cnpjs_ativos:
                    continue

                fantasia = limpar(row.get("EMP_FANTASIA") or row.get("emp_fantasia"))
                razao = limpar(row.get("EMP_RAZAO_SOCIAL") or row.get("emp_razao_social"))
                nome = fantasia if fantasia else razao
                
                empresas.append({
                    "id": empresa_id,
                    "fantasia": fantasia,
                    "razao_social": razao,
                    "cnpj": cnpj_raw,
                    "cidade": limpar(row.get("EMP_CIDADE") or row.get("emp_cidade")),
                    "status": "ATIVO",
                    "nome_exibicao": nome
                })
        except Exception as e:
            print(f"[DEBUG EMPRESAS] Erro ao ler banco local: {e}")

    # 3. Fallback para companies.json (se a lista ainda estiver vazia)
    if not empresas:
        print("[DEBUG EMPRESAS] Usando fallback do companies.json")
        try:
            cnpj_logado = re.sub(r"\D", "", str(current_cnpj.get() or ""))
            if os.path.exists("companies.json"):
                with open("companies.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
                    for c in config:
                        cnpj_c = re.sub(r"\D", "", str(c.get("cnpj", "")))
                        if cnpj_c == cnpj_logado or not cnpj_logado:
                            empresas.append({
                                "id": 1,
                                "fantasia": c.get("razao_social", "Empresa"),
                                "razao_social": c.get("razao_social", ""),
                                "cnpj": c.get("cnpj", ""),
                                "cidade": "Sincronizada",
                                "status": "ATIVO",
                                "nome_exibicao": c.get("razao_social", "Empresa")
                            })
                            break
        except Exception as e:
            print(f"[DEBUG EMPRESAS] Erro no fallback JSON: {e}")

    # 4. Fallback final (não pode retornar vazio)
    if not empresas:
        empresas.append({
            "id": 1,
            "fantasia": "Minha Empresa",
            "razao_social": "Dashboard",
            "cnpj": "",
            "cidade": "-",
            "status": "ATIVO",
            "nome_exibicao": "Minha Empresa"
        })

    print(f"[DEBUG EMPRESAS] Enviando {len(empresas)} empresas. Primeiro nome: {empresas[0]['nome_exibicao']}")
    return empresas