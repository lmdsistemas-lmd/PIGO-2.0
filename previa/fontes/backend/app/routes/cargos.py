from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.cargo import Cargo

router = APIRouter(prefix="/cargos", tags=["Cargos"])


@router.get("/")
def listar_cargos(db: Session = Depends(get_db)):
    cargos = db.query(Cargo).order_by(Cargo.nome).all()

    return [
        {
            "id": cargo.id,
            "nome": cargo.nome
        }
        for cargo in cargos
    ]