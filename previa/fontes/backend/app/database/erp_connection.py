import json
import os
import re
from contextvars import ContextVar
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


current_cnpj: ContextVar[str] = ContextVar("current_cnpj", default="default")
current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)
_engines = {}


def _legacy_firebird_enabled() -> bool:
    return os.getenv("ENABLE_LEGACY_FIREBIRD", "false").lower() in {"1", "true", "yes"}


def _load_fdb():
    if not _legacy_firebird_enabled():
        raise RuntimeError("Conexao Firebird legado desabilitada neste ambiente.")

    import fdb

    client_path = os.getenv("FB_CLIENT_PATH")
    if client_path:
        fdb.load_api(client_path)
    return fdb


def _companies_config_path() -> Path:
    configured = os.getenv("COMPANIES_CONFIG_PATH")
    if configured:
        return Path(configured)
    raise RuntimeError(
        "COMPANIES_CONFIG_PATH nao configurado. O P.I.G.O. SaaS nao usa arquivo local de empresas."
    )


def get_engine_for_cnpj(cnpj: str):
    _load_fdb()

    cnpj_clean = re.sub(r"\D", "", str(cnpj or ""))
    if not cnpj_clean or cnpj_clean == "default":
        cnpj_clean = "default"

    config_path = _companies_config_path()
    if not config_path.exists():
        raise RuntimeError(
            "Configuracao Firebird legado ausente. Defina COMPANIES_CONFIG_PATH "
            "somente em ambiente interno controlado."
        )

    with config_path.open("r", encoding="utf-8") as file:
        companies = json.load(file)

    company = None
    if cnpj_clean != "default":
        company = next((c for c in companies if re.sub(r"\D", "", str(c.get("cnpj", ""))) == cnpj_clean), None)

    if not company:
        raise RuntimeError(f"Empresa com CNPJ {cnpj_clean} nao cadastrada no legado.")

    if company.get("db_path") == "REMOTE":
        return None

    required_fields = ["user", "pass", "port", "db_path"]
    if any(not company.get(field) for field in required_fields):
        raise RuntimeError("Configuracao Firebird incompleta.")

    db_url = (
        f"firebird+fdb://{company['user']}:{company['pass']}"
        f"@127.0.0.1:{company['port']}/{company['db_path']}"
    )

    engine_key = cnpj_clean
    if engine_key not in _engines:
        _engines[engine_key] = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    return _engines[engine_key]


def get_session_for_cnpj(cnpj: str):
    engine = get_engine_for_cnpj(cnpj)
    if engine is None:
        return None
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def get_erp_db():
    cnpj = current_cnpj.get()
    if not _legacy_firebird_enabled():
        yield None
        return

    db = get_session_for_cnpj(cnpj)
    try:
        yield db
    finally:
        if db:
            db.close()
