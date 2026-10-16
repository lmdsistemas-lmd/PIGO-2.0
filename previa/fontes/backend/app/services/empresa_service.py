from sqlalchemy.orm import Session
import re
from app.services.erp_query_service import ERPQueryService

def limpar(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def listar_empresas_erp(db: Session = None):
    print("\n[DEBUG EMPRESAS] --- INICIO DA CHAMADA ---")
    empresas = []

    # 2. Tentar base sincronizada/ERP pela camada central com tenant_id.
    if db is not False:
        try:
            erp = ERPQueryService()
            rows = erp.fetch_all(
                """
                SELECT EMP_ID, EMP_FANTASIA, EMP_RAZAO_SOCIAL, EMP_CNPJ
                FROM TB_EMPRESA
                ORDER BY EMP_ID
                """
            )
            print(f"[DEBUG EMPRESAS] Banco Local encontrou {len(rows)} registros.")
            
            for row in rows:
                # Firebird dialect usually returns lowercase keys in mappings
                empresa_id = row.get("EMP_ID") or row.get("emp_id")
                cnpj_raw = row.get("EMP_CNPJ") or row.get("emp_cnpj")
                
                # Filtro de licença
                fantasia = limpar(row.get("EMP_FANTASIA") or row.get("emp_fantasia"))
                razao = limpar(row.get("EMP_RAZAO_SOCIAL") or row.get("emp_razao_social"))
                nome = fantasia if fantasia else razao
                
                empresas.append({
                    "id": empresa_id,
                    "empresa_id": empresa_id,
                    "erp_id": empresa_id,
                    "fantasia": fantasia,
                    "razao_social": razao,
                    "cnpj": cnpj_raw,
                    "cidade": "",
                    "status": "ATIVO",
                    "nome_exibicao": nome
                })
        except Exception as e:
            print(f"[DEBUG EMPRESAS] Erro ao ler banco local: {e}")

    # 4. Fallback final (não pode retornar vazio)
    if empresas:
        print(f"[DEBUG EMPRESAS] Enviando {len(empresas)} empresas. Primeiro nome: {empresas[0]['nome_exibicao']}")
    else:
        print("[DEBUG EMPRESAS] Nenhuma empresa espelhada encontrada para o tenant autenticado.")
    return empresas
