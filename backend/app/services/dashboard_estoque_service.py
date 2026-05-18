from __future__ import annotations
from app.repositories.dashboard_estoque_repository import DashboardEstoqueRepository
from app.services.base_dashboard_service import BaseDashboardService

class DashboardEstoqueService(BaseDashboardService):
    def __init__(self) -> None:
        self.repository = DashboardEstoqueRepository()

    def get_dashboard_estoque(self, empresa_id: int | None = None) -> dict:
        resumo = self.repository.get_resumo_produtos(empresa_id)
        valores = self.repository.get_valores_estoque(empresa_id)
        alertas = self.repository.get_alertas_estoque(empresa_id)
        compras = self.repository.get_compras_periodo(empresa_id)
        
        return {
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
            "rotatividade": self.repository.get_maior_rotatividade(empresa_id),
            "criticos": self.repository.get_estoque_critico(empresa_id)
        }
