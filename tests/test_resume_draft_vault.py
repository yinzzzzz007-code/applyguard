"""Resume draft → workflow experiences."""

from __future__ import annotations

import unittest

from backend.services.resume_draft_vault import experiences_from_resume_draft
from backend.services.schema_validation import validate_contract


class ResumeDraftVaultTests(unittest.TestCase):
    def test_builds_claims_from_internships_and_awards(self) -> None:
        form = {
            "candidateId": "cand_demo_001",
            "internships": [
                {
                    "id": "internship_yixun",
                    "organization": "广东亿迅科技有限公司",
                    "title": "后端开发实习生",
                    "role": "实习生",
                    "start": "2025-07",
                    "end": "2025-09",
                    "description": "参与内部平台接口开发，编写单元测试。",
                }
            ],
            "projects": [],
            "awards": [
                {
                    "id": "award_1",
                    "name": "校级程序设计竞赛二等奖",
                    "issuer": "学生会",
                    "date": "2025-11",
                    "description": "",
                }
            ],
        }
        items = experiences_from_resume_draft(form)
        self.assertEqual(len(items), 2)
        for item in items:
            validate_contract("experience", item)
        texts = {c["text"] for exp in items for c in exp["claims"]}
        self.assertTrue(any("亿迅" in t or "接口" in t for t in texts))
        self.assertTrue(any("程序设计" in t for t in texts))
        # Must not look like seed claim ids
        claim_ids = {c["claim_id"] for exp in items for c in exp["claims"]}
        self.assertFalse(any("lora" in cid or "pipeline" in cid for cid in claim_ids))
        internship = next(item for item in items if "亿迅" in item["organization"] or "接口" in item["summary"])
        award = next(item for item in items if "程序设计" in item["title"] or "程序设计" in item["summary"])
        self.assertEqual(internship["verification_state"], "UNVERIFIED")
        self.assertEqual(award["verification_state"], "UNVERIFIED")
        self.assertEqual(award["evidence_sources"][0]["verification_status"], "UNVERIFIED")

    def test_education_becomes_matchable_experience(self) -> None:
        form = {
            "candidateId": "cand_local_draft",
            "education": [
                {
                    "id": "edu_1",
                    "school": "华南理工大学",
                    "degree": "本科",
                    "major": "数据科学与大数据技术",
                    "start": "2024-09",
                    "end": "2028-09",
                    "fullTime": "是",
                }
            ],
            "internships": [],
            "projects": [],
            "awards": [],
        }
        items = experiences_from_resume_draft(form)
        self.assertEqual(len(items), 1)
        validate_contract("experience", items[0])
        text = items[0]["claims"][0]["text"]
        self.assertIn("华南理工大学", text)
        self.assertIn("本科", text)
        self.assertIn("在读", text)
        self.assertEqual(items[0]["organization"], "华南理工大学")
        self.assertEqual(items[0]["verification_state"], "VERIFIED")
        self.assertEqual(items[0]["claims"][0]["verification_state"], "VERIFIED")
        self.assertEqual(items[0]["evidence_sources"][0]["verification_status"], "VERIFIED")

    def test_education_form_match_is_strong_for_enrolled_degree(self) -> None:
        from backend.services.evidence_matcher import EvidenceMatcher

        form = {
            "candidateId": "cand_local_draft",
            "education": [
                {
                    "id": "edu_extract_1",
                    "school": "华南理工大学",
                    "degree": "",
                    "major": "数据科学与大数据技术",
                    "start": "2024-09",
                    "end": "2028-09",
                }
            ],
            "internships": [],
            "projects": [],
            "awards": [],
        }
        experiences = experiences_from_resume_draft(form)
        requirement = {
            "requirement_id": "req_edu",
            "type": "HARD",
            "category": "EDUCATION",
            "text": "本科及以上在读",
            "normalized_terms": ["本科及以上在读", "本科"],
            "evidence_text": "本科及以上在读",
            "confidence": 0.9,
        }
        # Simulate AI paraphrase coverage for university enrollment without inventing evidence IDs.
        matcher = EvidenceMatcher()
        terms = matcher._requirement_terms(requirement)
        scored = matcher.score_linked_claims(
            requirement,
            terms,
            experiences[0],
            experiences[0]["claims"],
            semantic_score=0.9,
            model_rationale="华南理工大学在读，符合本科及以上在读。",
            require_keyword_hit=False,
        )
        self.assertIsNotNone(scored)
        assert scored is not None
        self.assertEqual(scored["evidence_strength"], "STRONG")
        self.assertTrue(scored["ready_for_selection"])
        self.assertFalse(scored["missing_evidence"])

    def test_form_confirmed_education_passes_reverify_without_file_original(self) -> None:
        from pathlib import Path

        from backend.services.reverification import reverify_workflow

        form = {
            "candidateId": "cand_local_draft",
            "education": [
                {
                    "id": "edu_extract_1",
                    "school": "华南理工大学",
                    "degree": "",
                    "major": "数据科学与大数据技术",
                    "start": "2024-09",
                    "end": "2028-09",
                }
            ],
            "internships": [],
            "projects": [
                {
                    "id": "proj_need_evidence",
                    "organization": "实验室",
                    "title": "评测项目",
                    "role": "成员",
                    "start": "2025-01",
                    "end": "2025-06",
                    "description": "参与 Benchmark 接入与模型评测。",
                }
            ],
            "awards": [],
        }
        items = experiences_from_resume_draft(form)
        edu_claim = next(claim for exp in items for claim in exp["claims"] if "edu" in claim["claim_id"])
        proj_claim = next(claim for exp in items for claim in exp["claims"] if "proj" in claim["claim_id"])
        result = reverify_workflow(
            Path("data/career-vault.seed.json"),
            {
                "candidate_id": items[0]["candidate_id"],
                "jd_text": "任职要求\n本科及以上在读，计算机相关专业优先；\n熟悉 Python。\n加分项\n了解评测框架。",
                "claims": [
                    {"claim_id": edu_claim["claim_id"], "text": edu_claim["text"]},
                    {"claim_id": proj_claim["claim_id"], "text": proj_claim["text"]},
                ],
                "resume_draft": form,
                "grounding_mode": "off",
            },
            _skip_grounding=True,
        )
        by_id = {row["claim_id"]: row for row in result["claim_verification"]}
        self.assertEqual(by_id[edu_claim["claim_id"]]["state"], "VERIFIED")
        self.assertEqual(by_id[proj_claim["claim_id"]]["state"], "BLOCKED")

    def test_data_science_major_is_strong_for_related_cs_preference(self) -> None:
        from backend.services.evidence_matcher import EvidenceMatcher

        form = {
            "candidateId": "cand_local_draft",
            "education": [
                {
                    "id": "edu_ds",
                    "school": "华南理工大学",
                    "degree": "",
                    "major": "数据科学与大数据技术",
                    "start": "2024-09",
                    "end": "2028-09",
                }
            ],
            "internships": [],
            "projects": [],
            "awards": [],
        }
        experiences = experiences_from_resume_draft(form)
        requirement = {
            "requirement_id": "req_major",
            "type": "HARD",
            "category": "EDUCATION",
            "text": "本科及以上在读，计算机、人工智能、软件工程或相关专业优先",
            "normalized_terms": ["本科及以上在读", "计算机", "人工智能", "软件工程", "相关专业"],
            "evidence_text": "本科及以上在读，计算机、人工智能、软件工程或相关专业优先",
            "confidence": 0.9,
        }
        matcher = EvidenceMatcher()
        scored = matcher.score_linked_claims(
            requirement,
            matcher._requirement_terms(requirement),
            experiences[0],
            experiences[0]["claims"],
            semantic_score=0.6,
            model_rationale="属于计算机相关专业，但非精确匹配。",
            require_keyword_hit=False,
        )
        self.assertIsNotNone(scored)
        assert scored is not None
        self.assertEqual(scored["evidence_strength"], "STRONG")
        self.assertTrue(scored["ready_for_selection"])
        self.assertGreaterEqual(scored["score_breakdown"]["ai_score_10"], 9.0)
        self.assertIn("相关专业", scored["rationale"])


if __name__ == "__main__":
    unittest.main()
