import os
import json
import fdb
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextvars import ContextVar

# ContextVar para armazenar o CNPJ da requisição atual
current_cnpj: ContextVar[str] = ContextVar("current_cnpj", default="default")

# =========================================================
# CLIENTE FIREBIRD
# =========================================================
fdb.load_api(
    r"C:\Program Files (x86)\Firebird\Firebird_5_0\fbclient.dll"
)

# Cache de engines
_engines = {}

def get_engine_for_cnpj(cnpj: str):
    cnpj_clean = re.sub(r"\D", "", str(cnpj))
    
    # Se não houver CNPJ ou for default, tentamos pegar o primeiro do arquivo
    if not cnpj_clean or cnpj_clean == "default":
        cnpj_clean = "default"

    # Carregar do companies.json
    config_path = "companies.json"
    if not os.path.exists(config_path):
        config_path = os.path.join(os.getcwd(), "companies.json")
        if not os.path.exists(config_path):
             config_path = os.path.join(os.path.dirname(__file__), "..", "..", "companies.json")

    if not os.path.exists(config_path):
        raise Exception(f"Arquivo de configuracao nao encontrado: {config_path}")
    
    with open(config_path, "r") as f:
        companies = json.load(f)
    
    company = None
    if cnpj_clean != "default":
        company = next((c for c in companies if re.sub(r"\D", "", str(c["cnpj"])) == cnpj_clean), None)
    
    if not company:
        raise Exception(f"Empresa com CNPJ {cnpj_clean} nao cadastrada no sistema.")

    if company.get('db_path') == 'REMOTE':
        return None

    db_url = f"firebird+fdb://{company['user']}:{company['pass']}@127.0.0.1:{company['port']}/{company['db_path']}"
    
    # Se mudou o banco para este CNPJ ou não existe, cria engine
    engine_key = cnpj_clean
    if engine_key not in _engines:
        _engines[engine_key] = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
    return _engines[engine_key]

def get_session_for_cnpj(cnpj: str):
    engine = get_engine_for_cnpj(cnpj)
    if engine is None:
        return None
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

# Dependência dinâmica para o FastAPI
def get_erp_db():
    cnpj = current_cnpj.get()
    # Log para o terminal para sabermos quem está pedindo conexão
    print(f"[DB] Sessao solicitada para CNPJ: {cnpj}")
    
    db = get_session_for_cnpj(cnpj) 
    try:
        yield db
    finally:
        if db:
            db.close()
 
