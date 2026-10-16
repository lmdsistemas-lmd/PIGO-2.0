import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import agent
from credential_store import CredentialStore, CredentialStoreError
from firebird_provider import create_provider
from resolved_config import ResolvedAgentConfig


def response(status, payload=None):
    result = Mock()
    result.status_code = status
    result.content = b"{}"
    result.headers = {"X-Trace-Id": "request-test"}
    result.json.return_value = payload or {}
    return result


class RemoteSyncAgentTests(unittest.TestCase):
    def test_sales_item_contract_uses_physical_composite_key_without_artificial_id(self):
        spec = next(item for item in agent.GENERIC_TABLES if item["table"] == "TB_PEDIDO_VENDA_ITEM")
        self.assertNotIn("PEVI_ID", spec["columns"])
        self.assertIn("PEVI_SEQUENCIA", spec["columns"])
        self.assertEqual(
            spec["required_columns"],
            ["PEVI_EMPRESA", "PEVI_PEDIDO_VENDA", "PEVI_SEQUENCIA"],
        )
        self.assertTrue({
            "PEVI_UN_VENDA", "PEVI_VALOR_DESCONTO", "PEVI_VALOR_ACRESCIMO",
            "PEVI_VALOR_FRETE", "PEVI_DT_LANCAMENTO",
        }.issubset(spec["columns"]))

    def test_sales_payment_contract_uses_physical_composite_key_without_artificial_id(self):
        spec = next(item for item in agent.GENERIC_TABLES if item["table"] == "TB_PEDIDO_VENDA_FIN")
        self.assertNotIn("PEVF_ID", spec["columns"])
        self.assertIn("PEVF_SEQUENCIA", spec["columns"])
        self.assertEqual(
            spec["required_columns"],
            ["PEVF_EMPRESA", "PEVF_PEDIDO_VENDA", "PEVF_SEQUENCIA"],
        )

    def test_cash_register_missing_table_is_skipped_without_error(self):
        schema = Mock()
        schema.has_table.return_value = False
        spec = next(item for item in agent.GENERIC_TABLES if item["table"] == "TB_FECHAMENTO_CAIXA")
        self.assertEqual(agent.fetch_generic_table(Mock(), schema, spec, "2025-01-01", True), [])

    def test_cash_register_missing_required_field_is_skipped(self):
        schema = Mock()
        schema.has_table.return_value = True
        schema.has_column.side_effect = lambda table, column: column != "FCX_ID"
        spec = next(item for item in agent.GENERIC_TABLES if item["table"] == "TB_FECHAMENTO_CAIXA")
        self.assertEqual(agent.fetch_generic_table(Mock(), schema, spec, "2025-01-01", True), [])

    def test_cash_register_diagnostic_reports_not_available_without_tables(self):
        schema = Mock()
        schema.has_table.return_value = False
        result = agent.diagnose_cash_register_compatibility(Mock(), schema)
        self.assertEqual(result["status"], "NOT_AVAILABLE")
        self.assertEqual(len(result["tables"]), 4)
        self.assertTrue(all(not item["found"] for item in result["tables"]))

    def test_cash_register_fixture_is_serialized_and_sent_without_recalculation(self):
        fixture = {
            "FCX_EMPRESA": 1,
            "erp_company_id": 1,
            "FCX_ID": 365,
            "FCX_VALOR_TOTAL": 17281.60,
            "FCX_VALOR_CAIXA": 168.43,
            "FCX_VALOR_DIFERENCA": -16650.05,
            "FCX_VALOR_TROCO": 61.93,
            "FCX_VALOR_SUPRIMENTO": 200.00,
        }
        confirmed = response(200, {"success": True, "tenant_id": "tenant-1", "received": 1})
        with (
            patch.object(agent, "COMPANY_CNPJ", "12345678000199"),
            patch.object(agent, "active_api_token", return_value="token"),
            patch.object(agent, "remote_sync_headers", return_value={"Authorization": "masked"}),
            patch.object(agent.requests, "post", return_value=confirmed) as post,
        ):
            self.assertEqual(agent.send_to_dashboard("TB_FECHAMENTO_CAIXA", [fixture]), agent.SEND_SUCCESS)
        self.assertEqual(post.call_args.kwargs["json"]["content"][0], fixture)

    def test_cash_register_specs_use_explicit_company_alias_and_safe_whitelists(self):
        specs = {spec["table"]: spec for spec in agent.GENERIC_TABLES}
        expected = {
            "TB_FECHAMENTO_CAIXA": "FCX_EMPRESA",
            "TB_FECHAMENTO_CAIXA_ITEM": "FCXI_EMPRESA",
            "TB_FECHAMENTO_CAIXA_VENDA": "FCXV_EMPRESA",
            "TB_MOVIMENTO_CAIXA": "MOV_EMPRESA",
        }

        for table, company_column in expected.items():
            self.assertEqual(specs[table]["erp_company_column"], company_column)
            self.assertIn(company_column, specs[table]["columns"])
            self.assertNotIn("*", specs[table]["columns"])

    def test_cash_reference_projection_does_not_add_integration_secrets(self):
        specs = {spec["table"]: spec for spec in agent.GENERIC_TABLES}
        species_columns = set(specs["TB_ESPECIE_MOEDA"]["columns"])
        self.assertFalse({"ESP_SECRET_KEY", "ESP_SERIAL_STONE"} & species_columns)
        self.assertIn("USU_STATUS", specs["TB_USUARIO"]["columns"])

    def test_cash_register_incremental_specs_reprocess_mutable_closings(self):
        specs = {spec["table"]: spec for spec in agent.GENERIC_TABLES}
        closing_where = specs["TB_FECHAMENTO_CAIXA"]["where"]
        self.assertIn("FCX_DT_LANCAMENTO >= ?", closing_where)
        self.assertIn("FCX_DT_LANCAMENTO IS NULL", closing_where)
        self.assertIn("FCX_DT_FECHAMENTO IS NULL", closing_where)

    def test_stale_owner_lock_is_replaced_after_os_lock_is_acquired(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(agent, "DATA_DIR", Path(directory)):
            lock = Path(directory) / "agent.lock"
            lock.write_text("999999", encoding="ascii")
            with agent.single_agent_lock():
                pass
            self.assertEqual(lock.read_text(encoding="ascii"), str(os.getpid()))

    def test_activation_timeout_is_retryable_and_does_not_replace_token(self):
        store = Mock()
        store.installation_id.return_value = "installation-test"
        store.machine_fingerprint.return_value = "fingerprint-test"
        with (
            patch.object(agent, "require_remote_env"),
            patch.object(agent, "LICENSE_API_KEY", "configured"),
            patch.object(agent, "COMPANY_CNPJ", "12345678000199"),
            patch.object(agent, "CREDENTIAL_STORE", store),
            patch.object(agent.requests, "post", side_effect=agent.requests.ReadTimeout()),
        ):
            result = agent.activate_remote(reactivate=True)
        self.assertEqual(result["code"], "ACTIVATION_REMOTE_TIMEOUT")
        self.assertTrue(result["retryable"])
        store.save_token.assert_not_called()

    def test_existing_token_health_returns_structured_authenticated_result(self):
        public = response(200, {"status": "ok"})
        authenticated = response(200, {"authenticated": True, "tenant_id": "tenant-1"})
        with (
            patch.object(agent, "require_remote_env"),
            patch.object(agent, "active_api_token", return_value="existing-token"),
            patch.object(agent, "remote_sync_headers", return_value={"Authorization": "masked"}),
            patch.object(agent.requests, "get", side_effect=[public, authenticated]),
        ):
            result = agent.diagnose_remote_result()
        self.assertTrue(result["success"])
        self.assertTrue(result["authenticated"])
        self.assertTrue(result["tenant_resolved"])
        self.assertEqual(result["code"], "REMOTE_TOKEN_VALID")

    def test_existing_token_health_timeout_does_not_request_reactivation(self):
        with (
            patch.object(agent, "require_remote_env"),
            patch.object(agent, "active_api_token", return_value="existing-token"),
            patch.object(agent.requests, "get", side_effect=agent.requests.ReadTimeout()),
        ):
            result = agent.diagnose_remote_result()
        self.assertFalse(result["success"])
        self.assertTrue(result["retryable"])
        self.assertEqual(result["code"], "REMOTE_HEALTH_TIMEOUT")

    def test_activation_returns_success_after_token_is_reloaded_from_vault(self):
        store = Mock()
        store.installation_id.return_value = "installation-test"
        store.machine_fingerprint.return_value = "fingerprint-test"
        store.has_token.return_value = True
        api_response = response(200, {
            "success": True,
            "code": "AGENT_ACTIVATED",
            "remote_sync_token": "received-secret",
            "request_id": "request-test",
        })
        with (
            patch.object(agent, "require_remote_env"),
            patch.object(agent, "LICENSE_API_KEY", "configured"),
            patch.object(agent, "COMPANY_CNPJ", "12345678000199"),
            patch.object(agent, "CREDENTIAL_STORE", store),
            patch.object(agent.requests, "post", return_value=api_response),
        ):
            result = agent.activate_remote()
        self.assertTrue(result["success"])
        self.assertTrue(result["token_saved"])
        self.assertEqual(result["api_status"], 200)
        store.save_token.assert_called_once_with("received-secret")

    def test_activation_returns_structured_api_failure(self):
        store = Mock()
        store.installation_id.return_value = "installation-test"
        store.machine_fingerprint.return_value = "fingerprint-test"
        denied = response(403, {
            "success": False,
            "code": "LICENSE_DENIED",
            "message": "Licença não autorizada.",
            "request_id": "request-test",
        })
        with (
            patch.object(agent, "require_remote_env"),
            patch.object(agent, "LICENSE_API_KEY", "configured"),
            patch.object(agent, "COMPANY_CNPJ", "12345678000199"),
            patch.object(agent, "CREDENTIAL_STORE", store),
            patch.object(agent.requests, "post", return_value=denied),
        ):
            result = agent.activate_remote()
        self.assertFalse(result["success"])
        self.assertEqual(result["code"], "LICENSE_DENIED")
        self.assertEqual(result["api_status"], 403)

    def test_desktop_resolver_reads_firebird_password_from_shared_store(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"PIGO_ALLOW_INSECURE_CREDENTIAL_STORE": "true"}):
            root = Path(directory); config = root / "config.json"; env = root / ".env"
            config.write_text('{"firebird":{"host":"server","port":3051,"database":"base.fdb","user":"SYSDBA","charset":"WIN1252","driver":"fdb","architecture":"x86"},"pigo":{"apiBaseUrl":"https://example.test/api","companyCnpj":"12345678000199"}}',encoding="utf-8")
            store = CredentialStore(root / "credentials.dat", root / "installation.json")
            with patch("credential_store.os.name", "posix"):
                store.save_secret("firebird_password", "masterkey-test")
                resolved = ResolvedAgentConfig.resolve(config, env, store)
            self.assertEqual(resolved.mode, "desktop")
            self.assertEqual(resolved.firebird_password, "masterkey-test")
            self.assertEqual(resolved.firebird_settings()["password"], "masterkey-test")

    def test_get_db_connection_delivers_resolved_password_to_provider(self):
        resolved = ResolvedAgentConfig("desktop",Path("config.json"),"https://example.test/api","12345678000199","token","license","server",3050,"base.fdb","SYSDBA","resolved-secret","client.dll","WIN1252","fdb","x86",1)
        provider = Mock(); provider.connect.return_value = "connection"
        with patch.object(agent,"CONFIG",resolved),patch.object(agent,"API_BASE_URL",resolved.api_base_url),patch.object(agent,"COMPANY_CNPJ",resolved.company_cnpj),patch.object(agent,"_firebird_provider",provider):
            self.assertEqual(agent.get_db_connection(),"connection")
        self.assertEqual(provider.connect.call_args.args[0]["password"],"resolved-secret")
    def test_driver_selection_is_explicit(self):
        self.assertEqual(create_provider("fdb").name, "fdb")
        with self.assertRaises(ValueError):
            create_provider("automatic")
    def test_auth_failure_is_permanent_and_is_not_retried(self):
        with patch.object(agent.requests, "post", return_value=response(403)) as post:
            result = agent.send_to_dashboard("TB_EMPRESA", [{"EMP_ID": 1}])

        self.assertEqual(result, agent.SEND_PERMANENT_FAILURE)
        self.assertEqual(post.call_count, 1)

    def test_transient_failure_retries_and_requires_confirmation(self):
        confirmed = response(
            200,
            {"success": True, "tenant_id": "tenant-1", "received": 1},
        )
        with (
            patch.object(agent.requests, "post", side_effect=[response(503), confirmed]) as post,
            patch.object(agent.time, "sleep"),
            patch.object(agent.random, "uniform", return_value=0),
        ):
            result = agent.send_to_dashboard("TB_EMPRESA", [{"EMP_ID": 1}])

        self.assertEqual(result, agent.SEND_SUCCESS)
        self.assertEqual(post.call_count, 2)

    def test_http_200_without_valid_confirmation_is_rejected(self):
        with patch.object(
            agent.requests,
            "post",
            return_value=response(200, {"success": False, "received": 1}),
        ):
            result = agent.send_to_dashboard("TB_EMPRESA", [{"EMP_ID": 1}])

        self.assertEqual(result, agent.SEND_PERMANENT_FAILURE)

    def test_sensitive_values_are_masked(self):
        self.assertEqual(agent.mask_token("super-secret-token"), "(configurado)")
        self.assertEqual(agent.mask_cnpj("16.609.331/0001-63"), "16********63")

    def test_structured_server_error_is_sanitized(self):
        result = response(
            403,
            {
                "success": False,
                "code": "INVALID_API_KEY",
                "message": "Credencial de integracao invalida.",
                "request_id": "request-123",
            },
        )
        self.assertEqual(
            agent.sanitized_api_error(result),
            {
                "code": "INVALID_API_KEY",
                "message": "Credencial de integracao invalida.",
                "request_id": "request-123",
            },
        )

    def test_environment_token_has_priority_for_legacy_installations(self):
        with patch.object(agent, "API_TOKEN", "legacy-token"):
            self.assertEqual(agent.active_api_token(), "legacy-token")

    def test_development_store_persists_installation_and_token(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"PIGO_ALLOW_INSECURE_CREDENTIAL_STORE": "true"}
        ):
            store = CredentialStore(Path(directory) / "credentials.json")
            installation_id = store.installation_id()
            store.save_token("local-token")
            restarted = CredentialStore(Path(directory) / "credentials.json")
            self.assertEqual(restarted.installation_id(), installation_id)
            self.assertEqual(restarted.load_token(), "local-token")
            restarted.clear_token()
            self.assertFalse(restarted.has_token())

    def test_versioned_shared_store_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.dat"
            installation = Path(directory) / "installation.json"
            with patch.dict(os.environ, {"PIGO_ALLOW_INSECURE_CREDENTIAL_STORE": "true"}), patch("credential_store.os.name", "posix"):
                store = CredentialStore(path, installation)
                store.save_secret("license_api_key", "license-test")
                store.save_token("token-test")
                payload = __import__("json").loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["version"], 1)
                self.assertEqual(payload["scope"], "DevelopmentPlaintext")
                self.assertEqual(set(payload["entries"]), {"license_api_key", "remote_sync_token"})
                self.assertEqual(store.load_secret("license_api_key"), "license-test")

    def test_insecure_fallback_must_be_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            with patch.dict(
                os.environ, {"PIGO_ALLOW_INSECURE_CREDENTIAL_STORE": "false"}
            ), patch("credential_store.os.name", "posix"):
                store = CredentialStore(path)
                with self.assertRaises(CredentialStoreError):
                    store.save_token("must-not-be-written")

if __name__ == "__main__":
    unittest.main()
