import unittest

from app.services.sync_service import SyncService


class PhysicalKeyTests(unittest.TestCase):
    def test_stock_keeps_local_and_variation(self):
        self.assertEqual(SyncService._resolve_pk_columns("TB_PRODUTO_ESTOQUE", {
            "PRDE_PRODUTO": 1, "PRDE_EMPRESA": 2, "PRDE_LOCAL": 3, "PRDE_VARIACAO": 4}),
            ["PRDE_PRODUTO", "PRDE_EMPRESA", "PRDE_LOCAL", "PRDE_VARIACAO"])
        with self.assertRaises(ValueError):
            SyncService._resolve_pk_columns("TB_PRODUTO_ESTOQUE", {
                "PRDE_PRODUTO": 1, "PRDE_EMPRESA": 2, "PRDE_LOCAL": 3})

    def test_financial_and_order_ids_are_scoped_by_company(self):
        for table, prefix in [("TB_PEDIDO_VENDA", "PEV"), ("TB_RECEBIMENTO", "REC"), ("TB_PAGAMENTO", "PAG")]:
            with self.subTest(table=table):
                self.assertEqual(SyncService._resolve_pk_columns(table, {prefix + "_ID": 1, prefix + "_EMPRESA": 2}),
                                 [prefix + "_EMPRESA", prefix + "_ID"])

    def test_repeated_products_keep_distinct_physical_line_keys(self):
        keys = SyncService._resolve_pk_columns("TB_PEDIDO_VENDA_ITEM", {
            "PEVI_EMPRESA": 1, "PEVI_PEDIDO_VENDA": 10, "PEVI_SEQUENCIA": 2, "PEVI_PRODUTO": 123})
        self.assertEqual(keys, ["PEVI_EMPRESA", "PEVI_PEDIDO_VENDA", "PEVI_SEQUENCIA"])

    def test_payment_lines_do_not_collapse_same_currency(self):
        keys = SyncService._resolve_pk_columns("TB_PEDIDO_VENDA_FIN", {
            "PEVF_EMPRESA": 1, "PEVF_PEDIDO_VENDA": 10, "PEVF_SEQUENCIA": 2, "PEVF_ESPECIE_MOEDA": 1})
        self.assertEqual(keys, ["PEVF_EMPRESA", "PEVF_PEDIDO_VENDA", "PEVF_SEQUENCIA"])

    def test_cash_items_do_not_use_artificial_generic_ids(self):
        keys = SyncService._resolve_pk_columns("TB_FECHAMENTO_CAIXA_ITEM", {
            "FCXI_EMPRESA": 1, "FCXI_FECHAMENTO": 10, "FCXI_SEQUENCIA": 2})
        self.assertEqual(keys, ["FCXI_EMPRESA", "FCXI_FECHAMENTO", "FCXI_SEQUENCIA"])
        with self.assertRaises(ValueError):
            SyncService._resolve_pk_columns("TB_FECHAMENTO_CAIXA_ITEM", {"FCXI_EMPRESA": 1, "FCXI_FECHAMENTO": 10})

    def test_legacy_agent_contract_is_recognized_when_complete(self):
        self.assertEqual(SyncService._resolve_pk_columns("TB_PEDIDO_VENDA_ITEM", {
            "PEVI_PEDIDO_VENDA": 1, "PEVI_EMPRESA": 1, "PEVI_PRODUTO": 2}),
            ["PEVI_PEDIDO_VENDA", "PEVI_EMPRESA", "PEVI_PRODUTO"])
