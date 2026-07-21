from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from copy import deepcopy
import logging
import os
import threading
import time

from app.repositories.dashboard_financeiro_repository import DashboardFinanceiroRepository
from app.services.base_dashboard_service import BaseDashboardService
from app.database.erp_connection import current_cnpj, current_tenant_id

logger = logging.getLogger(__name__)

_dashboard_cache: dict[tuple, tuple[float, dict]] = {}
_dashboard_cache_lock = threading.Lock()
_DASHBOARD_CACHE_MAX_ENTRIES = 128


def clear_dashboard_financeiro_cache(tenant_id: str | None = None) -> None:
    """Invalida o cache após mutações financeiras ou sincronizações."""
    with _dashboard_cache_lock:
        if tenant_id is None:
            _dashboard_cache.clear()
            return
        for key in [key for key in _dashboard_cache if key[0] == str(tenant_id)]:
            _dashboard_cache.pop(key, None)


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
        user_scope: str | None = None,
    ) -> dict:
        started_at = time.perf_counter()
        date_range = self._resolve_period(period, start, end)

        cache_ttl = max(
            0,
            min(int(os.getenv("FINANCIAL_DASHBOARD_CACHE_TTL_SECONDS", "30")), 300),
        )
        cache_key = (
            str(current_tenant_id.get() or ""),
            str(current_cnpj.get() or ""),
            str(user_scope or ""),
            str(empresa_id or ""),
            period,
            report_type,
            date_range.start.isoformat(),
            date_range.end.isoformat(),
        )
        now = time.monotonic()
        cache_enabled = bool(cache_ttl and empresa_id is not None)
        if cache_enabled:
            with _dashboard_cache_lock:
                cached = _dashboard_cache.get(cache_key)
                if cached and now - cached[0] <= cache_ttl:
                    logger.info("dashboard.financeiro.cache status=hit")
                    return deepcopy(cached[1])

        # Tentar carregar dados sincronizados (JSON) como fallback
        sync_data = self._load_sync_data()
        if sync_data and ("FINANCEIRO" in sync_data or "VENDAS" in sync_data):
            print(f"[DEBUG SYNC] Aplicando dados sincronizados para o Dashboard Financeiro")
            return self._apply_sync_data(sync_data, report_type)

        previous_period = self._previous_period(date_range)

        def submit(executor, label, function, *args):
            context = copy_context()

            def run():
                block_started_at = time.perf_counter()
                try:
                    return context.run(function, *args)
                finally:
                    logger.info(
                        "dashboard.financeiro.block label=%s duration_ms=%.2f",
                        label,
                        (time.perf_counter() - block_started_at) * 1000,
                    )

            return executor.submit(run)

        # Cada consulta usa sua propria sessao. O limite evita pressionar o pool/Firebird.
        with ThreadPoolExecutor(max_workers=5, thread_name_prefix="financeiro") as executor:
            futures = {
                "pagar_total": submit(executor, "pagar_total", self.repository.get_contas_pagar_total, date_range, empresa_id, report_type),
                "receber_total": submit(executor, "receber_total", self.repository.get_contas_receber_total, date_range, empresa_id, report_type),
                "pagar_anterior": submit(executor, "pagar_anterior", self.repository.get_contas_pagar_total, previous_period, empresa_id, report_type),
                "receber_anterior": submit(executor, "receber_anterior", self.repository.get_contas_receber_total, previous_period, empresa_id, report_type),
                "vencido": submit(executor, "vencido", self.repository.get_total_receber_vencido, empresa_id, report_type),
                "recuperado": submit(executor, "recuperado", self.repository.get_total_recebido_periodo, date_range, empresa_id, report_type),
                "pagar_highlight": submit(executor, "pagar_highlight", self.repository.get_contas_pagar_highlight, empresa_id, report_type),
                "pagar_history": submit(executor, "pagar_history", self.repository.get_contas_pagar_history, empresa_id, report_type),
                "receber_highlight": submit(executor, "receber_highlight", self.repository.get_contas_receber_highlight, date_range, empresa_id, report_type),
                "receber_history": submit(executor, "receber_history", self.repository.get_contas_receber_history, empresa_id, report_type),
                "receitas_despesas": submit(executor, "receitas_despesas", self.repository.get_receitas_despesas, date_range, empresa_id, report_type),
                "aging": submit(executor, "aging", self.repository.get_aging, empresa_id, report_type),
                "clientes": submit(executor, "clientes", self.repository.get_melhores_clientes, date_range, empresa_id, report_type),
                "fornecedores": submit(executor, "fornecedores", self.repository.get_melhores_fornecedores, date_range, empresa_id, report_type),
                "estoque": submit(executor, "estoque", self.repository.get_estoque_critico, empresa_id),
                "cidades": submit(executor, "cidades", self.repository.get_clientes_por_cidade, date_range, empresa_id, report_type),
            }
            values = {name: future.result() for name, future in futures.items()}

        contas_pagar_total = values["pagar_total"]
        contas_receber_total = values["receber_total"]
        total_vencido = values["vencido"] if report_type == "aberto" else 0

        result = {
            "contasPagar": {
                "total": contas_pagar_total,
                "variation": self._format_variation(contas_pagar_total, values["pagar_anterior"]),
                "subtitle": (
                    "Compromissos financeiros em aberto do periodo selecionado"
                    if report_type == "aberto"
                    else "Pagamentos/baixas financeiras do periodo selecionado"
                ),
                "highlight": values["pagar_highlight"],
                "history": values["pagar_history"],
            },
            "contasReceber": {
                "total": contas_receber_total,
                "variation": self._format_variation(contas_receber_total, values["receber_anterior"]),
                "subtitle": (
                    "Titulos a receber e carteira financeira ativa"
                    if report_type == "aberto"
                    else "Titulos faturados/baixados no periodo"
                ),
                "highlight": values["receber_highlight"],
                "history": values["receber_history"],
            },
            "inadimplencia": {
                "taxa": round((total_vencido / contas_receber_total) * 100, 1)
                if contas_receber_total and report_type == "aberto"
                else 0,
                "totalVencido": total_vencido,
                "totalReceber": contas_receber_total,
                "recuperadoMes": values["recuperado"],
            },
            "receitasDespesas": values["receitas_despesas"],
            "aging": values["aging"],
            "melhoresClientes": values["clientes"],
            "melhoresFornecedores": values["fornecedores"],
            "estoqueCritico": values["estoque"],
            "cidadesClientes": values["cidades"],
        }

        logger.info(
            "dashboard.financeiro.completed duration_ms=%.2f period=%s type=%s",
            (time.perf_counter() - started_at) * 1000,
            period,
            report_type,
        )
        if cache_enabled:
            with _dashboard_cache_lock:
                if len(_dashboard_cache) >= _DASHBOARD_CACHE_MAX_ENTRIES:
                    oldest_key = min(_dashboard_cache, key=lambda key: _dashboard_cache[key][0])
                    _dashboard_cache.pop(oldest_key, None)
                _dashboard_cache[cache_key] = (time.monotonic(), deepcopy(result))
        return result

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
