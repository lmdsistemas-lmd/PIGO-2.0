from __future__ import annotations

from app.repositories.dashboard_financeiro_repository import DashboardFinanceiroRepository
from app.services.base_dashboard_service import BaseDashboardService


class DashboardFinanceiroService(BaseDashboardService):
    def __init__(self) -> None:
        self.repository = DashboardFinanceiroRepository()

    def get_dashboard_financeiro(
        self,
        period: str,
        report_type: str,
        start: str | None,
        end: str | None,
        empresa_id: int | None = None,
    ) -> dict:
        date_range = self._resolve_period(period, start, end)

        # Tentar carregar dados sincronizados (JSON) como fallback
        sync_data = self._load_sync_data()
        if sync_data and ("FINANCEIRO" in sync_data or "VENDAS" in sync_data):
            print(f"[DEBUG SYNC] Aplicando dados sincronizados para o Dashboard Financeiro")
            return self._apply_sync_data(sync_data, report_type)

        print(f"[DEBUG SYNC] Nenhum dado sincronizado encontrado. Buscando no banco local.")

        contas_pagar_total = self.repository.get_contas_pagar_total(
            date_range, empresa_id, report_type
        )
        contas_receber_total = self.repository.get_contas_receber_total(
            date_range, empresa_id, report_type
        )

        total_vencido = (
            self.repository.get_total_receber_vencido(empresa_id, report_type)
            if report_type == "aberto"
            else 0
        )

        recuperado_mes = self.repository.get_total_recebido_periodo(
            date_range, empresa_id, report_type
        )

        return {
            "contasPagar": {
                "total": contas_pagar_total,
                "variation": self._get_contas_pagar_variation(
                    date_range, empresa_id, report_type
                ),
                "subtitle": (
                    "Compromissos financeiros em aberto do periodo selecionado"
                    if report_type == "aberto"
                    else "Pagamentos/baixas financeiras do periodo selecionado"
                ),
                "highlight": self.repository.get_contas_pagar_highlight(
                    empresa_id, report_type
                ),
                "history": self.repository.get_contas_pagar_history(
                    empresa_id, report_type
                ),
            },
            "contasReceber": {
                "total": contas_receber_total,
                "variation": self._get_contas_receber_variation(
                    date_range, empresa_id, report_type
                ),
                "subtitle": (
                    "Titulos a receber e carteira financeira ativa"
                    if report_type == "aberto"
                    else "Titulos faturados/baixados no periodo"
                ),
                "highlight": self.repository.get_contas_receber_highlight(
                    date_range, empresa_id, report_type
                ),
                "history": self.repository.get_contas_receber_history(
                    empresa_id, report_type
                ),
            },
            "inadimplencia": {
                "taxa": round((total_vencido / contas_receber_total) * 100, 1)
                if contas_receber_total and report_type == "aberto"
                else 0,
                "totalVencido": total_vencido,
                "totalReceber": contas_receber_total,
                "recuperadoMes": recuperado_mes,
            },
            "receitasDespesas": self.repository.get_receitas_despesas(
                date_range, empresa_id, report_type
            ),
            "aging": self.repository.get_aging(empresa_id, report_type),
            "melhoresClientes": self.repository.get_melhores_clientes(
                date_range, empresa_id, report_type
            ),
            "melhoresFornecedores": self.repository.get_melhores_fornecedores(
                date_range, empresa_id, report_type
            ),
            "estoqueCritico": self.repository.get_estoque_critico(empresa_id),
            "cidadesClientes": self.repository.get_clientes_por_cidade(
                date_range, empresa_id, report_type
            ),
        }

    def _get_contas_receber_variation(
        self,
        date_range,
        empresa_id: int | None,
        report_type: str,
    ) -> str:
        previous_period = self._previous_period(date_range)
        current_value = self.repository.get_contas_receber_total(
            date_range, empresa_id, report_type
        )
        previous_value = self.repository.get_contas_receber_total(
            previous_period, empresa_id, report_type
        )
        return self._format_variation(current_value, previous_value)

    def _get_contas_pagar_variation(
        self,
        date_range,
        empresa_id: int | None,
        report_type: str,
    ) -> str:
        previous_period = self._previous_period(date_range)
        current_value = self.repository.get_contas_pagar_total(
            date_range, empresa_id, report_type
        )
        previous_value = self.repository.get_contas_pagar_total(
            previous_period, empresa_id, report_type
        )
        return self._format_variation(current_value, previous_value)

    def _apply_sync_data(self, sync_data: dict, report_type: str) -> dict:
        """
        Mapeia os dados crus do JSON de sincronismo para o formato do Dashboard
        """
        # Dados de VENDAS (se houver)
        vendas_data = sync_data.get("VENDAS", {})
        faturamento_mes = vendas_data.get("faturamento_mes", 0)
        total_pedidos = vendas_data.get("total_pedidos", 0)

        # Dados FINANCEIROS
        fin_data = sync_data.get("FINANCEIRO", {})
        total_vencido = fin_data.get("inadimplencia_total", 0)
        
        return {
            "contasPagar": {
                "total": 0,
                "variation": "Sync Ativo",
                "subtitle": "Dados sincronizados remotamente",
                "highlight": "",
                "history": [],
            },
            "contasReceber": {
                "total": faturamento_mes,
                "variation": "Sync Ativo",
                "subtitle": "Total faturado no mes (via Sync)",
                "highlight": "",
                "history": [],
            },
            "inadimplencia": {
                "taxa": 0,
                "totalVencido": total_vencido,
                "totalReceber": faturamento_mes,
                "recuperadoMes": 0,
            },
            "receitasDespesas": [],
            "aging": [],
            "melhoresClientes": [],
            "melhoresFornecedores": [],
            "estoqueCritico": [],
            "cidadesClientes": [],
            "is_remote": True
        }
