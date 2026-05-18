from fastapi import APIRouter, Query
from app.services.dashboard_consolidado_service import DashboardConsolidadoService

router = APIRouter(prefix="/api/dashboard/consolidado", tags=["Dashboard Consolidado"])
service = DashboardConsolidadoService()

@router.get("")
def get_consolidado(
    period: str = Query(default="this_month"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None)
):
    return service.get_dashboard_data(period, start, end)
