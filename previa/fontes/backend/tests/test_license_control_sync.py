import logging
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

os.environ.setdefault("LICENSE_CONTROL_INTEGRATION_TOKEN", "test-shared-token")

from fastapi.testclient import TestClient

from app.database.connection import get_db
from app.main import app
from app.core import config
from app.services.license_control_batch_sync_service import (
    normalize_cnpj,
    sync_license_control_batch,
)


def canonical_payload(**overrides):
    payload = {
        "tenant_id": "tenant-test-001",
        "company_id": "company-test-001",
        "empresa": "Empresa Teste LMD Ltda",
        "nome_fantasia": "Empresa Teste LMD",
        "cnpj": "00.000.000/0001-00",
        "produto": "PIGO",
        "status": "ACTIVE",
        "validade": None,
        "ativo": True,
        "updated_at": "2026-07-19T15:00:00.000Z",
    }
    payload.update(overrides)
    return payload


class FakeRepository:
    tenants = {}
    companies = {}
    logs = []

    def __init__(self, _db):
        pass

    def find_tenant(self, external_tenant_id, cnpj):
        return self.tenants.get(external_tenant_id) or next(
            (row for row in self.tenants.values() if row["cnpj"] == cnpj), None
        )

    def find_company(self, external_company_id, cnpj):
        return self.companies.get(external_company_id) or next(
            (row for row in self.companies.values() if row["cnpj"] == cnpj), None
        )

    def upsert_company(self, item, existing_id):
        row = {
            "id": existing_id or item["external_company_id"],
            "external_company_id": item["external_company_id"],
            "cnpj": item["cnpj"],
        }
        self.companies[item["external_company_id"]] = row
        return row

    def upsert_tenant(self, item, existing_id):
        row = {
            "id": existing_id or item["external_tenant_id"],
            "external_tenant_id": item["external_tenant_id"],
            "cnpj": item["cnpj"],
            "has_pigo_access": item["has_pigo_access"],
            "validade": item["validade"],
        }
        self.tenants[item["external_tenant_id"]] = row
        return row

    def write_sync_log(self, values):
        self.logs.append(values)


class FakeNested:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeSession:
    def begin_nested(self):
        return FakeNested()

    def commit(self):
        pass

    def rollback(self):
        pass


