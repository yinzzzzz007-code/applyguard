"""Local workflow-draft persistence and source-fingerprint stale checks."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.services import local_store


def _minimal_workflow(**overrides):
    base = {
        "application_id": "app_local_001",
        "candidate_id": "cand_demo_001",
        "parsed_jd": {
            "jd_id": "jd_test",
            "title": "后端实习生",
            "company": "UNKNOWN",
            "source_text": "任职要求\n熟悉 Python，具备良好的编程习惯和基础工程能力。",
            "requirements": [],
        },
        "evidence_match": {"match_id": "m1", "jd_id": "jd_test", "candidate_id": "cand_demo_001",
                           "matches": [], "uncovered_requirements": []},
        "resume_selection": {"application_id": "app_local_001", "selected_claim_ids": [],
                             "claims": [], "max_claims": 1, "max_characters": 420},
        "resume_claims": [{"claim_id": "claim_1", "text": "熟悉 Python 开发。", "evidence_ids": []}],
        "claim_verification": [{"claim_id": "claim_1", "state": "NEEDS_REVIEW", "grounded": False,
                                "support_score": 0, "explanation": "demo"}],
        "field_controls": [],
        "human_confirmation": {"required": True, "allowed_actions": ["EDIT", "CANCEL"], "reason": "demo"},
        "risk_result": {"action": "ALLOW", "reasons": []},
        "ats_form_mapping": {"application_id": "app_local_001", "target": "ATS_SIMULATOR", "fields": []},
        "step_trace": [{"step": "JD Parser", "mode": "RULE_FALLBACK"}],
    }
    base.update(overrides)
    return base


class WorkflowDraftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.patcher = mock.patch.object(local_store, "local_dir", return_value=self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_save_and_load_roundtrip(self) -> None:
        jd = "任职要求\n熟悉 Python，具备良好的编程习惯和基础工程能力。"
        workflow = _minimal_workflow()
        saved = local_store.save_workflow_draft({"workflow": workflow, "jd": jd})
        self.assertTrue(saved["saved"])
        loaded = local_store.load_workflow_draft()
        self.assertTrue(loaded["exists"])
        self.assertFalse(loaded["stale"])
        self.assertEqual(loaded["workflow"]["application_id"], "app_local_001")
        self.assertEqual(loaded["jd"], jd)

    def test_resume_change_marks_stale(self) -> None:
        jd = "任职要求\n熟悉 Python，具备良好的编程习惯和基础工程能力。"
        local_store.save_workflow_draft({"workflow": _minimal_workflow(), "jd": jd, "resume_saved_at": "old"})
        (self.root / "resume-draft.json").write_text(
            json.dumps({"saved_at": "new", "form": {"candidateId": "cand_demo_001", "basic": {}, "savedAt": "new"}},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        loaded = local_store.load_workflow_draft()
        self.assertTrue(loaded["stale"])
        self.assertIn("经历库", loaded["stale_reason"])

    def test_jd_change_marks_stale(self) -> None:
        jd = "任职要求\n熟悉 Python，具备良好的编程习惯和基础工程能力。"
        local_store.save_workflow_draft({"workflow": _minimal_workflow(), "jd": jd})
        loaded = local_store.load_workflow_draft(current_jd=jd + "\n加分项\n了解 Git。")
        self.assertTrue(loaded["stale"])
        self.assertIn("岗位原文", loaded["stale_reason"])

    def test_clear_removes_file(self) -> None:
        jd = "任职要求\n熟悉 Python，具备良好的编程习惯和基础工程能力。"
        local_store.save_workflow_draft({"workflow": _minimal_workflow(), "jd": jd})
        self.assertTrue(local_store.workflow_draft_path().is_file())
        local_store.clear_workflow_draft()
        self.assertFalse(local_store.workflow_draft_path().is_file())
        self.assertIsNone(local_store.load_workflow_draft())

    def test_reject_prerecorded(self) -> None:
        jd = "任职要求\n熟悉 Python，具备良好的编程习惯和基础工程能力。"
        with self.assertRaises(ValueError):
            local_store.save_workflow_draft({
                "workflow": _minimal_workflow(_prerecorded={"case": "unsupported_block"}),
                "jd": jd,
            })


if __name__ == "__main__":
    unittest.main()
