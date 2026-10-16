import unittest
from datetime import date
from unittest.mock import Mock

from pydantic import ValidationError

from app.routes.commercial_analytics import GoalInput, admin, tenant
from app.services.commercial_analytics_service import CommercialAnalyticsService, classify_abc
from app.services.erp_query_service import ERPQueryService


class CommercialAnalyticsTests(unittest.TestCase):
    def test_abc_keeps_crossing_item_in_preceding_class(self):
        result = classify_abc([{"codigo": i, "valor": value} for i, value in enumerate([79, 15, 4, 2])])
        self.assertEqual([row["classe"] for row in result["produtos"]], ["A", "A", "B", "C"])
        self.assertAlmostEqual(result["produtos"][-1]["acumulado"], 100)
        self.assertEqual(result["total"], 100)

    def test_abc_zero_negative_and_dominant_product(self):
        self.assertEqual(classify_abc([{"valor": 0}, {"valor": -50}])["produtos"], [])
        result = classify_abc([{"codigo": "a", "valor": 99}, {"codigo": "b", "valor": 1}])
        self.assertEqual([row["classe"] for row in result["produtos"]], ["A", "C"])
        self.assertEqual(classify_abc([])["total"], 0)

    def test_custom_period_requires_ordered_complete_dates(self):
        service = CommercialAnalyticsService()
        for start, end in [(None, None), ("2026-10-20", "2026-10-01"), ("bad", "2026-10-01")]:
            with self.assertRaises(ValueError):
                service.period("custom", start, end)

    def test_customer_metrics_distinguish_no_purchases_and_new_registration(self):
        service = CommercialAnalyticsService()
        service._fetch_all = Mock(return_value=[
            {"CODIGO": 1, "NOME": "Ana", "CIDADE": "Palmas", "CADASTRO": date(2026, 10, 1)},
            {"CODIGO": 2, "NOME": "Bruno", "CIDADE": "Palmas", "CADASTRO": date(2026, 9, 1)},
        ])
        service.sales = Mock(return_value=[{"CODIGO": 1, "NOME": "Ana", "PEDIDOS": 2, "VALOR": 150}])
        result = service.customers(1, "custom", "2026-10-01", "2026-10-15")
        self.assertEqual(result["resumo"], {"clientes": 2, "compradores": 1, "novos": 1,
                                           "semCompras": 1, "faturamento": 150, "ticketMedio": 75})
        self.assertEqual(result["semCompras"][0]["nome"], "Bruno")

    def test_customer_and_abc_sql_bind_company_and_exclude_cancelled_sales(self):
        service = CommercialAnalyticsService()
        service._fetch_all = Mock(return_value=[])
        service.abc(7, "custom", "2026-10-01", "2026-10-02")
        sql, params = service._fetch_all.call_args.args
        self.assertEqual(str(params["empresa_id"]), "7")
        self.assertIn("PV.PEV_EMPRESA = I.PEVI_EMPRESA", sql)
        self.assertIn("'CANCELADO'", sql)
        erp = ERPQueryService()
        guarded = erp._inject_join_tenant_guards(sql, "I")
        guarded = erp._inject_root_tenant_filter(guarded, "tenant-one", params)
        self.assertIn("PV.tenant_id = I.tenant_id", guarded)
        self.assertIn("P.tenant_id = I.tenant_id", guarded)
        self.assertEqual(params["tenant_id_filter"], "tenant-one")

    def test_goals_reject_invalid_values_and_unscoped_users(self):
        for values in [{"valor": "0"}, {"valor": "-1"}, {"valor": "1.001"}, {"mes": "2026-10-02"}]:
            with self.assertRaises(ValidationError):
                GoalInput.model_validate({"empresa_id": 1, "mes": "2026-10-01", "valor": "100.00", **values})
        with self.assertRaises(Exception) as context:
            tenant({})
        self.assertEqual(context.exception.status_code, 401)
        with self.assertRaises(Exception) as context:
            admin({"role": "sales"})
        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