class LicenseControlServiceTests(unittest.TestCase):
    def setUp(self):
        FakeRepository.tenants = {}
        FakeRepository.companies = {}
        FakeRepository.logs = []
        self.db = FakeSession()
        self.repository_patch = patch(
            "app.services.license_control_batch_sync_service.LicenseControlRepository",
            FakeRepository,
        )
        self.repository_patch.start()

    def tearDown(self):
        self.repository_patch.stop()

    def sync(self, items):
        return sync_license_control_batch(self.db, items, "127.0.0.1")

    def test_create_update_company_and_tenant_are_idempotent(self):
        first = self.sync([canonical_payload()])
        second = self.sync(
            [canonical_payload(cnpj="00000000000100", nome_fantasia="Novo Nome")]
        )
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["updated"], 1)
        self.assertEqual(len(FakeRepository.tenants), 1)
        self.assertEqual(len(FakeRepository.companies), 1)

    def test_inactive_disables_without_deleting(self):
        self.sync([canonical_payload()])
        result = self.sync([canonical_payload(ativo=False)])
        self.assertEqual(result["disabled"], 1)
        self.assertFalse(FakeRepository.tenants["tenant-test-001"]["has_pigo_access"])

    def test_null_expiration_and_invalid_record(self):
        valid = self.sync([canonical_payload(validade=None)])
        invalid = self.sync([canonical_payload(cnpj="123")])
        self.assertTrue(valid["success"])
        self.assertEqual(len(invalid["errors"]), 1)
        self.assertEqual(invalid["errors"][0]["field"], "cnpj")
        self.assertEqual(invalid["errors"][0]["code"], "INVALID_CNPJ")

    def test_validation_errors_are_detailed(self):
        cases = [
            ({k: v for k, v in canonical_payload().items() if k != "tenant_id"}, "tenant_id", "MISSING_TENANT_ID"),
            ({k: v for k, v in canonical_payload().items() if k != "company_id"}, "company_id", "MISSING_COMPANY_ID"),
            (canonical_payload(empresa="  "), "empresa", "EMPTY_EMPRESA"),
            (canonical_payload(cnpj="123"), "cnpj", "INVALID_CNPJ"),
            (canonical_payload(updated_at="not-a-date"), "updated_at", "INVALID_UPDATED_AT"),
            (canonical_payload(validade="not-a-date"), "validade", "INVALID_VALIDADE"),
            (canonical_payload(status="unexpected"), "status", "INVALID_STATUS"),
            (canonical_payload(produto="OUTRO"), "produto", "INVALID_PRODUCT"),
        ]

        for payload, field, code in cases:
            with self.subTest(field=field, code=code):
                result = self.sync([payload])
                self.assertFalse(result["success"])
                self.assertEqual(result["errors"][0]["field"], field)
                self.assertEqual(result["errors"][0]["code"], code)
                self.assertNotIn("token", str(result["errors"]).lower())

    def test_tenant_cnpj_conflict_is_detailed(self):
        self.sync([canonical_payload()])
        result = self.sync(
            [canonical_payload(tenant_id="different-tenant", company_id="different-company")]
        )
        error = result["errors"][0]
        self.assertEqual(error["field"], "tenant_id")
        self.assertEqual(error["code"], "TENANT_CNPJ_CONFLICT")

    def test_company_cnpj_conflict_is_detailed(self):
        self.sync([canonical_payload()])
        result = self.sync([canonical_payload(company_id="different-company")])
        error = result["errors"][0]
        self.assertEqual(error["field"], "company_id")
        self.assertEqual(error["code"], "COMPANY_CNPJ_CONFLICT")

    def test_product_name_accepts_punctuation_without_changing_contract(self):
        result = self.sync([canonical_payload(produto="P.I.G.O")])
        self.assertTrue(result["success"])

    def test_partial_errors_do_not_block_valid_records(self):
        result = self.sync(
            [canonical_payload(), canonical_payload(tenant_id="bad", cnpj="123")]
        )
        self.assertEqual(result["received"], 2)
        self.assertEqual(result["created"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertFalse(result["success"])

    def test_response_has_all_metrics(self):
        result = self.sync([canonical_payload()])
        expected = {
            "success", "received", "created", "updated", "disabled",
            "ignored", "errors", "processing_time", "action",
        }
        self.assertEqual(set(result), expected)

    def test_cnpj_normalization(self):
        self.assertEqual(normalize_cnpj("00.000.000/0001-00"), "00000000000100")


class LicenseControlRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = lambda: MagicMock()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def test_missing_and_invalid_token_return_401(self):
        self.assertEqual(
            self.client.post(
                "/api/internal/license-control/tenants/sync",
                json=canonical_payload(),
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/api/internal/license-control/tenants/sync",
                headers={"Authorization": "Bearer wrong"},
                json=canonical_payload(),
            ).status_code,
            401,
        )

    def test_missing_server_configuration_returns_503(self):
        current = config.LICENSE_CONTROL_INTEGRATION_TOKEN
        config.LICENSE_CONTROL_INTEGRATION_TOKEN = ""
        try:
            response = self.client.post(
                "/api/internal/license-control/tenants/sync",
                headers={"Authorization": "Bearer test-shared-token"},
                json=canonical_payload(),
            )
            self.assertEqual(response.status_code, 503)
        finally:
            config.LICENSE_CONTROL_INTEGRATION_TOKEN = current

    @patch("app.routes.internal_license_control.sync_license_control_batch")
    def test_direct_contract_and_envelope_with_correct_token(self, sync_mock):
        sync_mock.return_value = {
            "success": True, "received": 1, "created": 1, "updated": 0,
            "disabled": 0, "ignored": 0, "errors": [],
            "processing_time": 1, "action": "created",
        }
        headers = {"Authorization": "Bearer test-shared-token"}
        direct = self.client.post(
            "/api/internal/license-control/tenants/sync",
            headers=headers,
            json=canonical_payload(),
        )
        envelope = self.client.post(
            "/api/internal/license-control/tenants/sync",
            headers=headers,
            json={"tenants": [canonical_payload()], "snapshot": True},
        )
        self.assertEqual(direct.status_code, 200)
        self.assertEqual(envelope.status_code, 200)
        self.assertEqual(sync_mock.call_args.kwargs["raw_items"][0]["tenant_id"], "tenant-test-001")

    def test_token_is_not_logged(self):
        with self.assertLogs(level=logging.INFO) as captured:
            self.client.post(
                "/api/internal/license-control/tenants/sync",
                headers={"Authorization": "Bearer wrong-secret-value"},
                json=canonical_payload(),
            )
        self.assertNotIn("wrong-secret-value", "\n".join(captured.output))

    @patch("app.routes.internal_license_control.sync_license_control_batch")
    def test_integration_token_bypasses_dashboard_jwt_logging(self, sync_mock):
        sync_mock.return_value = {
            "success": True, "received": 1, "created": 1, "updated": 0,
            "disabled": 0, "ignored": 0, "errors": [],
            "processing_time": 1, "action": "created",
        }
        headers = {"Authorization": "Bearer test-shared-token"}
        with (
            patch(
                "app.middlewares.request_logging.decode_access_token",
                side_effect=AssertionError("JWT comum nao deve ser chamado"),
            ),
            patch(
                "app.main.decode_access_token",
                side_effect=AssertionError("JWT comum nao deve ser chamado"),
            ),
            self.assertLogs("pigo.request", level=logging.INFO) as captured,
        ):
            response = self.client.post(
                "/api/internal/license-control/tenants/sync",
                headers=headers,
                json=canonical_payload(),
            )

        logs = "\n".join(captured.output)
        self.assertEqual(response.status_code, 200)
        self.assertIn("auth_type=integration", logs)
        self.assertIn("integration_source=license-control", logs)
        self.assertNotIn("sub=invalid-token", logs)
        self.assertNotIn("test-shared-token", logs)

    @patch("app.routes.internal_license_control.sync_license_control_batch")
    def test_invalid_payload_returns_top_level_detailed_400(self, sync_mock):
        sync_mock.return_value = {
            "success": False,
            "received": 1,
            "created": 0,
            "updated": 0,
            "disabled": 0,
            "ignored": 0,
            "errors": [
                {
                    "tenant_id": "tenant-test-001",
                    "company_id": "company-test-001",
                    "field": "cnpj",
                    "code": "INVALID_CNPJ",
                    "message": "CNPJ invalido.",
                    "trace_id": "trace-test",
                }
            ],
            "processing_time": 1,
        }
        response = self.client.post(
            "/api/internal/license-control/tenants/sync",
            headers={"Authorization": "Bearer test-shared-token"},
            json=canonical_payload(cnpj="123"),
        )
        body = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("detail", body)
        self.assertEqual(body["errors"][0]["code"], "INVALID_CNPJ")

    @patch("app.routes.internal_license_control.sync_license_control_batch")
    def test_partial_batch_keeps_processing_and_returns_200(self, sync_mock):
        sync_mock.return_value = {
            "success": False,
            "received": 2,
            "created": 1,
            "updated": 0,
            "disabled": 0,
            "ignored": 0,
            "errors": [
                {
                    "tenant_id": "bad",
                    "company_id": "bad",
                    "field": "cnpj",
                    "code": "INVALID_CNPJ",
                    "message": "CNPJ invalido.",
                }
            ],
            "processing_time": 1,
        }
        response = self.client.post(
            "/api/internal/license-control/tenants/sync",
            headers={"Authorization": "Bearer test-shared-token"},
            json={"tenants": [canonical_payload(), canonical_payload(cnpj="123")]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 1)

    @patch("app.routes.internal_license_control.sync_license_control_batch")
    def test_legacy_route_uses_same_integration_token(self, sync_mock):
        sync_mock.return_value = {
            "success": True, "received": 1, "created": 1, "updated": 0,
            "disabled": 0, "ignored": 0, "errors": [],
            "processing_time": 1, "action": "created",
        }
        invalid = self.client.post(
            "/api/internal/license-control/sync-tenant",
            headers={"Authorization": "Bearer wrong"},
            json=canonical_payload(),
        )
        valid = self.client.post(
            "/api/internal/license-control/sync-tenant",
            headers={"Authorization": "Bearer test-shared-token"},
            json=canonical_payload(),
        )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(valid.status_code, 200)


if __name__ == "__main__":
    unittest.main()
