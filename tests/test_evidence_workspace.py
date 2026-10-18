"""Local evidence workspace: import, review, link, conflict, stale version."""

from __future__ import annotations

import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "evidence-samples"


class EvidenceWorkspaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["APPLYGUARD_EVIDENCE_DIR"] = self._tmp.name
        os.environ["APPLYGUARD_LOCAL_DIR"] = self._tmp.name
        from backend.services import evidence_workspace as ew

        self.ew = ew
        ew.init_db()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _b64(self, path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("ascii")

    def test_import_review_link_conflict_and_stale(self) -> None:
        ws = self.ew.create_workspace("测试工作区")
        ws_id = ws["workspace_id"]
        png = SAMPLES / "award-programming.png"
        ocr = SAMPLES / "award-programming.png.ocr.json"
        md = SAMPLES / "award-scholarship.md"
        pdf = SAMPLES / "award-programming-text.pdf"
        scanned = SAMPLES / "award-scanned-stub.pdf"
        docx = SAMPLES / "award-programming.docx"
        self.assertTrue(png.is_file())
        self.assertTrue(docx.is_file())

        imported = self.ew.import_files(
            ws_id,
            [
                {"relative_path": png.name, "content_base64": self._b64(png)},
                {"relative_path": ocr.name, "content_base64": self._b64(ocr)},
                {"relative_path": md.name, "content_base64": self._b64(md)},
                {"relative_path": pdf.name, "content_base64": self._b64(pdf)},
                {"relative_path": scanned.name, "content_base64": self._b64(scanned)},
                {"relative_path": docx.name, "content_base64": self._b64(docx)},
            ],
        )
        files = {f["relative_path"]: f for f in imported["files"] if not f.get("sidecar")}
        self.assertEqual(files[png.name]["state"], "NEEDS_REVIEW")
        self.assertTrue(files[png.name].get("evidence_id"))
        self.assertIn("二等奖", (files[png.name].get("suggested_fields") or {}).get("grade", ""))
        self.assertEqual(files[md.name]["state"], "NEEDS_REVIEW")
        self.assertEqual(files[pdf.name]["state"], "NEEDS_REVIEW")
        self.assertIn(files[scanned.name]["state"], {"NEEDS_REVIEW", "FAILED"})
        self.assertEqual(files[docx.name]["state"], "NEEDS_REVIEW")

        evidence_id = files[png.name]["evidence_id"]
        detail = self.ew.get_evidence(evidence_id)
        self.assertTrue(any("二等奖" in s["raw_text"] for s in detail["spans"]))
        hit = next(s for s in detail["spans"] if "二等奖" in s["raw_text"])
        self.assertEqual(len(hit["bbox"]), 4)

        reviewed = self.ew.review_evidence(
            evidence_id,
            {
                "normalized_fields": {
                    "recipient": "示例同学",
                    "award_name": "校级程序设计竞赛",
                    "grade": "二等奖",
                    "issuer": "示例理工大学学生会（虚构）",
                    "date": "2025-11",
                },
                "review_state": "REVIEWED",
            },
        )
        self.assertEqual(reviewed["review_state"], "REVIEWED")
        # OCR original preserved
        self.assertEqual(reviewed["ocr_fields"].get("grade"), "二等奖")

        link = self.ew.create_link(
            {
                "target_type": "award",
                "target_id": "award_campus_programming",
                "evidence_id": evidence_id,
            }
        )
        self.assertEqual(link["link_state"], "ACTIVE")

        ok = self.ew.check_claim_support("获得校级程序设计竞赛二等奖", evidence_id)
        self.assertEqual(ok["status"], "VERIFIED")
        bad = self.ew.check_claim_support("获得校级程序设计竞赛一等奖", evidence_id)
        self.assertEqual(bad["status"], "CONFLICT")

        search = self.ew.search_evidence("二等奖", workspace_id=ws_id)
        self.assertGreaterEqual(len(search["matches"]), 1)

        # Same bytes again → reuse OCR, do not create a new version
        same = self.ew.import_files(
            ws_id,
            [
                {"relative_path": png.name, "content_base64": self._b64(png)},
                {"relative_path": ocr.name, "content_base64": self._b64(ocr)},
            ],
        )
        png_same = next(f for f in same["files"] if f.get("relative_path") == png.name)
        self.assertTrue(png_same.get("skipped_reparse") or png_same.get("deduplicated"))
        self.assertEqual(png_same["file_id"], files[png.name]["file_id"])
        self.assertEqual(png_same["version"], files[png.name]["version"])

        # Explicit reparse on stored file keeps file_id, refreshes recognition
        reparsed = self.ew.reparse_file(files[png.name]["file_id"])
        self.assertTrue(reparsed.get("reparsed"))
        self.assertEqual(reparsed["file_id"], files[png.name]["file_id"])
        self.assertGreaterEqual(reparsed.get("span_count") or 0, 1)

        # Re-import modified image → STALE old link
        mutated = png.read_bytes() + b"\x00"
        again = self.ew.import_files(
            ws_id,
            [
                {"relative_path": png.name, "content_base64": base64.b64encode(mutated).decode()},
                {"relative_path": ocr.name, "content_base64": self._b64(ocr)},
            ],
        )
        png_again = next(f for f in again["files"] if f.get("relative_path") == png.name)
        self.assertTrue(png_again.get("stale_previous"))
        links = self.ew.list_links(target_type="award", target_id="award_campus_programming")
        self.assertTrue(any(item["link_state"] == "STALE" for item in links["links"]))

        preview = self.ew.resolve_preview_path(files[png.name]["file_id"])
        self.assertTrue(preview[0].is_file())

    def test_match_resume_reports_gaps_and_matches(self) -> None:
        ws = self.ew.create_workspace("对照测试")
        ws_id = ws["workspace_id"]
        png = SAMPLES / "award-programming.png"
        ocr = SAMPLES / "award-programming.png.ocr.json"
        imported = self.ew.import_files(
            ws_id,
            [
                {"relative_path": png.name, "content_base64": self._b64(png)},
                {"relative_path": ocr.name, "content_base64": self._b64(ocr)},
            ],
        )
        evidence_id = next(f["evidence_id"] for f in imported["files"] if f.get("evidence_id"))
        self.ew.review_evidence(
            evidence_id,
            {
                "normalized_fields": {
                    "recipient": "示例同学",
                    "award_name": "校级程序设计竞赛",
                    "grade": "二等奖",
                    "issuer": "示例理工大学学生会（虚构）",
                    "date": "2025-11",
                },
                "review_state": "REVIEWED",
            },
        )
        report = self.ew.match_resume(
            ws_id,
            {
                "awards": [
                    {
                        "award_id": "award_campus_programming",
                        "name": "校级程序设计竞赛二等奖（虚构）",
                        "issuer": "示例理工大学学生会（虚构）",
                        "date": "2025-11",
                        "description": "虚构个人赛",
                    },
                    {
                        "award_id": "award_scholarship",
                        "name": "校级学习优秀奖学金（虚构）",
                        "issuer": "示例理工大学（虚构）",
                        "date": "2025-10",
                        "description": "虚构学年综合测评奖学金。",
                    },
                    {
                        "award_id": "award_fake_first",
                        "name": "校级程序设计竞赛一等奖（虚构）",
                        "issuer": "示例理工大学学生会（虚构）",
                        "date": "2025-11",
                        "description": "故意写错等级",
                    },
                ],
                "projects": [
                    {
                        "id": "exp_api",
                        "organization": "示例课程项目",
                        "title": "HTTP API",
                        "role": "后端",
                        "description": "Python 接口与测试",
                    }
                ],
                "internships": [
                    {
                        "id": "exp_ml_evaluation",
                        "organization": "示例实习",
                        "title": "模型评测",
                        "role": "实习生",
                        "description": "PyTorch 评测",
                    }
                ],
            },
        )
        by_id = {row["target_id"]: row for row in report["results"]}
        self.assertIn(by_id["award_campus_programming"]["status"], {"MATCHED", "NEEDS_CONFIRM"})
        self.assertEqual(by_id["award_scholarship"]["status"], "MISSING")
        self.assertEqual(by_id["award_fake_first"]["status"], "CONFLICT")
        self.assertIn(by_id["exp_api"]["kind"], {"项目", "经历"})
        self.assertIn(by_id["exp_ml_evaluation"]["kind"], {"实习", "经历"})
        # Reject wrong candidate then rematch → should not keep forcing it
        cand = by_id["award_campus_programming"]["evidence_id"]
        self.ew.create_link(
            {
                "target_type": "award",
                "target_id": "award_campus_programming",
                "evidence_id": cand,
                "link_state": "REJECTED",
            }
        )
        again = self.ew.match_resume(
            ws_id,
            {
                "awards": [
                    {
                        "award_id": "award_campus_programming",
                        "name": "校级程序设计竞赛二等奖（虚构）",
                        "issuer": "示例理工大学学生会（虚构）",
                        "date": "2025-11",
                        "description": "虚构个人赛",
                    }
                ]
            },
        )
        row = again["results"][0]
        self.assertNotEqual(row.get("evidence_id"), cand)
        self.assertEqual(row["status"], "MISSING")

    def test_internship_certificate_matches_org_in_glued_ocr(self) -> None:
        """Company names often sit mid-sentence with no separators after OCR."""
        ws = self.ew.create_workspace("实习匹配")
        ws_id = ws["workspace_id"]
        text = (
            "实习证明\n"
            "兹有示例理工大学张三同学从2026年07月14日至2026年08月13日"
            "由我单位安排至示例云网科技有限公司云网事业部（部门）实习，"
            "实习工作内容为开源及其它开发。\n"
            "示例人才服务有限公司\n"
        )
        md_name = "internship-proof.md"
        imported = self.ew.import_files(
            ws_id,
            [
                {
                    "relative_path": md_name,
                    "content_base64": base64.b64encode(text.encode("utf-8")).decode(),
                }
            ],
        )
        self.assertTrue(imported["files"][0].get("evidence_id"))
        report = self.ew.match_resume(
            ws_id,
            {
                "internships": [
                    {
                        "id": "intern_yx",
                        "organization": "示例云网科技有限公司",
                        "title": "云网事业部实习",
                        "role": "",
                        "start": "2026-07",
                        "end": "2026-08",
                        "description": "参与开源开发工作，结合 AI Agent 与 Python 构建复杂业务流水线。",
                    }
                ]
            },
        )
        row = report["results"][0]
        self.assertIn(row["status"], {"NEEDS_CONFIRM", "MATCHED"})
        self.assertGreaterEqual(row["score"], 45)
        self.assertEqual(row["evidence_id"], imported["files"][0]["evidence_id"])

    def test_delete_files_keeps_siblings(self) -> None:
        ws = self.ew.create_workspace("删除测试")
        ws_id = ws["workspace_id"]
        md = SAMPLES / "award-scholarship.md"
        png = SAMPLES / "award-programming.png"
        ocr = SAMPLES / "award-programming.png.ocr.json"
        imported = self.ew.import_files(
            ws_id,
            [
                {"relative_path": "keep/" + md.name, "content_base64": self._b64(md)},
                {"relative_path": "drop/" + png.name, "content_base64": self._b64(png)},
                {"relative_path": "drop/" + ocr.name, "content_base64": self._b64(ocr)},
            ],
        )
        drop = next(f for f in imported["files"] if f.get("relative_path", "").startswith("drop/") and not f.get("sidecar"))
        keep = next(f for f in imported["files"] if f.get("relative_path", "").startswith("keep/"))
        deleted = self.ew.delete_files([drop["file_id"]], workspace_id=ws_id)
        self.assertTrue(deleted["deleted"])
        self.assertGreaterEqual(deleted["removed"], 1)
        listed = self.ew.list_files(ws_id)
        paths = {f["relative_path"] for f in listed}
        self.assertIn(keep["relative_path"], paths)
        self.assertNotIn(drop["relative_path"], paths)
        # Second distinct path with same basename still appends
        again = self.ew.import_files(
            ws_id,
            [{"relative_path": "added/" + md.name, "content_base64": self._b64(md)}],
        )
        self.assertEqual(again["files"][0]["state"] in {"INDEXED", "NEEDS_REVIEW"}, True)
        listed2 = self.ew.list_files(ws_id)
        self.assertEqual(len(listed2), 2)


class EvidenceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        os.environ["APPLYGUARD_EVIDENCE_DIR"] = cls._tmp.name
        os.environ["APPLYGUARD_LOCAL_DIR"] = cls._tmp.name
        from backend.app import create_server

        cls.server = create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls._tmp.cleanup()

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = None if body is None else json.dumps(body)
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        connection.close()
        ctype = response.getheader("Content-Type") or ""
        if "application/json" in ctype:
            return response.status, json.loads(raw.decode("utf-8"))
        return response.status, raw

    def test_workspace_http_roundtrip(self) -> None:
        status, data = self.request("POST", "/api/v1/evidence/workspaces", {"name": "API工作区"})
        self.assertEqual(status, 200)
        assert isinstance(data, dict)
        ws_id = data["workspace_id"]
        md = SAMPLES / "award-scholarship.md"
        status, imported = self.request(
            "POST",
            f"/api/v1/evidence/workspaces/{ws_id}/files",
            {
                "files": [
                    {
                        "relative_path": md.name,
                        "content_base64": base64.b64encode(md.read_bytes()).decode(),
                    }
                ]
            },
        )
        self.assertEqual(status, 200)
        assert isinstance(imported, dict)
        file_id = imported["files"][0]["file_id"]
        status, preview = self.request("GET", f"/api/v1/evidence/files/{file_id}/preview")
        self.assertEqual(status, 200)
        self.assertIsInstance(preview, (bytes, bytearray))
        self.assertGreater(len(preview), 10)
        status, deleted = self.request(
            "POST",
            "/api/v1/evidence/files/delete",
            {"file_ids": [file_id], "workspace_id": ws_id},
        )
        self.assertEqual(status, 200)
        assert isinstance(deleted, dict)
        self.assertTrue(deleted.get("deleted"))
        status, listing = self.request("GET", f"/api/v1/evidence/workspaces/{ws_id}/files")
        self.assertEqual(status, 200)
        assert isinstance(listing, dict)
        self.assertEqual(listing.get("files") or [], [])


if __name__ == "__main__":
    unittest.main()
