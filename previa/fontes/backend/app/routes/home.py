from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.erp_connection import get_erp_db


router = APIRouter(tags=["Sistema"])


@router.get("/status")
def home():
    return {"mensagem": "API do dashboard ERP esta funcionando!"}


@router.get("/teste-banco")
def teste_banco(erp_db: Session = Depends(get_erp_db)):
    if erp_db is None:
        return {"banco_erp": "legado_firebird_desabilitado"}

    try:
        erp_db.execute(text("SELECT 1 FROM RDB$DATABASE"))
        return {"banco_erp": "conectado com sucesso"}
    except Exception as exc:
        return {"erro": str(exc)}
