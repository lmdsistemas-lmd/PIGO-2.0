from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.session import get_db
from app.database.erp_connection import get_erp_db
from app.models.funcionario import Funcionario

router = APIRouter(prefix="/rh", tags=["RH Integração"])


@router.post("/vincular-funcionario")
def vincular_funcionario_erp(
    col_pessoa: int,
    departamento_id: int,
    db: Session = Depends(get_db),
    erp_db: Session = Depends(get_erp_db)
):
    existente = db.query(Funcionario).filter(
        Funcionario.col_pessoa == col_pessoa
    ).first()

    if existente:
        return {
            "erro": "Este colaborador do ERP já está vinculado no RH.",
            "funcionario_id": existente.id,
            "col_pessoa": existente.col_pessoa
        }

    query = text("""
        SELECT
            COL_PESSOA
        FROM TB_COLABORADOR
        WHERE COL_PESSOA = :col_pessoa
    """)

    result = erp_db.execute(query, {"col_pessoa": col_pessoa}).fetchone()

    if not result:
        return {
            "erro": "Colaborador não encontrado no ERP."
        }

    novo = Funcionario(
        col_pessoa=col_pessoa,
        departamento_id=departamento_id
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {
        "mensagem": "Funcionário vinculado com sucesso.",
        "funcionario": {
            "id": novo.id,
            "col_pessoa": novo.col_pessoa,
            "departamento_id": novo.departamento_id
        }
    }