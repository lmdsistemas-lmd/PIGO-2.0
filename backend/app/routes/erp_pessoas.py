from fastapi import APIRouter, Depends

from app.routes.auth import get_current_user
from app.services.erp_query_service import ERPQueryService


router = APIRouter(prefix="/erp", tags=["ERP"])


@router.get("/pessoas")
def listar_pessoas(current_user: dict = Depends(get_current_user)):
    rows = ERPQueryService().fetch_all(
        """
        SELECT
            PES_ID,
            PES_RSOCIAL_NOME
        FROM TB_PESSOA
        ROWS 50
        """
    )
    return [{"id": row.get("PES_ID"), "nome": row.get("PES_RSOCIAL_NOME")} for row in rows]


@router.get("/colaboradores")
def listar_colaboradores(current_user: dict = Depends(get_current_user)):
    rows = ERPQueryService().fetch_all(
        """
        SELECT
            PES_ID,
            PES_RSOCIAL_NOME,
            PES_CNPJ_CPF
        FROM TB_PESSOA
        WHERE PES_COLABORADOR = 'S'
        ROWS 100
        """
    )
    return [
        {
            "id": row.get("PES_ID"),
            "nome": row.get("PES_RSOCIAL_NOME"),
            "cpf": row.get("PES_CNPJ_CPF"),
        }
        for row in rows
    ]
