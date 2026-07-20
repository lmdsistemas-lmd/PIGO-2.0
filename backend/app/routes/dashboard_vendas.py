from fastapi import APIRouter, Query, Depends
from app.schemas.dashboard_vendas import DashboardVendasResponse
from app.services.dashboard_vendas_service import DashboardVendasService
from app.routes.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard Vendas"])


@router.get("/vendas", response_model=DashboardVendasResponse)
def get_dashboard_vendas(
    period: str = Query(default="month"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    empresa_id: int | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    service = DashboardVendasService()

    return service.get_dashboard_vendas(
        period=period,
        start=start,
        end=end,
        empresa_id=empresa_id,
    )


@router.get("/vendas/pedidos")
def get_detalhes_pedidos(
    period: str = Query(default="month"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    empresa_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    current_user: dict = Depends(get_current_user),
):
    service = DashboardVendasService()
    return service.get_detalhes_pedidos(period, start, end, empresa_id, page, page_size, status)


@router.get("/vendas/clientes_novos")
def get_detalhes_clientes(
    period: str = Query(default="month"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    empresa_id: int | None = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=10),
    current_user: dict = Depends(get_current_user),
):
    service = DashboardVendasService()
    return service.get_detalhes_novos_clientes(period, start, end, empresa_id, page, page_size)


@router.get("/vendas/pedido/{pedido_id}")
def get_pedido_detalhes(
    pedido_id: int,
    empresa_id: int,
    current_user: dict = Depends(get_current_user),
):
    service = DashboardVendasService()
    return service.get_pedido_detalhes_completos(pedido_id, empresa_id)
