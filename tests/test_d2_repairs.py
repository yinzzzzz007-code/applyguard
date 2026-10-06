"""Regression checks for D-2 evidence isolation and durable draft saving."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import CAREER_VAULT_PATH, build_mock_workflow
from backend.services.draft_store import DraftStore
from backend.services.evidence_matcher import EvidenceMatcher


def seed_form() -> dict:
    seed = json.loads(CAREER_VAULT_PATH.read_text(encoding="utf-8"))
    entries = []
    for exp in seed["experiences"]:
        entries.append({"id": exp["experience_id"], "sourceExperienceId": exp["experience_id"],
                        "organization": exp["organization"], "title": exp["title"], "role": exp["role"],
                        "start": exp["start_date"], "end": exp["end_date"],
                        "description": "\n".join([exp["summary"], *exp["responsibilities"]])})
    return {"candidateId": seed["candidate_id"], "basic": {"name": "林晓舟"},
            "intention": {}, "education": [], "internships": [], "projects": entries,
            "extras": {}, "awards": [], "dirty": True}


class DraftIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = DraftStore(Path(self.temp.name), CAREER_VAULT_PATH)

    def test_unchanged_seed_keeps_evidence_but_edited_entry_loses_it(self) -> None:
        form = seed_form()
        first = self.store.save(form["candidateId"], form)
        self.assertEqual(first["vault"]["experiences"][0]["claims"][0]["claim_id"], "claim_python_api")
        form["projects"][0]["description"] = "曾尝试写接口，未保存证明。"
        second = self.store.save(form["candidateId"], form)
        changed = second["vault"]["experiences"][0]
        self.assertEqual(changed["claims"], [])
        self.assertEqual(changed["evidence_sources"], [])
        self.assertEqual(changed["verification_state"], "UNVERIFIED")
        self.assertNotEqual(first["version"], second["version"])

    def test_failed_atomic_replace_keeps_last_good_draft(self) -> None:
        form = seed_form()
        good = self.store.save(form["candidateId"], form)
        form["projects"][0]["description"] = "新描述"
        with patch("backend.services.draft_store.os.replace", side_effect=OSError("simulated disk failure")):
            with self.assertRaises(OSError):
                self.store.save(form["candidateId"], form)
        self.assertEqual(self.store.load(form["candidateId"])["version"], good["version"])
        self.assertFalse(list(Path(self.temp.name).glob("*.tmp")))

    def test_workflow_uses_saved_draft_not_old_seed_claim(self) -> None:
        form = seed_form()
        form["projects"][0]["description"] = "仅参加课堂讨论，未完成接口或测试。"
        self.store.save(form["candidateId"], form)
        with patch.dict(os.environ, {"APPLYGUARD_LOCAL_DATA_DIR": self.temp.name}):
            result = build_mock_workflow({"candidate_id": form["candidateId"],
                                          "jd_text": "后端开发实习生，负责 Python 接口服务和自动化测试。",
                                          "parse_mode": "offline"})
        self.assertNotIn("claim_python_api", {claim["claim_id"] for claim in result["resume_claims"]})
        self.assertNotIn("ev_repo_api", {ev for match in result["evidence_match"]["matches"]
                                         for ev in match.get("evidence_ids", [])})

    def test_candidate_path_rejects_traversal(self) -> None:
        with self.assertRaises(ValueError):
            self.store.load("../../secrets")

    def test_award_saves_as_unverified_structured_data(self) -> None:
        form = seed_form()
        form["awards"] = [{"id": "award_pdf_001", "name": "虚构创新大赛一等奖", "category": "竞赛",
                           "organizer": "虚构协会", "level": "省级", "rank": "一等奖", "date": "2026-05",
                           "role": "团队成员", "sourcePage": 2, "sourceLine": "虚构创新大赛 省级 一等奖"}]
        saved = self.store.save(form["candidateId"], form)
        self.assertEqual(saved["vault"]["awards"][0]["sourcePage"], 2)
        self.assertFalse(any("award_pdf_001" == claim["claim_id"] for exp in saved["vault"]["experiences"] for claim in exp["claims"]))
        form["awards"][0]["date"] = "2026-13"
        with self.assertRaisesRegex(ValueError, "award schema"):
            self.store.save(form["candidateId"], form)


class SpecialtyMatchTests(unittest.TestCase):
    def test_generic_ml_cannot_claim_multimodal_or_reinforcement_learning(self) -> None:
        seed = json.loads(CAREER_VAULT_PATH.read_text(encoding="utf-8"))
        for specialty in ("多模态", "强化学习", "推荐系统"):
            with self.subTest(specialty=specialty):
                parsed = {"jd_id": "jd_specialty", "title": "算法实习生", "company": "虚构单位",
                          "source_text": f"需要{specialty}经验", "requirements": [{
                              "requirement_id": "req_001", "type": "REQUIRED", "category": "SKILL",
                              "text": f"需要{specialty}经验", "evidence_text": f"需要{specialty}经验",
                              "normalized_terms": [specialty], "confidence": 1.0}]}
                result = EvidenceMatcher().match(parsed, seed["experiences"])
                self.assertFalse(any(m["evidence_strength"] == "STRONG" for m in result["matches"]))


if __name__ == "__main__":
    unittest.main()
