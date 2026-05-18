from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.erp_connection import get_erp_db

router = APIRouter()


@router.get("/")
def home():
    return {
        "mensagem": "API do dashboard ERP está funcionando!"
    }


@router.get("/teste-banco")
def teste_banco(erp_db: Session = Depends(get_erp_db)):
    try:
        erp_db.execute(text("SELECT 1 FROM RDB$DATABASE"))
        return {"banco_erp": "conectado com sucesso"}
    except Exception as e:
        return {"erro": str(e)}
