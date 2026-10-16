from __future__ import annotations
from app.repositories.dashboard_consolidado_repository import DashboardConsolidadoRepository
from app.services.base_dashboard_service import BaseDashboardService, DateRange

class DashboardConsolidadoService(BaseDashboardService):
    def __init__(self):
        self.repository = DashboardConsolidadoRepository()

    def get_dashboard_data(self, period: str, start: str | None, end: str | None) -> dict:
        date_range = self._resolve_period(period, start, end)
        
        # Tentar carregar dados sincronizados (JSON) como fallback
        sync_data = self._load_sync_data()
        if sync_data:
            print(f"[DEBUG SYNC] Aplicando dados sincronizados para o Dashboard Consolidado")
            return self._apply_sync_data(sync_data, period, date_range)

        resumo_filiais = self.repository.get_resumo_consolidado(date_range)
        
        # Totais da Rede
        faturamento_total = sum(f["faturamento"] for f in resumo_filiais)
        total_vendas = sum(f["vendas"] for f in resumo_filiais)
        ticket_medio_rede = round((faturamento_total / total_vendas), 2) if total_vendas > 0 else 0
        filiais_ativas = len(resumo_filiais)
        
        vendas_dia_semana = self.repository.get_vendas_por_dia_semana(date_range)
        vendas_mensais = self.repository.get_vendas_mensais()
        
        return {
            "cards": {
                "faturamento_total": faturamento_total,
                "total_vendas": total_vendas,
                "ticket_medio": ticket_medio_rede,
                "filiais_ativas": filiais_ativas
            },
            "resumo_filiais": resumo_filiais,
            "graficos": {
                "vendas_dia_semana": vendas_dia_semana,
                "vendas_mensais": vendas_mensais
            }
        }

    def _apply_sync_data(self, sync_data: dict, period: str, date_range: DateRange) -> dict:
        """
        Mapeia os dados crus do JSON de sincronismo para o formato Consolidado
        """
        vendas = sync_data.get("VENDAS", {})
        fin = sync_data.get("FINANCEIRO", {})
        
        vendas_diarias = vendas.get("vendas_diarias", [])
        
        faturamento = 0.0
        total_vendas = 0
        
        # Filtra os dados de acordo com o date_range selecionado no dashboard
        for dia in vendas_diarias:
            try:
                from datetime import datetime
                data_venda = datetime.strptime(dia["data"], "%Y-%m-%d").date()
                if date_range.start <= data_venda <= date_range.end:
                    faturamento += dia.get("faturamento", 0)
                    total_vendas += dia.get("pedidos", 0)
            except Exception:
                pass
        
        ticket_medio = faturamento / total_vendas if total_vendas > 0 else 0

        return {
            "cards": {
                "faturamento_total": faturamento,
                "total_vendas": total_vendas,
                "ticket_medio": round(ticket_medio, 2),
                "filiais_ativas": 1
            },
            "resumo_filiais": [
                {
                    "empresa_id": 1,
                    "empresa_nome": "Empresa Remota (Sync)",
                    "faturamento": faturamento,
                    "vendas": total_vendas,
                    "is_remote": True
                }
            ],
            "graficos": {
                "vendas_dia_semana": [],
                "vendas_mensais": []
            }
        }
