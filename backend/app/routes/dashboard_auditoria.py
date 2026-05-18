from fastapi import APIRouter, Query

from app.schemas.dashboard_auditoria import (
    DashboardAuditoriaFuncionarioResponse,
    DashboardAuditoriaResponse,
)
from app.services.dashboard_auditoria_service import DashboardAuditoriaService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Auditoria"])


@router.get("/auditoria", response_model=DashboardAuditoriaResponse)
def get_dashboard_auditoria(
    period: str = Query(default="month"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    empresa_id: int | None = Query(default=None),
):
    service = DashboardAuditoriaService()
    return service.get_dashboard_auditoria(
        period=period,
        start=start,
        end=end,
        empresa_id=empresa_id,
    )


@router.get("/auditoria/funcionario/{colaborador_pessoa}", response_model=DashboardAuditoriaFuncionarioResponse)
def get_dashboard_auditoria_funcionario(
    colaborador_pessoa: int,
    period: str = Query(default="month"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    empresa_id: int | None = Query(default=None),
):
    service = DashboardAuditoriaService()
    return service.get_dashboard_auditoria_funcionario(
        colaborador_pessoa=colaborador_pessoa,
        period=period,
        start=start,
        end=end,
        empresa_id=empresa_id,
    )