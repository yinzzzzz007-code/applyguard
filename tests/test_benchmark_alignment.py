import json
import unittest

from eval.build_c_cases_zh import SEED, TARGET, build


class BenchmarkAlignmentTests(unittest.TestCase):
    def test_frozen_chinese_claim_cases_match_current_seed_and_labels(self) -> None:
        generated = build()
        frozen = json.loads(TARGET.read_text(encoding="utf-8"))
        self.assertEqual(frozen, generated)
        originals = {claim["claim_id"]: claim["text"] for exp in json.loads(SEED.read_text(encoding="utf-8"))["experiences"] for claim in exp["claims"]}
        counts = {state: sum(case["expected_state"] == state for case in frozen["claim_cases"])
                  for state in ("VERIFIED", "NEEDS_REVIEW", "BLOCKED")}
        self.assertEqual(counts, {"VERIFIED": 4, "NEEDS_REVIEW": 8, "BLOCKED": 28})
        for case in frozen["claim_cases"]:
            if case["expected_state"] == "VERIFIED":
                self.assertEqual(case["text"], originals[case["claim_id"]])
        self.assertEqual(len({case["id"] for case in frozen["claim_cases"]}), 40)
