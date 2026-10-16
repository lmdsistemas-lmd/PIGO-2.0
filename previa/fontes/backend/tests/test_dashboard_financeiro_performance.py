import threading
import time
import unittest
from collections import Counter

from app.database.erp_connection import current_tenant_id
from app.services.dashboard_financeiro_service import (
    DashboardFinanceiroService,
    clear_dashboard_financeiro_cache,
)


class FakeFinanceiroRepository:
    def __init__(self):
        self.calls = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def _value(self, name, value):
        with self.lock:
            self.calls.append((name, current_tenant_id.get()))
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.005)
        with self.lock:
            self.active -= 1
        return value

    def get_contas_pagar_total(self, date_range, empresa_id, report_type):
        value = 100 if date_range.end.day >= date_range.start.day else 50
        return self._value("pagar_total", value)

    def get_contas_receber_total(self, date_range, empresa_id, report_type):
        value = 200 if date_range.end.day >= date_range.start.day else 100
        return self._value("receber_total", value)

    def get_total_receber_vencido(self, empresa_id, report_type):
        return self._value("vencido", 40)

    def get_total_recebido_periodo(self, date_range, empresa_id, report_type):
        return self._value("recuperado", 30)

    def get_contas_pagar_highlight(self, empresa_id, report_type):
        return self._value("pagar_highlight", "2 títulos")

    def get_contas_pagar_history(self, empresa_id, report_type):
        return self._value("pagar_history", [10, 20])

    def get_contas_receber_highlight(self, date_range, empresa_id, report_type):
        return self._value("receber_highlight", "5 dias")

    def get_contas_receber_history(self, empresa_id, report_type):
        return self._value("receber_history", [20, 40])

    def get_receitas_despesas(self, date_range, empresa_id, report_type):
        return self._value("receitas_despesas", [{"label": "Jul", "receitas": 200, "despesas": 100}])

    def get_aging(self, empresa_id, report_type):
        return self._value("aging", [{"faixa": "A vencer", "valor": 160}])

    def get_melhores_clientes(self, date_range, empresa_id, report_type):
        return self._value("clientes", [{"nome": "Cliente", "valor": 200}])

    def get_melhores_fornecedores(self, date_range, empresa_id, report_type):
        return self._value("fornecedores", [{"nome": "Fornecedor", "volume": 100}])

    def get_estoque_critico(self, empresa_id):
        return self._value("estoque", [])

    def get_clientes_por_cidade(self, date_range, empresa_id, report_type):
        return self._value("cidades", [{"cidade": "Leopoldina", "quantidade": 3}])


class DashboardFinanceiroPerformanceTests(unittest.TestCase):
    def setUp(self):
        clear_dashboard_financeiro_cache()

    def test_parallel_result_is_equivalent_and_tenant_is_preserved(self):
        tenant_id = "tenant-performance-test"
        token = current_tenant_id.set(tenant_id)
        try:
            service = DashboardFinanceiroService()
            repository = FakeFinanceiroRepository()
            service.repository = repository
            service._load_sync_data = lambda: None

            result = service.get_dashboard_financeiro(
                period="month",
                report_type="aberto",
                start=None,
                end=None,
                empresa_id=1,
            )
        finally:
            current_tenant_id.reset(token)

        self.assertEqual(result["contasPagar"]["total"], 100)
        self.assertEqual(result["contasReceber"]["total"], 200)
        self.assertEqual(result["inadimplencia"]["taxa"], 20.0)
        self.assertEqual(result["inadimplencia"]["recuperadoMes"], 30)
        self.assertEqual(result["receitasDespesas"][0]["receitas"], 200)
        self.assertTrue(all(call_tenant == tenant_id for _, call_tenant in repository.calls))
        self.assertLessEqual(repository.max_active, 5)
        self.assertGreater(repository.max_active, 1)

    def test_current_totals_are_not_queried_twice_for_variation(self):
        service = DashboardFinanceiroService()
        repository = FakeFinanceiroRepository()
        service.repository = repository
        service._load_sync_data = lambda: None

        service.get_dashboard_financeiro("month", "aberto", None, None, 1)

        counts = Counter(name for name, _ in repository.calls)
        self.assertEqual(counts["pagar_total"], 2)  # atual e período anterior
        self.assertEqual(counts["receber_total"], 2)  # atual e período anterior

    def test_cache_reuses_same_scope_and_never_crosses_tenants(self):
        service = DashboardFinanceiroService()
        repository = FakeFinanceiroRepository()
        service.repository = repository
        service._load_sync_data = lambda: None

        first_token = current_tenant_id.set("tenant-a")
        try:
            first = service.get_dashboard_financeiro("month", "aberto", None, None, 1, "user-a")
            calls_after_first = len(repository.calls)
            repeated = service.get_dashboard_financeiro("month", "aberto", None, None, 1, "user-a")
        finally:
            current_tenant_id.reset(first_token)

        self.assertEqual(first, repeated)
        self.assertEqual(len(repository.calls), calls_after_first)

        second_token = current_tenant_id.set("tenant-b")
        try:
            service.get_dashboard_financeiro("month", "aberto", None, None, 1, "user-a")
        finally:
            current_tenant_id.reset(second_token)

        self.assertGreater(len(repository.calls), calls_after_first)

    def test_cache_is_not_written_without_resolved_company(self):
        service = DashboardFinanceiroService()
        repository = FakeFinanceiroRepository()
        service.repository = repository
        service._load_sync_data = lambda: None

        service.get_dashboard_financeiro("month", "aberto", None, None, None, "user-a")
        calls_after_first = len(repository.calls)
        service.get_dashboard_financeiro("month", "aberto", None, None, None, "user-a")

        self.assertEqual(len(repository.calls), calls_after_first * 2)


if __name__ == "__main__":
    unittest.main()
