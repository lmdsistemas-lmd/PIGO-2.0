from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.erp_connection import get_erp_db
from app.services.empresa_service import listar_empresas_erp

router = APIRouter(prefix="/empresas", tags=["Empresas"])


@router.get("")
def listar_empresas(db: Session = Depends(get_erp_db)):
    return listar_empresas_erp(db)