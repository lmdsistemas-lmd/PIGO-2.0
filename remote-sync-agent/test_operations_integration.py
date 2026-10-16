import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import agent
from owner import AgentOwner
from resolved_config import ResolvedAgentConfig
from writeback import poll_commands


class CurrentAgentIntegrationTests(unittest.TestCase):
    def test_command_poll_preserves_installation_authentication_header(self):
        with patch("writeback.requests.Session") as session:
            post = session.return_value.__enter__.return_value.post
            post.return_value.json.return_value = {"commands": []}
            headers = {"Authorization": "Bearer test", "X-Installation-Id": "installation-test"}
            self.assertFalse(poll_commands(Mock(), lambda path: "https://example.invalid/" + path, "test", "00000000000191", False, "", [], headers=headers))
            self.assertEqual(post.call_args.kwargs["headers"], headers)

    def test_desktop_writeback_settings_do_not_fall_back_to_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"writeback": {"enabled": False, "procedure": "erp_apply", "resources": ["clientes"]}}))
            store = Mock(); store.load_secret.return_value = None
            with patch.dict("os.environ", {"WRITEBACK_ENABLED": "true", "WRITEBACK_PROCEDURE": "OTHER"}):
                config = ResolvedAgentConfig.resolve(path, Path(directory) / ".env", store)
            self.assertFalse(config.writeback_enabled)
            self.assertEqual(config.writeback_procedure, "ERP_APPLY")
            self.assertEqual(config.writeback_resources, ("clientes",))

    def test_export_contains_all_table_columns_without_reading_business_rows(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(agent, "DIAGNOSTIC_DIR", Path(directory)), patch.object(agent, "DIAGNOSTIC_FILE", "schema_diagnostics.json"):
            connection = Mock()
            schema = agent.FirebirdSchema(connection)
            schema.tables = {"TB_PESSOA", "TB_OTHER"}
            schema.columns = {"TB_PESSOA": ["PES_ID"], "TB_OTHER": ["OTHER_ID"]}
            path = schema.write_diagnostics(["TB_PESSOA"])
            exported = json.loads(Path(path).read_text())
            self.assertEqual(exported["columns"]["TB_OTHER"], ["OTHER_ID"])
            connection.cursor.assert_not_called()

    def test_owner_serializes_writeback_and_sync_and_honors_pause(self):
        mutex = threading.Lock(); collisions = []; writes = []; entered = threading.Event()
        def operation(kind):
            if not mutex.acquire(blocking=False): collisions.append(kind); return False
            try:
                if kind == "write": writes.append(time.monotonic()); entered.set()
                time.sleep(.01)
                return False
            finally:
                mutex.release()
        owner = AgentOwner(lambda: operation("sync"), lambda: True, lambda: 60,
                           interval_minutes=60, writeback_callback=lambda: operation("write"), writeback_interval=.02)
        owner.start()
        try:
            self.assertTrue(entered.wait(2))
            owner.submit("pause")
            deadline = time.monotonic() + 2
            while owner.state != "PAUSED" and time.monotonic() < deadline: time.sleep(.005)
            self.assertEqual(owner.state, "PAUSED")
            count = len(writes); time.sleep(.08)
            self.assertEqual(len(writes), count)
            owner.submit("resume"); owner.submit("sync-now")
            deadline = time.monotonic() + 2
            while not owner.last_sync_at and time.monotonic() < deadline: time.sleep(.005)
            self.assertIsNotNone(owner.last_sync_at)
            self.assertFalse(collisions)
        finally:
            owner.submit("shutdown"); owner.worker.join(2)
            self.assertFalse(owner.worker.is_alive())
