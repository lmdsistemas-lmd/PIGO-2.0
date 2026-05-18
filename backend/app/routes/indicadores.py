from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.erp_connection import get_erp_db

router = APIRouter(prefix="/indicadores", tags=["Indicadores"])


@router.get("/resumo")
def resumo_funcionarios(
    erp_db: Session = Depends(get_erp_db)
):
    query = text(
        """
        SELECT
            c.COL_PESSOA,
            c.COL_STATUS,
            c.COL_SALARIO_VALOR,
            c.COL_DATA_AFASTAMENTO
        FROM TB_COLABORADOR c
        """
    )

    colaboradores = erp_db.execute(query).fetchall()

    total_funcionarios = len(colaboradores)
    total_ativos = 0
    total_afastados = 0
    salarios = []

    for colaborador in colaboradores:
        status = colaborador[1]
        salario = colaborador[2]
        data_afastamento = colaborador[3]

        if status is not None:
            status_str = str(status).strip().upper()
            if status_str in ["A", "ATIVO", "1", "S"]:
                total_ativos += 1

        if data_afastamento is not None:
            total_afastados += 1

        if salario is not None:
            try:
                salarios.append(float(salario))
            except (TypeError, ValueError):
                pass

    media_salarial = round(sum(salarios) / len(salarios), 2) if salarios else 0

    return {
        "total_funcionarios": total_funcionarios,
        "total_ativos": total_ativos,
        "total_afastados": total_afastados,
        "media_salarial": media_salarial,
    }


@router.get("/por-status")
def funcionarios_por_status(
    erp_db: Session = Depends(get_erp_db)
):
    query = text(
        """
        SELECT
            c.COL_STATUS,
            COUNT(*) AS total
        FROM TB_COLABORADOR c
        GROUP BY c.COL_STATUS
        ORDER BY total DESC
        """
    )

    rows = erp_db.execute(query).fetchall()

    resultado = []

    for row in rows:
        resultado.append(
            {
                "status": str(row[0]).strip() if row[0] is not None else "Não informado",
                "total_funcionarios": int(row[1] or 0),
            }
        )

    return resultado
