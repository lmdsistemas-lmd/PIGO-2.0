from __future__ import annotations
from app.repositories.dashboard_estoque_repository import DashboardEstoqueRepository
from app.services.base_dashboard_service import BaseDashboardService
from app.repositories.stock_availability import stock_requires_consolidation

class DashboardEstoqueService(BaseDashboardService):
    def __init__(self) -> None:
        self.repository = DashboardEstoqueRepository()

    def get_dashboard_estoque(self, empresa_id: int | None = None) -> dict:
        resumo = self.repository.get_resumo_produtos(empresa_id)
        requires_rule = stock_requires_consolidation(self.repository, empresa_id)
        valores = {"custo": None, "venda": None} if requires_rule else self.repository.get_valores_estoque(empresa_id)
        alertas = {"total": None, "semEstoque": None, "abaixoMinimo": None} if requires_rule else self.repository.get_alertas_estoque(empresa_id)
        compras = self.repository.get_compras_periodo(empresa_id)
        
        return {
            "estoqueDisponivel": not requires_rule,
            "resumo": {
                "totalProdutos": resumo["total"],
                "ativos": resumo["ativos"],
                "inativos": resumo["inativos"]
            },
            "valores": {
                "custoTotal": valores["custo"],
                "vendaTotal": valores["venda"]
            },
            "alertas": {
                "total": alertas["total"],
                "semEstoque": alertas["semEstoque"],
                "abaixoMinimo": alertas["abaixoMinimo"]
            },
            "compras": {
                "quantidade": compras["quantidade"],
                "valorTotal": compras["valor"]
            },
            "rotatividade": [] if requires_rule else self.repository.get_maior_rotatividade(empresa_id),
            "criticos": [] if requires_rule else self.repository.get_estoque_critico(empresa_id)
        }
