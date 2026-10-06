import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONTRACTS = ROOT / "contracts"


def load(directory: Path, name: str) -> dict:
    with (directory / name).open("r", encoding="utf-8") as stream:
        return json.load(stream)


class ContractFixtureTests(unittest.TestCase):
    def test_all_contract_and_fixture_files_parse(self) -> None:
        self.assertEqual(len(list(CONTRACTS.glob("*.schema.json"))), 10)
        self.assertEqual(len(list(DATA.glob("*.example.json"))), 8)
        for path in [*CONTRACTS.glob("*.json"), *DATA.glob("*.json")]:
            with self.subTest(path=path.name):
                load(path.parent, path.name)

    def test_selected_claim_is_traceable_to_evidence(self) -> None:
        candidate = load(DATA, "candidate.example.json")
        selected = load(DATA, "resume-claims.example.json")["claims"][0]
        experience = candidate["experiences"][0]
        evidence_ids = {item["evidence_id"] for item in experience["evidence_sources"]}
        self.assertTrue(set(selected["evidence_ids"]).issubset(evidence_ids))
        self.assertGreater(selected["evidence_support_score"], 0)
        self.assertTrue(selected["selection_reason"])

    def test_requirement_keeps_source_text_and_confidence(self) -> None:
        parsed = load(DATA, "parsed-jd.example.json")
        for requirement in parsed["requirements"]:
            self.assertTrue(requirement["evidence_text"])
            self.assertGreaterEqual(requirement["confidence"], 0)
            self.assertLessEqual(requirement["confidence"], 1)

    def test_mapping_and_risk_require_confirmation(self) -> None:
        mapping = load(DATA, "form-mapping.example.json")
        risk = load(DATA, "risk-result.example.json")
        self.assertEqual(mapping["consistency_state"], "NEEDS_REVIEW")
        self.assertEqual(risk["action"], "REQUIRES_CONFIRMATION")
        self.assertTrue(risk["requires_human_confirmation"])


if __name__ == "__main__":
    unittest.main()
