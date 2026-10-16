"""Integration tests with synthetic rows shaped like the received ERP schema.

Set PIGO_SCHEMA_TEST_DATABASE_URL to a disposable local PostgreSQL database
whose name starts with pigo_schema_test_. Never run against an ERP database.
"""
import os
import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.services.operations_service import OperationsService
from app.services.sync_service import SyncService
from app.services.dashboard_estoque_service import DashboardEstoqueService
from app.repositories.dashboard_financeiro_repository import DashboardFinanceiroRepository
from app.repositories.stock_availability import stock_requires_consolidation


@unittest.skipUnless(os.getenv("PIGO_SCHEMA_TEST_DATABASE_URL"), "requires disposable schema test database")
class RealSchemaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(os.environ["PIGO_SCHEMA_TEST_DATABASE_URL"])
        url = cls.engine.url
        if url.host not in {"127.0.0.1", "localhost"} or not url.database.startswith("pigo_schema_test_"):
            raise RuntimeError("Only a disposable local pigo_schema_test_ database is allowed.")
        with Session(cls.engine) as db:
            if db.execute(text("SELECT 1 FROM information_schema.tables WHERE table_schema='public' LIMIT 1")).first():
                raise RuntimeError("The schema test database must be empty.")
            for tenant in ["tenant-a", "tenant-b"]:
                def sync(table, rows):
                    result = SyncService._sync_generic_table(db, tenant, table, rows)
                    if result["ignored"]:
                        raise AssertionError(result)
                sync("TB_PRODUTO", [{"PRD_ID": str(i), "PRD_EMPRESA": "1", "PRD_STATUS": "A", "PRD_DESCRICAO": f"Produto {tenant} {i}"} for i in [1, 2, 3]])
                sync("TB_PRODUTO_ESTOQUE", [
                    {"PRDE_PRODUTO": "1", "PRDE_EMPRESA": "1", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "0", "PRDE_ESTOQUE": 5},
                    {"PRDE_PRODUTO": "1", "PRDE_EMPRESA": "1", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "1", "PRDE_ESTOQUE": 7},
                    {"PRDE_PRODUTO": "1", "PRDE_EMPRESA": "2", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "0", "PRDE_ESTOQUE": 999},
                    {"PRDE_PRODUTO": "2", "PRDE_EMPRESA": "1", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "0", "PRDE_ESTOQUE": 0},
                    {"PRDE_PRODUTO": "3", "PRDE_EMPRESA": "1", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "0", "PRDE_ESTOQUE": None},
                    {"PRDE_PRODUTO": "3", "PRDE_EMPRESA": "3", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "0", "PRDE_ESTOQUE": None},
                ])
                sync("TB_PROD_CODIGO_BARRAS", [{"PRDC_PRODUTO": "1", "PRDC_EMPRESA": str(company), "PRDC_COD_BARRAS": code}
                    for company, code in [(1, "ABC"), (1, "DEF"), (2, "OTHER")]])
                for table, prefix in [("TB_PROD_GRUPO", "PGRU"), ("TB_PROD_MARCA", "PMAR"), ("TB_PROD_SUBGRUPO", "PSGR"), ("TB_PLANO_CONTA", "PLC")]:
                    sync(table, [{prefix + "_ID": str(c), prefix + "_EMPRESA": str(c), prefix + "_DESCRICAO": f"Cadastro {tenant} {c}"} for c in [1, 2]])
                for table, prefix in [("TB_RECEBIMENTO", "REC"), ("TB_PAGAMENTO", "PAG")]:
                    sync(table, [{prefix + "_ID": "1", prefix + "_EMPRESA": str(c), prefix + "_VALOR": c * 100,
                                  prefix + "_DT_VENCIMENTO": "2026-10-16", prefix + "_ABERTO": "S"} for c in [1, 2]])
                sync("TB_FECHAMENTO_CAIXA", [{"FCX_EMPRESA": "1", "FCX_ID": "55", "FCX_VALOR_TOTAL": 777, "FCX_VALOR_DIFERENCA": -17}])
                sync("TB_PEDIDO_VENDA", [{"PEV_EMPRESA": str(c), "PEV_ID": str(i), "PEV_FECHAMENTO": closing,
                     "PEV_VALOR_TOTAL": c * 50, "PEV_STATUS": "CODIGO_DESCONHECIDO",
                     "PEV_DT_CANCELAMENTO": "2026-10-16" if i == 11 else None} for c, i, closing in [(1, 10, "55"), (1, 11, "55"), (2, 10, "55"), (1, 12, "OUTRO")]])
                sync("TB_PEDIDO_VENDA_ITEM", [{"PEVI_EMPRESA": str(c), "PEVI_PEDIDO_VENDA": "10", "PEVI_SEQUENCIA": str(i), "PEVI_PRODUTO": "1",
                     "PEVI_DESCRICAO": f"Item {i}", "PEVI_QUANTIDADE": i, "PEVI_VALOR_TOTAL": i * 10} for c, i in [(1, 1), (1, 2), (2, 1)]])

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        self.db = Session(self.engine)
        self.service = OperationsService(self.db, "tenant-a")

    def tearDown(self):
        self.db.close()

    def test_product_rows_do_not_multiply_and_stock_is_not_guessed(self):
        result = self.service.list("produtos", 1)
        self.assertEqual(result["total"], 3)
        rows = {row["codigo"]: row for row in result["rows"]}
        self.assertEqual(rows["1"]["posicoes"], 2)
        self.assertIsNone(rows["1"]["estoque"])
        self.assertEqual(rows["1"]["codigos_barras"], "ABC, DEF")
        self.assertEqual(rows["2"]["estoque"], 0)
        self.assertIsNone(rows["3"]["estoque"])
        self.assertTrue(all("tenant-a" in row["nome"] for row in rows.values()))
        self.assertEqual(self.service.list("produtos", 1, search="DEF")["total"], 1)

    def test_stock_detail_preserves_local_and_variation(self):
        positions = self.service.detail("produtos", 1, "1")["stock_positions"]
        self.assertEqual([(row["local"], row["variacao"], row["quantidade"]) for row in positions], [("1", "0", 5), ("1", "1", 7)])
        with self.assertRaises(LookupError):
            self.service.detail("produtos", 2, "1")

    def test_lookups_respect_company_and_tenant(self):
        for resource in ["grupos", "marcas", "subgrupos", "plano-contas"]:
            with self.subTest(resource=resource):
                self.assertEqual(self.service.list(resource, 1)["rows"][0]["nome"], "Cadastro tenant-a 1")
                self.assertEqual(self.service.list(resource, 2)["rows"][0]["nome"], "Cadastro tenant-a 2")
                self.assertEqual(self.service.list(resource, 3)["total"], 0)

    def test_cash_orders_are_scoped_and_repeated_products_preserved(self):
        detail = self.service.detail("fechamentos", 1, "55")
        self.assertEqual({row["pedido"] for row in detail["cash_orders"]}, {"10", "11"})
        self.assertEqual([row["sequencia"] for row in detail["cash_order_products"]], ["1", "2"])
        self.assertEqual([row["pedido"] for row in detail["cash_cancellations"]], ["11"])
        self.assertTrue(all(row["status"] == "CODIGO_DESCONHECIDO" for row in detail["cash_orders"]))
        self.assertEqual(detail["cash_summary"]["total_registrado"], 777)
        self.assertEqual(detail["cash_summary"]["diferenca"], -17)
        self.assertFalse(detail["cash_items_available"])

    def test_title_ids_do_not_overwrite_between_companies_and_nominal_is_not_balance(self):
        for resource in ["receber", "pagar"]:
            self.assertEqual(self.service.list(resource, 1)["rows"][0]["original"], 100)
            self.assertEqual(self.service.list(resource, 2)["rows"][0]["original"], 200)
            self.assertIsNone(self.service.list(resource, 1)["rows"][0]["saldo"])
        result = self.service.forecast(1, date(2026, 10, 16), date(2026, 10, 16))
        self.assertFalse(result["available"])
        self.assertEqual(result["summary"], {})

    def test_mixed_payload_cannot_fall_back_to_collapsing_stock_key(self):
        result = SyncService._sync_generic_table(self.db, "tenant-a", "TB_PRODUTO_ESTOQUE", [
            {"PRDE_PRODUTO": "4", "PRDE_EMPRESA": "1", "PRDE_ESTOQUE": 999},
            {"PRDE_PRODUTO": "4", "PRDE_EMPRESA": "1", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "0", "PRDE_ESTOQUE": 1},
            {"PRDE_PRODUTO": "4", "PRDE_EMPRESA": "1", "PRDE_LOCAL": "1", "PRDE_VARIACAO": "1", "PRDE_ESTOQUE": 2},
        ])
        self.assertEqual(result["ignored_reasons"], {"incomplete_primary_key": 1})
        self.assertEqual(result["inserted"], 2)
        self.assertIn("PRDE_VARIACAO", result["pk_columns"])

    def test_legacy_stock_indicators_report_unavailable_instead_of_summing_positions(self):
        service = DashboardEstoqueService()
        repo = service.repository
        with patch("app.services.erp_query_service.SessionLocal", sessionmaker(self.engine)), \
             patch.object(repo.erp, "_is_saas_mode", return_value=True), \
             patch.object(repo.erp, "_get_tenant_id", return_value="tenant-a"), \
             patch.object(repo, "get_resumo_produtos", return_value={"total": 3, "ativos": 3, "inativos": 0}), \
             patch.object(repo, "get_compras_periodo", return_value={"quantidade": 0, "valor": 0}), \
             patch.object(repo, "get_valores_estoque") as values:
            self.assertTrue(stock_requires_consolidation(repo, 1))
            self.assertFalse(stock_requires_consolidation(repo, 2))
            self.assertTrue(stock_requires_consolidation(repo, 3))
            result = service.get_dashboard_estoque(1)
            values.assert_not_called()
            self.assertFalse(result["estoqueDisponivel"])
            self.assertEqual(result["valores"], {"custoTotal": None, "vendaTotal": None})
            self.assertIsNone(result["alertas"]["total"])
        finance = DashboardFinanceiroRepository()
        with patch("app.services.erp_query_service.SessionLocal", sessionmaker(self.engine)), \
             patch.object(finance.erp, "_is_saas_mode", return_value=True), \
             patch.object(finance.erp, "_get_tenant_id", return_value="tenant-a"):
            self.assertEqual(finance.get_estoque_critico(1), [])
            self.assertTrue(finance.stock_requires_rule)
