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


if __name__ == "__main__":
    unittest.main()
