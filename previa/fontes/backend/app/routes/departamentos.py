from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.departamento import Departamento

router = APIRouter(prefix="/departamentos", tags=["Departamentos"])


@router.get("/")
def listar_departamentos(db: Session = Depends(get_db)):
    departamentos = db.query(Departamento).order_by(Departamento.nome).all()

    return [
        {
            "id": departamento.id,
            "nome": departamento.nome
        }
        for departamento in departamentos
    ]