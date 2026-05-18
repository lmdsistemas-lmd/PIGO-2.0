from fastapi import APIRouter, Query, Depends
from app.schemas.dashboard_financeiro import DashboardFinanceiroResponse
from app.services.dashboard_financeiro_service import DashboardFinanceiroService
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Financeiro"])


@router.get("/financeiro", response_model=DashboardFinanceiroResponse)
def get_dashboard_financeiro(
    period: str = Query(default="month"),
    type: str = Query(default="faturamento"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    empresa_id: int | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    service = DashboardFinanceiroService()

    return service.get_dashboard_financeiro(
        period=period,
        report_type=type,
        start=start,
        end=end,
        empresa_id=empresa_id,
    )