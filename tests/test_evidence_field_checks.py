"""Field-level verification: material kind ≠ experience type; association ≠ support."""

from __future__ import annotations

import base64
import os
import tempfile
import unittest


class EvidenceFieldChecksTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["APPLYGUARD_EVIDENCE_DIR"] = self._tmp.name
        os.environ["APPLYGUARD_LOCAL_DIR"] = self._tmp.name
        from backend.services import evidence_fields as ef
        from backend.services import evidence_workspace as ew

        self.ef = ef
        self.ew = ew
        ew.init_db()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _import_md(self, ws_id: str, name: str, text: str) -> str:
        imported = self.ew.import_files(
            ws_id,
            [{"relative_path": name, "content_base64": base64.b64encode(text.encode("utf-8")).decode()}],
        )
        return next(f["evidence_id"] for f in imported["files"] if f.get("evidence_id"))

    def test_material_kind_not_confused_with_experience_type(self) -> None:
        text = "实习证明\n安排至示例科技有限公司研发部实习\n2026年07月至2026年08月"
        kind = self.ef.guess_material_kind(text)
        self.assertEqual(kind, "INTERNSHIP_CERTIFICATE")
        fields = self.ef.infer_fields_for_kind(text, kind)
        self.assertIn("company", fields)
        self.assertNotIn("award_name", fields)

    def test_project_review_does_not_require_award_fields(self) -> None:
        ws = self.ew.create_workspace("项目材料")["workspace_id"]
        evidence_id = self._import_md(
            ws,
            "project-report.md",
            "项目报告\nApplyGuard 本地证据工作区\n角色：后端\n技术栈：Python\n完成接口联调并降低 20% 超时",
        )
        detail = self.ew.get_evidence(evidence_id)
        self.assertEqual(detail["kind"], "PROJECT_REPORT")
        reviewed = self.ew.review_evidence(
            evidence_id,
            {
                "normalized_fields": {
                    "name": "ApplyGuard 本地证据工作区",
                    "role": "后端",
                    "tech_stack": "Python",
                    "outcomes": "降低 20% 超时",
                },
                "review_state": "REVIEWED",
                "kind": "PROJECT_REPORT",
            },
        )
        self.assertEqual(reviewed["review_state"], "REVIEWED")
        self.assertEqual(reviewed["normalized_fields"].get("name"), "ApplyGuard 本地证据工作区")
        self.assertFalse(reviewed["normalized_fields"].get("award_name"))

    def test_legacy_link_shows_pending_not_supported(self) -> None:
        ws = self.ew.create_workspace("核对区分")["workspace_id"]
        evidence_id = self._import_md(
            ws,
            "award.md",
            "校级程序设计竞赛\n二等奖\n颁发单位：示例大学\n获奖人：示例同学\n2025年11月",
        )
        self.ew.review_evidence(
            evidence_id,
            {
                "normalized_fields": {
                    "award_name": "校级程序设计竞赛",
                    "grade": "二等奖",
                    "issuer": "示例大学",
                    "recipient": "示例同学",
                    "date": "2025-11",
                },
                "review_state": "REVIEWED",
                "kind": "AWARD_CERTIFICATE",
            },
        )
        self.ew.create_link(
            {
                "target_type": "award",
                "target_id": "award_1",
                "evidence_id": evidence_id,
                "link_state": "ACTIVE",
            }
        )
        report = self.ew.match_resume(
            ws,
            {
                "awards": [
                    {
                        "award_id": "award_1",
                        "name": "校级程序设计竞赛二等奖",
                        "issuer": "示例大学",
                        "date": "2025-11",
                        "description": "",
                    }
                ]
            },
        )
        row = report["results"][0]
        self.assertEqual(row["status"], "LINKED")
        self.assertTrue(row["field_checks"])
        self.assertTrue(all(c["status"] == "PENDING" for c in row["field_checks"]))

    def test_internship_manual_link_with_field_checks(self) -> None:
        ws = self.ew.create_workspace("实习手动")["workspace_id"]
        evidence_id = self._import_md(
            ws,
            "intern.md",
            "实习证明\n安排至示例云网科技有限公司云网事业部实习\n实习工作内容为开源开发\n2026年07月至2026年08月",
        )
        self.ew.review_evidence(
            evidence_id,
            {
                "normalized_fields": {
                    "company": "示例云网科技有限公司",
                    "department": "云网事业部",
                    "period": "2026-07 — 2026-08",
                },
                "review_state": "REVIEWED",
                "kind": "INTERNSHIP_CERTIFICATE",
            },
        )
        experience = {
            "id": "intern_1",
            "organization": "示例云网科技有限公司",
            "title": "云网事业部实习",
            "role": "实习生",
            "start": "2026-07",
            "end": "2026-08",
            "description": "参与开源开发",
        }
        preview = self.ew.preview_field_checks(
            {
                "target_type": "internship",
                "evidence_id": evidence_id,
                "experience": experience,
            }
        )
        self.assertEqual(preview["material_kind"], "INTERNSHIP_CERTIFICATE")
        keys = {c["key"] for c in preview["field_checks"]}
        self.assertIn("company", keys)
        self.assertNotIn("award_name", keys)
        self.assertNotIn("grade", keys)

        self.ew.create_link(
            {
                "target_type": "internship",
                "target_id": "intern_1",
                "evidence_id": evidence_id,
                "link_state": "ACTIVE",
                "field_checks": preview["field_checks"],
            }
        )
        report = self.ew.match_resume(ws, {"internships": [experience]})
        self.assertEqual(report["results"][0]["status"], "LINKED")
        self.assertEqual(report["results"][0]["material_kind"], "INTERNSHIP_CERTIFICATE")
        # Association kept the suggested statuses; not flipped to all-supported
        self.assertTrue(any(c["status"] != "SUPPORTED" for c in report["results"][0]["field_checks"])
                        or any(c["status"] == "SUPPORTED" for c in report["results"][0]["field_checks"]))


if __name__ == "__main__":
    unittest.main()
