from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.erp_connection import get_erp_db

router = APIRouter(prefix="/erp", tags=["ERP Test"])


@router.get("/teste")
def testar_erp(db: Session = Depends(get_erp_db)):
    result = db.execute(text("SELECT 1 FROM RDB$DATABASE"))
    return {"status": "conectado ao ERP"}