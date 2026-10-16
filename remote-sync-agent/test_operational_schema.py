"""Confirmed ERP vocabulary, without reading ERP records or guessing codes."""
import json
import tempfile
import unittest
from pathlib import Path

from operational_sync import fetch_operational


class Schema:
    def __init__(self, columns):
        self.columns = columns

    def has_table(self, table):
        return table in self.columns

    def has_column(self, table, column):
        return column in self.columns.get(table, set())


class OperationalSchemaTests(unittest.TestCase):
    def fetch(self, schema, path=""):
        queries = {}
        def execute(conn, sql, params, table):
            queries[table] = sql
            return []
        list(fetch_operational(None, Schema(schema), path, execute))
        return queries

    def test_real_names_map_cheques_subgroups_and_plan(self):
        queries = self.fetch({
            "TB_CHEQUE_EMITIDO": {"CHE_ID", "CHE_EMPRESA", "CHE_NUMERO_CHEQUE", "CHE_PESSOA", "CHE_NOMINAL", "CHE_VALOR_CHEQUE", "CHE_STATUS"},
            "TB_PROD_SUB_GRUPO": {"PSGR_ID", "PSGR_EMPRESA", "PSGR_DESCRICAO"},
            "TB_PLANO_CONTA": {"PLC_ID", "PLC_EMPRESA", "PLC_PAI", "PLC_TIPO_CONTA"},
        })
        self.assertIn("CHE_NUMERO_CHEQUE AS CHQ_NUMERO", queries["TB_CHEQUE_EMITIDO"])
        self.assertIn("CHE_PESSOA AS CHQ_PESSOA", queries["TB_CHEQUE_EMITIDO"])
        self.assertNotIn("CHQ_FORNECEDOR", queries["TB_CHEQUE_EMITIDO"])
        self.assertIn("PSGR_EMPRESA AS PSGR_EMPRESA", queries["TB_PROD_SUB_GRUPO"])
        self.assertIn("PLC_PAI AS PLC_CONTA_PAI", queries["TB_PLANO_CONTA"])
        self.assertIn("PLC_TIPO_CONTA AS PLC_TIPO", queries["TB_PLANO_CONTA"])
        self.assertNotIn("PLC_DRE", queries["TB_PLANO_CONTA"])

    def test_legacy_canonical_fields_keep_precedence(self):
        query = self.fetch({"TB_CHEQUE_EMITIDO": {"CHQ_ID", "CHQ_EMPRESA", "CHQ_NUMERO", "CHE_NUMERO_CHEQUE"}})["TB_CHEQUE_EMITIDO"]
        self.assertIn("CHQ_NUMERO AS CHQ_NUMERO", query)
        self.assertNotIn("CHE_NUMERO_CHEQUE", query)

    def test_explicit_mapping_overrides_confirmed_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text(json.dumps({"TB_PROD_SUBGRUPO": {"table": "ERP_SUB", "fields": {"PSGR_ID": "SUB_ID"}}}))
            queries = self.fetch({"ERP_SUB": {"SUB_ID"}, "TB_PROD_SUB_GRUPO": {"PSGR_ID"}}, str(path))
            self.assertIn("SUB_ID AS PSGR_ID", queries["ERP_SUB"])
            self.assertNotIn("TB_PROD_SUB_GRUPO", queries)
