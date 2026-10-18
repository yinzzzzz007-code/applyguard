import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.sag_auxiliary import SAGSearchClient, augment_match_with_sag
from backend.services.schema_validation import validate_contract


DATA = Path(__file__).resolve().parents[1] / "data"


class FakeSAG:
    source_id = "source_local_001"

    def __init__(self, hits=None, error=None):
        self.hits = hits or []
        self.error = error
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return copy.deepcopy(self.hits)


class SAGAuxiliaryTests(unittest.TestCase):
    def setUp(self):
        self.jd = json.loads((DATA / "parsed-jd.example.json").read_text(encoding="utf-8"))
        self.experiences = json.loads((DATA / "career-vault.seed.json").read_text(encoding="utf-8"))["experiences"]
        self.baseline = EvidenceMatcher().match(self.jd, self.experiences)
        self.manifest = {
            "candidate_id": self.baseline["candidate_id"],
            "source_id": FakeSAG.source_id,
            "links": [{"chunk_id": "chunk_api", "evidence_id": "ev_repo_api"}],
        }
        self.hit = {"source_id": FakeSAG.source_id, "chunk_id": "chunk_api", "score": 0.81}

    def test_off_is_identical_to_baseline(self):
        with patch.dict("os.environ", {"APPLYGUARD_SAG_MODE": "off"}):
            self.assertIs(augment_match_with_sag(self.jd, self.experiences, self.baseline), self.baseline)

    def test_shadow_links_only_existing_verified_evidence(self):
        result = augment_match_with_sag(self.jd, self.experiences, self.baseline,
                                        client=FakeSAG([self.hit]), manifest=self.manifest, mode="shadow")
        validate_contract("evidence-match", result)
        supported = result["matches"][0]
        self.assertEqual(supported["sag_support"][0]["evidence_id"], "ev_repo_api")
        self.assertEqual(supported["relevance_score"], self.baseline["matches"][0]["relevance_score"])
        self.assertEqual(result["sag_auxiliary"]["mode"], "shadow")
        self.assertNotIn("sag_support", self.baseline["matches"][0])

    def test_rerank_never_changes_readiness_or_evidence_ids(self):
        result = augment_match_with_sag(self.jd, self.experiences, self.baseline,
                                        client=FakeSAG([self.hit]), manifest=self.manifest, mode="rerank")
        validate_contract("evidence-match", result)
        original = {(m["requirement_id"], m["experience_id"]): m for m in self.baseline["matches"]}
        for match in result["matches"]:
            before = original[(match["requirement_id"], match["experience_id"])]
            self.assertEqual(match["ready_for_selection"], before["ready_for_selection"])
            self.assertEqual(match["evidence_ids"], before["evidence_ids"])
            self.assertEqual(match["evidence_strength"], before["evidence_strength"])
        self.assertGreater(result["matches"][0]["relevance_score"], self.baseline["matches"][0]["relevance_score"])

    def test_unmapped_foreign_and_unverified_hits_cannot_boost(self):
        self.manifest["links"].extend([
            {"chunk_id": "unverified", "evidence_id": "does_not_exist"},
            {"chunk_id": "weak", "evidence_id": "ev_pipeline_repo"},
        ])
        hits = [
            {"source_id": "foreign_source", "chunk_id": "chunk_api", "score": 1.0},
            {"source_id": FakeSAG.source_id, "chunk_id": "unverified", "score": 1.0},
            {"source_id": FakeSAG.source_id, "chunk_id": "weak", "score": 1.0},
        ]
        result = augment_match_with_sag(self.jd, self.experiences, self.baseline,
                                        client=FakeSAG(hits), manifest=self.manifest, mode="rerank")
        validate_contract("evidence-match", result)
        self.assertEqual([m["relevance_score"] for m in result["matches"]],
                         [m["relevance_score"] for m in self.baseline["matches"]])
        self.assertFalse(next(m for m in result["matches"] if m["experience_id"] == "exp_data_pipeline")["ready_for_selection"])

    def test_candidate_mismatch_and_search_error_fall_back(self):
        foreign = {**self.manifest, "candidate_id": "cand_foreign"}
        self.assertIs(augment_match_with_sag(self.jd, self.experiences, self.baseline,
                                            client=FakeSAG([self.hit]), manifest=foreign, mode="rerank"), self.baseline)
        self.assertIs(augment_match_with_sag(self.jd, self.experiences, self.baseline,
                                            client=FakeSAG(error=OSError("offline")),
                                            manifest=self.manifest, mode="rerank"), self.baseline)

    def test_ambiguous_chunk_mapping_fails_closed(self):
        manifest = {**self.manifest, "links": self.manifest["links"] +
                    [{"chunk_id": "chunk_api", "evidence_id": "ev_test_report"}]}
        self.assertIs(augment_match_with_sag(self.jd, self.experiences, self.baseline,
                                            client=FakeSAG([self.hit]), manifest=manifest, mode="rerank"), self.baseline)

    def test_malformed_manifest_and_duplicate_evidence_ids_fail_closed(self):
        bad_manifest = {**self.manifest, "links": None}
        self.assertIs(augment_match_with_sag(self.jd, self.experiences, self.baseline,
                                            client=FakeSAG([self.hit]), manifest=bad_manifest, mode="rerank"), self.baseline)
        experiences = copy.deepcopy(self.experiences)
        experiences[1]["evidence_sources"][0]["evidence_id"] = "ev_repo_api"
        self.assertIs(augment_match_with_sag(self.jd, experiences, self.baseline,
                                            client=FakeSAG([self.hit]), manifest=self.manifest, mode="rerank"), self.baseline)

    def test_client_requires_loopback(self):
        with self.assertRaises(ValueError):
            SAGSearchClient("https://example.com", "source", "token")

    def test_client_uses_source_scoped_sag_api(self):
        with patch("backend.services.sag_auxiliary.urlopen") as opened:
            opened.return_value.__enter__.return_value.read.return_value = b'{"sections": [{"chunk_id": "c1"}]}'
            hits = SAGSearchClient("http://127.0.0.1:8001", "source_1", "secret").search("Python API")
        self.assertEqual(hits[0]["chunk_id"], "c1")
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8001/api/v1/sources/source_1/search")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(json.loads(request.data)["strategy"], "multi")

    def test_client_rejects_malformed_or_oversized_response(self):
        with patch("backend.services.sag_auxiliary.urlopen") as opened:
            opened.return_value.__enter__.return_value.read.return_value = b'{"wrong": []}'
            with self.assertRaises(ValueError):
                SAGSearchClient("http://localhost:8001", "source", "secret").search("query")
            opened.return_value.__enter__.return_value.read.return_value = b"x" * 2_000_001
            with self.assertRaises(ValueError):
                SAGSearchClient("http://localhost:8001", "source", "secret").search("query")


if __name__ == "__main__":
    unittest.main()
