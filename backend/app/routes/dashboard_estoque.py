from fastapi import APIRouter, Depends, Query
from app.schemas.dashboard_estoque import DashboardEstoqueResponse
from app.services.dashboard_estoque_service import DashboardEstoqueService
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Estoque"])

@router.get("/estoque", response_model=DashboardEstoqueResponse)
def get_dashboard_estoque(
    empresa_id: int | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    service = DashboardEstoqueService()
    return service.get_dashboard_estoque(empresa_id=empresa_id)
