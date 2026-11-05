"""AI evidence matching: ID-grounded scoring with deterministic evidence gates."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from backend.services.ai_evidence_matcher import augment_match_with_ai, merge_ai_match
from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.model_client import ModelFailure
from backend.services.schema_validation import validate_contract


ROOT = Path(__file__).resolve().parents[1]


class FakeModel:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def complete_json(self, *_):
        self.calls += 1
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class AIEvidenceMatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        vault = json.loads((ROOT / "data" / "career-vault.seed.json").read_text(encoding="utf-8"))
        cls.experiences = [item for item in vault["experiences"] if item["candidate_id"] == "cand_demo_001"]
        cls.parsed = json.loads((ROOT / "data" / "parsed-jd.example.json").read_text(encoding="utf-8"))
        cls.baseline = EvidenceMatcher().match(cls.parsed, cls.experiences)

    def test_ai_boosts_with_existing_claim_ids_only(self) -> None:
        claim = self.experiences[0]["claims"][0]
        req_id = self.parsed["requirements"][0]["requirement_id"]
        raw = {
            "scores": [{
                "requirement_id": req_id,
                "experience_id": self.experiences[0]["experience_id"],
                "claim_ids": [claim["claim_id"]],
                "score": 9.2,
                "rationale": "Claim covers the API requirement.",
            }]
        }
        merged = merge_ai_match(self.parsed, self.experiences, self.baseline, raw)
        validate_contract("evidence-match", merged)
        self.assertEqual(merged["ai_match"]["mode"], "MODEL")
        row = next(item for item in merged["matches"] if item["requirement_id"] == req_id)
        self.assertEqual(row["claim_ids"], [claim["claim_id"]])
        self.assertGreaterEqual(row["relevance_score"], 0.65)
        self.assertGreaterEqual(row["score_breakdown"]["ai_score_10"], 9.2)
        self.assertGreaterEqual(row["score_breakdown"]["ai_semantic_score"], 0.92)

    def test_invented_claim_id_is_rejected_and_falls_back(self) -> None:
        model = FakeModel({
            "scores": [{
                "requirement_id": self.parsed["requirements"][0]["requirement_id"],
                "experience_id": self.experiences[0]["experience_id"],
                "claim_ids": ["claim_does_not_exist"],
                "score": 9.9,
                "rationale": "Fabricated",
            }]
        })
        result = augment_match_with_ai(self.parsed, self.experiences, copy.deepcopy(self.baseline), model)
        self.assertEqual(result["ai_match"]["mode"], "RULE_FALLBACK")
        self.assertEqual(len(result["matches"]), len(self.baseline["matches"]))
        self.assertEqual(model.calls, 1)

    def test_model_failure_keeps_baseline(self) -> None:
        model = FakeModel(ModelFailure("timeout"))
        result = augment_match_with_ai(self.parsed, self.experiences, copy.deepcopy(self.baseline), model)
        self.assertEqual(result["ai_match"]["mode"], "RULE_FALLBACK")
        self.assertIn("timeout", result["ai_match"]["failure"])

    def test_disabled_or_missing_model_returns_baseline_unchanged(self) -> None:
        plain = augment_match_with_ai(self.parsed, self.experiences, copy.deepcopy(self.baseline), None)
        self.assertIsNone(plain.get("ai_match"))
        self.assertEqual(plain["matches"], self.baseline["matches"])


if __name__ == "__main__":
    unittest.main()
