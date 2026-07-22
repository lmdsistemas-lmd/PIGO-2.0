import unittest

from app.schemas.reporting import ReportDefinition, ReportFilterValue, ReportTotal
from app.services.report_catalog import CATALOG, READY_TEMPLATES, ReportCatalog
from app.services.business_semantic_layer import BusinessSemanticLayer
from app.services.report_engine import ReportEngine, clear_report_cache
from app.services.report_query_builder import ReportQueryBuilder


class FakeProvider:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return [{"number": "10", "total": 99.9}]


class ReportEngineTests(unittest.TestCase):
    def setUp(self):
        clear_report_cache()
        self.definition = ReportDefinition(
            category="sales", source="orders", fields=["number", "total"], chart="table"
        )

    def test_public_catalog_never_exposes_physical_sql(self):
        catalog = ReportCatalog().public_catalog()
        source = catalog["sales"]["sources"]["orders"]
        self.assertNotIn("table", source)
        self.assertNotIn("joins", catalog["sales"]["sources"]["items"])
        self.assertNotIn("expression", source["fields"]["total"])
        for category in catalog.values():
            for public_source in category["sources"].values():
                for field in public_source["fields"].values():
                    self.assertTrue(field["semantic_id"])
                    self.assertTrue(field["description"])
                    self.assertTrue(field["help"])
                    self.assertIn("can_group", field)
                    self.assertIn("can_filter", field)

    def test_unknown_field_and_filter_are_rejected(self):
        with self.assertRaises(ValueError):
            ReportQueryBuilder().build(
                ReportDefinition(category="sales", source="orders", fields=["number; DROP TABLE tenants"]),
                1,
            )

    def test_builder_generates_only_catalog_sql_and_bound_values(self):
        definition = ReportDefinition(
            category="finance", source="receipts", fields=["number", "amount"],
            filters=[ReportFilterValue(field="status", operator="in", value=["BX", "AB"])],
        )
        sql, params = ReportQueryBuilder().build(definition, 1)
        self.assertIn("FROM TB_RECEBIMENTO REC", sql)
        self.assertIn("REC.REC_EMPRESA = :report_company", sql)
        self.assertNotIn("BX", sql)
        self.assertEqual(params["filter_0_0"], "BX")

    def test_cache_is_isolated_by_tenant_and_company(self):
        provider = FakeProvider(); engine = ReportEngine(provider=provider)
        first = engine.execute(self.definition, "tenant-a", 1)
        repeated = engine.execute(self.definition, "tenant-a", 1)
        engine.execute(self.definition, "tenant-a", 2)
        engine.execute(self.definition, "tenant-b", 1)
        self.assertEqual(first["cache"], "miss")
        self.assertEqual(repeated["cache"], "hit")
        self.assertEqual(len(provider.calls), 3)

    def test_aggregation_must_be_allowed_by_catalog(self):
        definition = ReportDefinition(
            category="finance", source="receipts", fields=["status"], group_by=["status"],
            totals=[ReportTotal(field="amount", aggregation="sum")], chart="bar",
        )
        sql, _ = ReportQueryBuilder().build(definition, 1)
        self.assertIn("SUM(", sql)
        self.assertIn("GROUP BY", sql)

    def test_phase_two_sources_generate_catalogued_joins(self):
        builder = ReportQueryBuilder()
        definitions = {
            "items": ["order_number", "product", "total"],
            "customers": ["customer_id", "name", "city"],
            "products": ["product_id", "product", "sale_price"],
            "sellers": ["seller_id", "name"],
        }
        for source, fields in definitions.items():
            sql, params = builder.build(ReportDefinition(category="sales", source=source, fields=fields), 1)
            self.assertNotIn(";", sql)
            self.assertEqual(params.get("report_company", "1"), "1")
        items_sql, _ = builder.build(ReportDefinition(category="sales", source="items", fields=definitions["items"]), 1)
        self.assertIn("JOIN TB_PEDIDO_VENDA", items_sql)
        self.assertIn("LEFT JOIN TB_PRODUTO", items_sql)

    def test_dynamic_filter_options_are_catalogued(self):
        sql, params = ReportQueryBuilder().build_filter_options("sales", "items", "product_id", 1)
        self.assertIn("SELECT DISTINCT", sql)
        self.assertIn("PEVI_PRODUTO", sql)
        self.assertEqual(params["report_company"], "1")
        with self.assertRaises(ValueError):
            ReportQueryBuilder().build_filter_options("sales", "items", "period", 1)

    def test_ready_templates_all_validate(self):
        builder = ReportQueryBuilder()
        for template in READY_TEMPLATES:
            definition = ReportDefinition.model_validate(template["definition"])
            builder.build(definition, 1)

    def test_business_dictionary_contains_no_physical_identifiers(self):
        dictionary = BusinessSemanticLayer().public_dictionary(CATALOG)
        serialized = str(dictionary).upper()
        self.assertNotIn("TB_", serialized)
        self.assertNotIn("PEV_", serialized)
        self.assertNotIn("REC_", serialized)
        self.assertTrue(any(item["semantic_id"] == "sales.orders.total" for item in dictionary))

    def test_preview_columns_use_business_metadata(self):
        provider = FakeProvider(); engine = ReportEngine(provider=provider)
        result = engine.execute(self.definition, "tenant-semantic", 1)
        total = next(item for item in result["columns"] if item["key"] == "total")
        self.assertEqual(total["label"], "Valor da venda")
        self.assertEqual(total["format"], "currency")
        self.assertTrue(total["description"])


if __name__ == "__main__":
    unittest.main()
