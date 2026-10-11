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

    def test_resume_parse_rejects_non_pdf(self) -> None:
        status, data = self.request(
            "POST",
            "/api/v1/resume/parse",
            {"filename": "resume.txt", "pdf_base64": "AAAA"},
        )
        self.assertEqual(status, 422)
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

    def test_resume_draft_roundtrip_stays_local(self) -> None:
        import os
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            os.environ["APPLYGUARD_LOCAL_DIR"] = folder
            missing_status, missing = self.request("GET", "/api/v1/resume/draft")
            self.assertEqual(missing_status, 200)
            self.assertFalse(missing["exists"])
            form = {
                "candidateId": "cand_demo_001",
                "basic": {"name": "林晓舟（演示）"},
                "intention": {},
                "education": [],
                "internships": [],
                "projects": [],
                "awards": [],
                "extras": {"skills": "", "awards": "", "summary": ""},
            }
            save_status, saved = self.request("POST", "/api/v1/resume/draft", form)
            self.assertEqual(save_status, 200)
            self.assertTrue(saved["saved"])
            loaded_status, loaded = self.request("GET", "/api/v1/resume/draft")
            self.assertEqual(loaded_status, 200)
            self.assertTrue(loaded["exists"])
            self.assertEqual(loaded["form"]["basic"]["name"], "林晓舟（演示）")
            self.assertTrue((Path(folder) / "resume-draft.json").is_file())
            os.environ.pop("APPLYGUARD_LOCAL_DIR", None)


class ResumeExtractTests(unittest.TestCase):
    def test_rule_extract_reads_labeled_chinese_fields(self) -> None:
        from backend.services.resume_parser import extract_resume_from_text

        text = """
姓名：林晓舟
性别：男
手机：13800000001
邮箱：lin@example.com
出生年月：2004年05月
现居住地：广东省深圳市
求职意向：后端开发
教育经历
示例理工大学
专业：软件工程
本科
实习经历
北桥课程实验组
使用 Python 完成接口开发
项目经历
学生服务门户
获奖情况
校级程序设计竞赛二等奖
技能
Python、Git
"""
        result = extract_resume_from_text(text)
        self.assertEqual(result["basic"]["name"], "林晓舟")
        self.assertEqual(result["basic"]["phone"], "13800000001")
        self.assertEqual(result["basic"]["email"], "lin@example.com")
        self.assertEqual(result["intention"]["expectRole"], "后端开发")
        self.assertTrue(result["education"])
        self.assertIn("软件工程", result["education"][0]["major"])
        self.assertTrue(result["awards"])
        self.assertIn("程序设计", result["awards"][0]["name"])

    def test_rule_extract_reads_contest_section(self) -> None:
        from backend.services.resume_parser import extract_resume_from_text

        text = """
项目经历
学生服务门户
竞赛经历
2024.05 全国大学生数学建模竞赛省级二等奖
2023.11 校级程序设计大赛一等奖
技能
Python
"""
        result = extract_resume_from_text(text)
        names = " ".join(item["name"] for item in result["awards"])
        self.assertIn("数学建模", names)
        self.assertIn("程序设计", names)
        self.assertEqual(len(result["awards"]), 2)
        self.assertNotIn("数学建模", result["projects"][0]["description"] if result["projects"] else "")


if __name__ == "__main__":
    unittest.main()

