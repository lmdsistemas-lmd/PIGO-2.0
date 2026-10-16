import json
import unittest
from unittest.mock import Mock
from uuid import uuid4

from writeback import execute_command


class WritebackTests(unittest.TestCase):
    def command(self):
        return {"id": str(uuid4()), "company_erp_id": 1, "resource": "clientes", "action": "create",
                "record_id": None, "payload": {"nome": "Cliente de teste"}, "expected": {}}

    def test_commit_contains_both_erp_write_and_replay_receipt(self):
        conn = Mock(); cursor = conn.cursor.return_value
        cursor.fetchone.side_effect = [None, ("applied", "123", "Confirmado")]
        result = execute_command(conn, "PIGO_APPLY_COMMAND", self.command(), "00000000000191")
        self.assertEqual(result["record_id"], "123")
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(statements[1].startswith("INSERT INTO PIGO_COMMAND_RECEIPT"))
        self.assertTrue(statements[2].startswith("EXECUTE PROCEDURE"))
        self.assertTrue(statements[3].startswith("UPDATE PIGO_COMMAND_RECEIPT"))
        conn.commit.assert_called_once(); conn.rollback.assert_not_called()

    def test_lost_http_ack_reuses_receipt_without_second_erp_write(self):
        conn = Mock(); cursor = conn.cursor.return_value
        command = self.command()
        cursor.fetchone.side_effect = [None, ("applied", "123", "Confirmado")]
        result = execute_command(conn, "PIGO_APPLY_COMMAND", command, "00000000000191")
        digest = cursor.execute.call_args_list[1].args[1][1]
        replay = Mock(); replay.cursor.return_value.fetchone.return_value = (digest, json.dumps(result))
        self.assertEqual(execute_command(replay, "PIGO_APPLY_COMMAND", command, "00000000000191"), result)
        replay.cursor.return_value.execute.assert_called_once(); replay.commit.assert_not_called()

    def test_replay_with_different_payload_does_not_write(self):
        conn = Mock(); conn.cursor.return_value.fetchone.return_value = ("0" * 64, "{}")
        with self.assertRaises(ValueError):
            execute_command(conn, "PIGO_APPLY_COMMAND", self.command(), "00000000000191")
        conn.rollback.assert_called_once(); conn.commit.assert_not_called()

    def test_erp_error_rolls_back_business_and_receipt(self):
        conn = Mock(); conn.cursor.return_value.fetchone.side_effect = [None, RuntimeError("database unavailable")]
        with self.assertRaises(RuntimeError):
            execute_command(conn, "PIGO_APPLY_COMMAND", self.command(), "00000000000191")
        conn.rollback.assert_called_once(); conn.commit.assert_not_called()

    def test_rejection_rolls_back_partial_erp_changes(self):
        conn = Mock(); conn.cursor.return_value.fetchone.side_effect = [None, ("rejected", None, "Campo obrigatório")]
        self.assertEqual(execute_command(conn, "PIGO_APPLY_COMMAND", self.command(), "00000000000191")["status"], "rejected")
        conn.rollback.assert_called_once(); conn.commit.assert_called_once()
        self.assertTrue(conn.cursor.return_value.execute.call_args.args[0].startswith("INSERT INTO PIGO_COMMAND_RECEIPT"))

    def test_procedure_identifier_cannot_contain_sql(self):
        conn = Mock()
        with self.assertRaises(ValueError):
            execute_command(conn, "ERP; DROP TABLE X", self.command(), "00000000000191")
        conn.cursor.assert_not_called()
