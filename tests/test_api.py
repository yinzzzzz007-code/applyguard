import http.client
import json
import threading
import unittest

from backend.app import build_mock_workflow, create_server


class WorkflowUnitTests(unittest.TestCase):
    def test_mock_workflow_requires_human_confirmation(self) -> None:
        result = build_mock_workflow(
            {
                "candidate_id": "cand_demo_001",
                "jd_text": "Software engineering internship requiring Python APIs and automated tests.",
            }
        )
        self.assertEqual(result["workflow_status"], "AWAITING_HUMAN_CONFIRMATION")
        self.assertTrue(result["human_confirmation"]["required"])
        self.assertEqual(len(result["step_trace"]), 9)
        for claim in result["resume_claims"]:
            self.assertGreaterEqual(len(claim["evidence_ids"]), 1)

    def test_short_jd_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 20"):
            build_mock_workflow({"candidate_id": "cand_demo_001", "jd_text": "short"})


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = None if body is None else json.dumps(body)
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_health(self) -> None:
        status, data = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_mock_endpoint(self) -> None:
        status, data = self.request(
            "POST",
            "/api/v1/workflow/mock",
            {
                "candidate_id": "cand_demo_001",
                "jd_text": "Software engineering internship requiring Python APIs and automated tests.",
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("risk_result", data)
        self.assertEqual(data["step_trace"][-1]["step"], "Audit Record")

    def test_validation_error_uses_unified_envelope(self) -> None:
        status, data = self.request("POST", "/api/v1/workflow/mock", {"candidate_id": "", "jd_text": "short"})
        self.assertEqual(status, 422)
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")
        self.assertTrue(data["error"]["trace_id"].startswith("trace_"))

    def test_not_found(self) -> None:
        status, data = self.request("GET", "/missing")
        self.assertEqual(status, 404)
        self.assertEqual(data["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()

