import unittest
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError

from app.routes.erp_commands import AckInput, CommandInput, administrator
from app.routes.operations import service_for, spreadsheet_value
from app.services.erp_command_service import same_previous_value, validate_payload


class ErpCommandValidationTests(unittest.TestCase):
    def test_only_catalog_fields_can_be_submitted(self):
        for payload in ({"tenant_id": "other"}, {"codigo": "1"}, {"sql": "UPDATE TB_PESSOA"}, {}):
            with self.assertRaises(ValueError):
                validate_payload("clientes", "update", payload)
        with self.assertRaises(ValueError):
            validate_payload("receber", "update", {"nome": "Título"})

    def test_create_requires_nonempty_description(self):
        for payload in ({"email": "a@example.invalid"}, {"nome": "  "}, {"nome": None}):
            with self.assertRaises(ValueError):
                validate_payload("clientes", "create", payload)
        self.assertEqual(validate_payload("clientes", "create", {"nome": " Cliente "}), {"nome": "Cliente"})

    def test_amounts_reject_nonfinite_negative_and_oversized_values(self):
        for value in ("NaN", "Infinity", "-1", "1000000000000", "bad"):
            with self.assertRaises(ValueError):
                validate_payload("produtos", "update", {"venda": value})
        self.assertEqual(validate_payload("produtos", "update", {"venda": "9.90"}), {"venda": "9.90"})

    def test_regular_users_cannot_write_and_payloads_are_bounded(self):
        with self.assertRaises(HTTPException) as error:
            administrator({"role": "sales"})
        self.assertEqual(error.exception.status_code, 403)
        with self.assertRaises(ValueError):
            validate_payload("clientes", "update", {"nome": "a" * 251})
        with self.assertRaises(ValidationError):
            CommandInput.model_validate({"empresa_id": 1, "action": "delete", "payload": {}})
        with self.assertRaises(ValidationError):
            AckInput.model_validate({"cnpj": "0", "lease_token": "bad", "status": "applied", "message": ""})

    def test_exports_neutralize_formulas_but_preserve_numbers(self):
        for value in ("=SUM(1,1)", " @command", "+12", "-12"):
            self.assertEqual(spreadsheet_value(value), "'" + value)
        self.assertEqual(spreadsheet_value(-12), -12)
        self.assertEqual(spreadsheet_value("Cliente"), "Cliente")

    def test_financial_queries_require_finance_permission(self):
        for resource in ("receber", "pagar", "fechamentos", "cheques", "sangrias"):
            with self.assertRaises(HTTPException) as error:
                service_for(resource, None, {"role": "sales"})
            self.assertEqual(error.exception.status_code, 403)

    def test_conflict_check_compares_decimal_values_without_float_rounding_errors(self):
        self.assertTrue(same_previous_value(Decimal("9.9000"), 9.9, "number"))
        self.assertFalse(same_previous_value(Decimal("9.9000"), 9.8, "number"))
        self.assertFalse(same_previous_value(None, "None", "text"))
        self.assertTrue(same_previous_value(None, None, "text"))
