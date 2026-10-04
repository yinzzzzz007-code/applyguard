import copy
import json
import re
import unittest
from pathlib import Path
from typing import Any

from backend.app import build_mock_workflow
from backend.services.career_vault import CareerVault, JsonCareerVaultRepository
from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.resume_selector import ResumeSelector


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONTRACTS = ROOT / "contracts"


def load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def assert_schema(test: unittest.TestCase, value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Small standard-library validator for the frozen contract features used here."""
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    if types:
        test.assertTrue(any(checks[item_type](value) for item_type in types), f"{path} has wrong type")
    if "enum" in schema:
        test.assertIn(value, schema["enum"], f"{path} is outside enum")
    if isinstance(value, str):
        if "minLength" in schema:
            test.assertGreaterEqual(len(value), schema["minLength"], f"{path} is too short")
        if "pattern" in schema:
            test.assertRegex(value, re.compile(schema["pattern"]), f"{path} fails pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema:
            test.assertGreaterEqual(value, schema["minimum"], f"{path} is below minimum")
        if "maximum" in schema:
            test.assertLessEqual(value, schema["maximum"], f"{path} is above maximum")
    if isinstance(value, list):
        if "minItems" in schema:
            test.assertGreaterEqual(len(value), schema["minItems"], f"{path} has too few items")
        if schema.get("uniqueItems"):
            test.assertEqual(len(value), len({json.dumps(item, sort_keys=True) for item in value}), f"{path} is not unique")
        if "items" in schema:
            for index, item in enumerate(value):
                assert_schema(test, item, schema["items"], f"{path}[{index}]")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            test.assertIn(name, value, f"{path}.{name} is required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            test.assertTrue(set(value).issubset(properties), f"{path} has unsupported properties")
        for name, item in value.items():
            if name in properties:
                assert_schema(test, item, properties[name], f"{path}.{name}")


class MemberBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vault = CareerVault.from_json(DATA / "career-vault.seed.json")
        cls.experiences = cls.vault.list_experiences("cand_demo_001")
        cls.matcher = EvidenceMatcher()
        cls.selector = ResumeSelector()
        cls.base_jd = load(DATA / "parsed-jd.example.json")
        cls.benchmark = load(DATA / "benchmarks" / "fixed-jd-benchmark.json")

    def test_career_vault_reads_structured_fictional_experiences(self) -> None:
        self.assertEqual(len(self.experiences), 4)
        api = self.vault.get_experience("cand_demo_001", "exp_api_course_project")
        self.assertEqual(api["title"], "后端开发")
        self.assertTrue(api["responsibilities"])
        self.assertEqual(api["evidence_sources"][0]["source_type"], "REPOSITORY")
        self.assertEqual(api["evidence_sources"][0]["verification_status"], "VERIFIED")
        self.assertNotIn("calculation", api["metrics"][0])
        self.assertEqual(api["metrics"][1]["calculation"]["displayed_percent"], 100)

    def test_career_vault_rejects_broken_evidence_links(self) -> None:
        seed = load(DATA / "career-vault.seed.json")
        for mutate in (
            lambda item: item["claims"][0].update(evidence_ids=[]),
            lambda item: item["metrics"][0].update(evidence_ids=["ev_missing"]),
            lambda item: item["evidence_sources"][0].update(source_type="DOCUMENT"),
        ):
            with self.subTest(mutate=mutate):
                payload = copy.deepcopy(seed)
                mutate(payload["experiences"][0])
                with self.assertRaises(ValueError):
                    JsonCareerVaultRepository._validate(payload)

    def test_vault_accepts_complete_structured_metric_arithmetic(self) -> None:
        seed = load(DATA / "career-vault.seed.json")
        for calculation in (
            {"numerator": 12, "denominator": 12, "displayed_percent": 100},
            {"baseline": 100, "result": 125, "change_type": "relative_percent", "displayed_change": 25},
            {"baseline": 60, "result": 70, "change_type": "percentage_points", "displayed_change": 10},
            {"numerator": 12, "denominator": 12, "displayed_percent": 100,
             "baseline": 60, "result": 70, "change_type": "percentage_points", "displayed_change": 10},
        ):
            with self.subTest(calculation=calculation):
                payload = copy.deepcopy(seed)
                payload["experiences"][0]["metrics"][1]["calculation"] = calculation
                JsonCareerVaultRepository._validate(payload)

    def test_vault_rejects_inconsistent_or_incomplete_metric_arithmetic(self) -> None:
        seed = load(DATA / "career-vault.seed.json")
        for calculation in (
            {"numerator": 12, "denominator": 12, "displayed_percent": 80},
            {"numerator": 12, "denominator": 0, "displayed_percent": 100},
            {"numerator": 12, "denominator": 12},
            {"baseline": 100, "result": 125, "change_type": "relative_percent", "displayed_change": 20},
            {"baseline": 0, "result": 125, "change_type": "relative_percent", "displayed_change": 25},
            {"baseline": 60, "result": 70, "change_type": "percentage_points", "displayed_change": 16.67},
            {"baseline": 60, "result": 70, "change_type": "percentage_points"},
            {"numerator": True, "denominator": 12, "displayed_percent": 100},
            {"numerator": float("nan"), "denominator": 12, "displayed_percent": 100},
            {"numerator": float("inf"), "denominator": 12, "displayed_percent": 100},
            {"numerator": "12", "denominator": 12, "displayed_percent": 100},
            {"numerator": 12, "denominator": 12, "displayed_percent": 100, "unexpected": 1},
            None,
        ):
            with self.subTest(calculation=calculation):
                payload = copy.deepcopy(seed)
                payload["experiences"][0]["metrics"][1]["calculation"] = calculation
                with self.assertRaises(ValueError):
                    JsonCareerVaultRepository._validate(payload)

    def test_strong_experience_ranks_before_weaker_overlap(self) -> None:
        backend_case = self.benchmark["cases"][0]
        result = self.matcher.match(backend_case["parsed_jd"], self.experiences)
        api_matches = [item for item in result["matches"] if item["requirement_id"] == "req_backend_python_api"]
        self.assertEqual(api_matches[0]["experience_id"], "exp_api_course_project")
        self.assertGreater(api_matches[0]["relevance_score"], api_matches[1]["relevance_score"])
        self.assertIn("ev_repo_api", api_matches[0]["evidence_ids"])

    def test_selected_claim_keeps_evidence_ids(self) -> None:
        matches = self.matcher.match(self.base_jd, self.experiences)
        selected = self.selector.select(matches, self.experiences, "app_test_001", max_claims=1)
        self.assertEqual(selected.claims[0]["claim_id"], "claim_python_api")
        self.assertTrue(selected.claims[0]["evidence_ids"])
        self.assertIn("ev_repo_api", selected.claims[0]["evidence_ids"])

    def test_mock_fixture_claim_references_follow_computed_selection(self) -> None:
        response = build_mock_workflow(
            {"candidate_id": "cand_demo_001", "jd_text": "Fictional Python backend role with HTTP APIs and tests.", "parse_mode": "fixture"}
        )
        selected_ids = {claim["claim_id"] for claim in response["resume_claims"]}
        self.assertEqual(selected_ids, {item["claim_id"] for item in response["claim_verification"]})
        for field in response["ats_form_mapping"]["fields"]:
            self.assertTrue(set(field["source_claim_ids"]).issubset(selected_ids))
        self.assertEqual(response["execution_mode"], "DETERMINISTIC_FIXTURE")
        self.assertIn("not dynamically parsed", response["mock_notice"])

    def test_insufficient_evidence_is_not_selected_as_high_confidence_claim(self) -> None:
        insufficient = copy.deepcopy(self.experiences[0])
        insufficient["evidence_sources"] = []
        insufficient["metrics"] = []
        matches = self.matcher.match(self.base_jd, [insufficient])
        selected = self.selector.select(matches, [insufficient], "app_test_002")
        self.assertFalse(selected.claims)
        self.assertTrue(any("INSUFFICIENT_EVIDENCE" in item["reason"] for item in selected.removed_claims))

    def test_conflicting_evidence_reduces_score_and_requires_review(self) -> None:
        verified = self.matcher.match(self.base_jd, [self.experiences[0]])
        conflicted_experience = copy.deepcopy(self.experiences[0])
        conflicted_experience["evidence_sources"][0]["verification_status"] = "CONFLICTING"
        conflicted = self.matcher.match(self.base_jd, [conflicted_experience])
        verified_score = verified["matches"][0]["relevance_score"]
        conflicted_match = conflicted["matches"][0]
        self.assertLess(conflicted_match["relevance_score"], verified_score)
        self.assertTrue(conflicted_match["conflicts"])
        selected = self.selector.select(conflicted, [conflicted_experience], "app_test_003")
        self.assertFalse(selected.claims)
        self.assertTrue(any(item["reason"].startswith("CONFLICT") for item in selected.removed_claims))

    def test_duplicate_claim_is_removed(self) -> None:
        experience = copy.deepcopy(self.experiences[0])
        duplicate = copy.deepcopy(experience["claims"][0])
        duplicate["claim_id"] = "claim_python_api_duplicate"
        experience["claims"].append(duplicate)
        matches = self.matcher.match(self.base_jd, [experience])
        selected = self.selector.select(matches, [experience], "app_test_004")
        self.assertEqual(len(selected.claims), 1)
        self.assertTrue(any(item["reason"].startswith("REDUNDANT") for item in selected.removed_claims))

    def test_claim_count_and_length_budgets_apply(self) -> None:
        experience = copy.deepcopy(self.experiences[0])
        second = copy.deepcopy(experience["claims"][0])
        second["claim_id"] = "claim_api_integration_checks"
        second["text"] = "Implemented Python HTTP API routes and documented automated testing outcomes."
        experience["claims"].append(second)
        matches = self.matcher.match(self.base_jd, [experience])
        count_limited = self.selector.select(matches, [experience], "app_test_005", max_claims=1, max_characters=420)
        self.assertEqual(len(count_limited.claims), 1)
        self.assertTrue(any(item["reason"].startswith("CLAIM_LIMIT") for item in count_limited.removed_claims))
        length_limited = self.selector.select(matches, [experience], "app_test_006", max_claims=3, max_characters=10)
        self.assertFalse(length_limited.claims)
        self.assertTrue(any(item["reason"].startswith("LENGTH_LIMIT") for item in length_limited.removed_claims))

    def test_unrelated_claim_does_not_cover_a_skill_only_in_experience(self) -> None:
        experience = copy.deepcopy(self.experiences[0])
        experience["skills"].append("CUDA")
        parsed_jd = {
            "jd_id": "jd_cuda_gap",
            "requirements": [{"requirement_id": "req_cuda", "normalized_terms": ["CUDA"]}],
        }
        matches = self.matcher.match(parsed_jd, [experience])
        self.assertFalse(matches["matches"])
        self.assertEqual(matches["uncovered_requirements"][0]["requirement_id"], "req_cuda")
        self.assertFalse(self.selector.select(matches, [experience], "app_cuda_gap").claims)

    def test_generic_api_or_fine_tuning_does_not_imply_specialized_skill(self) -> None:
        experience = copy.deepcopy(self.experiences[0])
        experience["skills"].append("LLM fine-tuning")
        experience["claims"][0]["text"] = "Built an API and fine-tuned a scheduler."
        parsed_jd = {
            "jd_id": "jd_overbroad_aliases",
            "requirements": [
                {"requirement_id": "req_http_api", "normalized_terms": ["HTTP API"]},
                {"requirement_id": "req_llm_fine_tuning", "normalized_terms": ["LLM fine-tuning"]},
            ],
        }
        matches = self.matcher.match(parsed_jd, [experience])
        self.assertFalse(matches["matches"])
        self.assertEqual(
            {item["requirement_id"] for item in matches["uncovered_requirements"]},
            {"req_http_api", "req_llm_fine_tuning"},
        )

    def test_partial_requirement_stays_uncovered(self) -> None:
        experience = copy.deepcopy(self.experiences[0])
        experience["skills"].append("CUDA")
        parsed_jd = {
            "jd_id": "jd_partial_cuda",
            "requirements": [{"requirement_id": "req_python_cuda", "normalized_terms": ["Python", "CUDA"]}],
        }
        matches = self.matcher.match(parsed_jd, [experience])
        self.assertTrue(matches["matches"])
        self.assertFalse(matches["matches"][0]["ready_for_selection"])
        self.assertIn("cuda", " ".join(matches["matches"][0]["missing_evidence"]))
        self.assertFalse(self.selector.select(matches, [experience], "app_partial_cuda").claims)

    def test_verified_claim_without_metric_can_still_be_selected(self) -> None:
        experience = copy.deepcopy(self.experiences[0])
        experience["metrics"] = []
        matches = self.matcher.match(self.base_jd, [experience])
        selected = self.selector.select(matches, [experience], "app_no_metric")
        self.assertTrue(selected.claims)
        self.assertNotIn("quantified outcome", selected.claims[0]["selection_reason"])

    def test_selector_refills_after_duplicate_and_length_rejection(self) -> None:
        experience = copy.deepcopy(self.experiences[0])
        duplicate = copy.deepcopy(experience["claims"][0])
        duplicate["claim_id"] = "claim_api_duplicate"
        short = copy.deepcopy(experience["claims"][0])
        short["claim_id"] = "claim_short_python"
        short["text"] = "Built Python APIs."
        experience["claims"].extend([duplicate, short])
        matches = self.matcher.match(self.base_jd, [experience])
        result = self.selector.select(matches, [experience], "app_refill", max_claims=2, max_characters=90)
        self.assertEqual(len(result.claims), 2)
        self.assertTrue(any(item["reason"].startswith("REDUNDANT") for item in result.removed_claims))
        result_tight = self.selector.select(matches, [experience], "app_refill_tight", max_claims=1, max_characters=20)
        self.assertEqual([claim["claim_id"] for claim in result_tight.claims], ["claim_short_python"])
        self.assertTrue(any(item["reason"].startswith("LENGTH_LIMIT") for item in result_tight.removed_claims))

    def test_same_input_produces_same_output(self) -> None:
        first_match = self.matcher.match(self.base_jd, self.experiences)
        second_match = self.matcher.match(self.base_jd, self.experiences)
        self.assertEqual(first_match, second_match)
        self.assertEqual(
            self.selector.select(first_match, self.experiences, "app_test_007"),
            self.selector.select(second_match, self.experiences, "app_test_007"),
        )

    def test_all_five_fixed_benchmark_cases_run(self) -> None:
        self.assertEqual(len(self.benchmark["cases"]), 5)
        for case in self.benchmark["cases"]:
            with self.subTest(jd_id=case["jd_id"]):
                result = self.matcher.match(case["parsed_jd"], self.experiences)
                selected = self.selector.select(result, self.experiences, "app_benchmark_001")
                matched_ids = {match["experience_id"] for match in result["matches"]}
                for experience_id in case["expected_strong_experience_ids"]:
                    self.assertIn(experience_id, matched_ids)
                    self.assertTrue(any(match["experience_id"] == experience_id and match["evidence_strength"] == "STRONG" for match in result["matches"]))
                for experience_id in case["expected_weak_or_unmatched_experience_ids"]:
                    self.assertFalse(any(match["experience_id"] == experience_id and match["evidence_strength"] == "STRONG" for match in result["matches"]))
                uncovered_ids = {item["requirement_id"] for item in result["uncovered_requirements"]}
                self.assertEqual(set(case["expected_insufficient_requirements"]), uncovered_ids)
                if not case["expected_strong_experience_ids"]:
                    self.assertFalse(selected.claims)

    def test_b_outputs_follow_frozen_schemas_with_compatible_extensions(self) -> None:
        evidence_schema = load(CONTRACTS / "evidence-match.schema.json")
        claim_schema = load(CONTRACTS / "resume-claim.schema.json")
        experience_schema = load(CONTRACTS / "experience.schema.json")
        for experience in self.experiences:
            assert_schema(self, experience, experience_schema)
        matches = self.matcher.match(self.base_jd, self.experiences)
        assert_schema(self, matches, evidence_schema)
        selected = self.selector.select(matches, self.experiences, "app_test_008", max_claims=1)
        for claim in selected.claims:
            assert_schema(self, claim, claim_schema)


if __name__ == "__main__":
    unittest.main()
