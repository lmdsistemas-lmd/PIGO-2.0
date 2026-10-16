from fastapi import APIRouter, Depends

from app.routes.auth import get_current_user
from app.services.erp_query_service import ERPQueryService


router = APIRouter(prefix="/indicadores", tags=["Indicadores"])


@router.get("/resumo")
def resumo_funcionarios(current_user: dict = Depends(get_current_user)):
    rows = ERPQueryService().fetch_all(
        """
        SELECT
            C.COL_PESSOA,
            C.COL_STATUS,
            C.COL_SALARIO_VALOR,
            C.COL_DATA_AFASTAMENTO
        FROM TB_COLABORADOR C
        """
    )

    total_ativos = 0
    total_afastados = 0
    salarios = []
    for row in rows:
        status = str(row.get("COL_STATUS") or "").strip().upper()
        if status in {"A", "ATIVO", "1", "S"}:
            total_ativos += 1
        if row.get("COL_DATA_AFASTAMENTO") is not None:
            total_afastados += 1
        if row.get("COL_SALARIO_VALOR") is not None:
            try:
                salarios.append(float(row.get("COL_SALARIO_VALOR")))
            except (TypeError, ValueError):
                pass

    return {
        "total_funcionarios": len(rows),
        "total_ativos": total_ativos,
        "total_afastados": total_afastados,
        "media_salarial": round(sum(salarios) / len(salarios), 2) if salarios else 0,
    }


@router.get("/por-status")
def funcionarios_por_status(current_user: dict = Depends(get_current_user)):
    rows = ERPQueryService().fetch_all(
        """
        SELECT
            C.COL_STATUS,
            COUNT(*) AS TOTAL
        FROM TB_COLABORADOR C
        GROUP BY C.COL_STATUS
        ORDER BY TOTAL DESC
        """
    )
    return [
        {
            "status": str(row.get("COL_STATUS")).strip() if row.get("COL_STATUS") is not None else "Nao informado",
            "total_funcionarios": int(row.get("TOTAL") or 0),
        }
        for row in rows
    ]
