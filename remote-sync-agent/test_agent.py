import unittest
from unittest.mock import Mock, patch

import agent


def response(status, payload=None):
    result = Mock()
    result.status_code = status
    result.content = b"{}"
    result.json.return_value = payload or {}
    return result


class RemoteSyncAgentTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
