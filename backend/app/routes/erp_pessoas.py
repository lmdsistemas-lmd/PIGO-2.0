from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.erp_connection import get_erp_db

router = APIRouter(prefix="/erp", tags=["ERP"])


@router.get("/pessoas")
def listar_pessoas(db: Session = Depends(get_erp_db)):

    query = text("""
        SELECT
            PES_ID,
            PES_RSOCIAL_NOME
        FROM TB_PESSOA
        ROWS 50
    """)

    result = db.execute(query)

    pessoas = []

    for row in result:
        pessoas.append({
            "id": row[0],
            "nome": row[1]
        })

    return pessoas

@router.get("/colaboradores")
def listar_colaboradores(db: Session = Depends(get_erp_db)):

    query = text("""
        SELECT
            PES_ID,
            PES_RSOCIAL_NOME,
            PES_CNPJ_CPF
        FROM TB_PESSOA
        WHERE PES_COLABORADOR = 'S'
        ROWS 100
    """)

    result = db.execute(query)

    colaboradores = []

    for row in result:
        colaboradores.append({
            "id": row[0],
            "nome": row[1],
            "cpf": row[2]
        })

    return colaboradores