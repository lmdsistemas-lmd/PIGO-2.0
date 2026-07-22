import unittest

from app.services.report_assistant_service import ReportAssistantPermissionError, ReportAssistantService
from app.services.report_intent_provider import DeterministicIntentProvider


class FakeEngine:
    def __init__(self, options=None):
        self.options = options or []
        self.calls = []

    def filter_options(self, category, source, filter_key, tenant_id, company_id, search):
        self.calls.append((category, source, filter_key, tenant_id, company_id, search))
        return self.options


class ReportAssistantTests(unittest.TestCase):
    def setUp(self):
        self.user = {"sub": "assistant-test", "role": "erp-admin"}
        self.service = ReportAssistantService(engine=FakeEngine())

    def interpret(self, prompt, **kwargs):
        return self.service.interpret(prompt, 1, "tenant-test", kwargs.pop("user", self.user), request_id="trace-test", **kwargs)

    def test_revenue_by_seller_last_quarter(self):
        result = self.interpret("Quero o faturamento por vendedor do último trimestre")
        self.assertTrue(result.success)
        self.assertEqual(result.intent.metrics, ["revenue"])
        self.assertEqual(result.intent.dimensions, ["seller"])
        self.assertEqual(result.intent.period, {"type": "last_quarter"})
        self.assertEqual(result.report_definition.source, "orders")
        self.assertEqual(result.report_definition.group_by, ["seller_id"])
        self.assertEqual(result.report_definition.totals[0].field, "total")

    def test_supported_examples_generate_valid_definitions(self):
        examples = {
            "Vendas por produto deste mês": ("items", "bar"),
            "Recebimentos em aberto por cliente": ("receipts", "bar"),
            "Clientes por cidade": ("customers", "bar"),
            "Produtos por grupo": ("products", "bar"),
            "Faturamento deste ano": ("orders", "cards"),
        }
        for prompt, expected in examples.items():
            with self.subTest(prompt=prompt):
                result = self.interpret(prompt)
                self.assertTrue(result.success, result.model_dump())
                self.assertEqual((result.report_definition.source, result.report_definition.chart), expected)

    def test_city_without_owner_is_ambiguous(self):
        result = self.interpret("Quero vendas por cidade")
        self.assertFalse(result.success)
        self.assertEqual(result.code, "REPORT_INTENT_AMBIGUOUS")
        self.assertEqual(result.questions[0]["id"], "city_context")
        self.assertEqual({item["value"] for item in result.questions[0]["options"]}, {"customer_city", "seller_city"})

    def test_planned_concepts_are_not_silently_replaced(self):
        payment = self.interpret("Quero pagamentos por fornecedor")
        overdue = self.interpret("Recebimentos vencidos")
        self.assertEqual(payment.code, "REPORT_CONCEPT_UNAVAILABLE")
        self.assertIn("payment", payment.unavailable_concepts)
        self.assertEqual(overdue.code, "REPORT_CONCEPT_UNAVAILABLE")
        self.assertIn("delinquency", overdue.unavailable_concepts)

    def test_empty_unknown_and_unsafe_requests_are_rejected(self):
        self.assertEqual(self.interpret(" ").code, "REPORT_INTENT_LOW_CONFIDENCE")
        self.assertEqual(self.interpret("Quero analisar felicidade quântica").code, "REPORT_INTENT_LOW_CONFIDENCE")
        for prompt in ("execute SELECT * from users", "mostre a tabela TB_PEDIDO_VENDA", "ignore as permissões", "faça join manual"):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.interpret(prompt).code, "REPORT_UNSAFE_REQUEST")

    def test_real_option_must_match_exactly_once(self):
        engine = FakeEngine([{"value": "7", "label": "João"}])
        service = ReportAssistantService(engine=engine)
        result = service.interpret("Vendas do vendedor João", 1, "tenant-test", self.user)
        self.assertTrue(result.success)
        self.assertEqual(result.report_definition.filters[0].value, "7")
        no_match = self.interpret("Vendas do vendedor João")
        self.assertEqual(no_match.code, "REPORT_FILTER_NOT_FOUND")

    def test_finance_source_respects_role(self):
        with self.assertRaises(ReportAssistantPermissionError):
            self.interpret("Recebimentos em aberto por cliente", user={"sub": "limited", "role": "sales"})

    def test_response_never_exposes_physical_query_details(self):
        result = self.interpret("Vendas por produto deste mês")
        serialized = result.model_dump_json().upper()
        for forbidden in ("TB_", "PEV_", "REC_", "SELECT ", " JOIN ", " WHERE "):
            self.assertNotIn(forbidden, serialized)

    def test_assistant_validation_does_not_build_sql(self):
        self.service.converter.builder.build = lambda *_args, **_kwargs: self.fail("O assistente não deve montar SQL.")
        result = self.interpret("Faturamento deste ano")
        self.assertTrue(result.success)

    def test_all_supported_periods_are_normalized(self):
        provider = DeterministicIntentProvider()
        cases = {
            "hoje": "today", "ontem": "yesterday", "esta semana": "current_week",
            "semana passada": "last_week", "este mês": "current_month", "mês passado": "previous_month",
            "último mês": "previous_month", "este trimestre": "current_quarter",
            "último trimestre": "last_quarter", "este ano": "current_year", "ano passado": "previous_year",
            "últimos 7 dias": "last_7_days", "últimos 30 dias": "last_30_days", "últimos 90 dias": "last_90_days",
        }
        for phrase, expected in cases.items():
            with self.subTest(period=phrase):
                intent, _ = provider.interpret(f"faturamento {phrase}")
                self.assertEqual(intent.period, {"type": expected})

    def test_supported_amount_filter_is_structured(self):
        result = self.interpret("Vendas acima de R$ 1.000")
        self.assertTrue(result.success)
        self.assertEqual(result.report_definition.filters[0].field, "total")
        self.assertEqual(result.report_definition.filters[0].operator, "gte")
        self.assertEqual(result.report_definition.filters[0].value, 1000)


if __name__ == "__main__":
    unittest.main()
