from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.erp_connection import get_erp_db
from app.services.performance_service import PerformanceService

router = APIRouter(prefix="/performance", tags=["Performance"])


@router.get("/visao-geral")
def obter_visao_geral_performance(
    acao: str = Query(default=""),
    departamento_id: Optional[int] = Query(default=None),
    data_inicial: str = Query(default=""),
    data_final: str = Query(default=""),
    erp_db: Session = Depends(get_erp_db),
):
    service = PerformanceService(erp_db=erp_db)
    return service.obter_visao_geral(
        acao=acao,
        data_inicial=data_inicial,
        data_final=data_final,
    )


@router.get("/filtros")
def obter_filtros_performance(
    tipo: str = Query(..., description="I, A, E ou C"),
    data_inicial: str = Query(default=""),
    data_final: str = Query(default=""),
    erp_db: Session = Depends(get_erp_db),
):
    service = PerformanceService(erp_db=erp_db)
    return service.obter_filtros_detalhe(
        tipo=tipo,
        data_inicial=data_inicial,
        data_final=data_final,
    )


@router.get("/registros")
def obter_registros_performance(
    tipo: str = Query(..., description="I, A, E ou C"),
    usuario: str = Query(default=""),
    tabela: str = Query(default=""),
    data_inicial: str = Query(default=""),
    data_final: str = Query(default=""),
    erp_db: Session = Depends(get_erp_db),
):
    service = PerformanceService(erp_db=erp_db)
    return service.obter_registros(
        tipo=tipo,
        usuario=usuario,
        tabela=tabela,
        data_inicial=data_inicial,
        data_final=data_final,
    )
