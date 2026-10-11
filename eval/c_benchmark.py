"""Reproducible fictional C benchmark; no participant data or model claims hidden in scores."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from backend.services.claim_validator import ClaimValidator
from backend.services.jd_parser import JDParser, JDParseError
from backend.services.model_client import HttpModelClient


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "c_cases.json"
_ALIASES = {"automated tests": "automated testing", "data pipeline": "data pipelines"}


def _normalise(term: str) -> str:
    lowered = term.casefold()
    return _ALIASES.get(lowered, lowered)


def run(use_model: bool = False) -> dict:
    if use_model and not os.getenv("APPLYGUARD_AI_API_KEY"):
        raise RuntimeError("APPLYGUARD_AI_API_KEY is required for --model")
    with CASES.open(encoding="utf-8") as stream:
        benchmark = json.load(stream)
    with (ROOT / "data" / "career-vault.seed.json").open(encoding="utf-8") as stream:
        experiences = json.load(stream)["experiences"]
    parser = JDParser(HttpModelClient() if use_model else None)
    jd_results = []
    for case in benchmark["jd_cases"]:
        try:
            parsed, mode, failure = parser.parse(case["text"])
            actual = {_normalise(term) for item in parsed["requirements"] for term in item["normalized_terms"]}
            expected = {_normalise(term) for term in case["expected_terms"]}
            jd_results.append({"id": case["id"], "mode": mode, "expected": sorted(expected),
                               "actual": sorted(actual), "true_positive": len(expected & actual),
                               "false_positive": len(actual - expected), "false_negative": len(expected - actual),
                               "failure": failure})
        except JDParseError as exc:
            jd_results.append({"id": case["id"], "mode": "SAFE_STOP", "error": str(exc),
                               "true_positive": 0, "false_positive": 0,
                               "false_negative": len(case["expected_terms"])})
    claim_results = []
    validator = ClaimValidator()
    for case in benchmark["claim_cases"]:
        original = next(item for experience in experiences for item in experience["claims"]
                        if item["claim_id"] == case["claim_id"])
        candidate = {"claim_id": case["claim_id"], "text": case["text"],
                     "evidence_ids": original["evidence_ids"], "evidence_support_score": 0.9}
        result = validator.verify(candidate, experiences, "cand_demo_001")
        claim_results.append({"id": case["id"], "expected": case["expected_state"],
                              "actual": result["state"], "unsupported_fragments": result["unsupported_fragments"]})
    tp = sum(item["true_positive"] for item in jd_results)
    fp = sum(item["false_positive"] for item in jd_results)
    fn = sum(item["false_negative"] for item in jd_results)
    exact_claims = sum(item["expected"] == item["actual"] for item in claim_results)
    negatives = [item for item in claim_results if item["expected"] == "BLOCKED"]
    blocked = sum(item["actual"] == "BLOCKED" for item in negatives)
    accepted = sum(item["actual"] == "VERIFIED" for item in claim_results)
    positive = [item for item in claim_results if item["expected"] == "VERIFIED"]
    nonblocked = [item for item in claim_results if item["expected"] != "BLOCKED"]
    true_accepted = sum(item["actual"] == "VERIFIED" for item in positive)
    return {"model": "gpt-4o-mini" if use_model else None,
            "accepted_claim_precision": round(true_accepted / accepted, 4) if accepted else None,
            "supported_claim_acceptance_rate": round(true_accepted / len(positive), 4) if positive else None,
            "false_block_rate": round(sum(item["actual"] == "BLOCKED" for item in nonblocked) / len(nonblocked), 4),
            "review_rate": round(sum(item["actual"] == "NEEDS_REVIEW" for item in claim_results) / len(claim_results), 4),
            "claim_confusion_matrix": {expected: {actual: sum(item["expected"] == expected and item["actual"] == actual for item in claim_results)
                for actual in ("VERIFIED", "NEEDS_REVIEW", "BLOCKED")} for expected in ("VERIFIED", "NEEDS_REVIEW", "BLOCKED")},
            "dataset": "Fictional, hand-labelled C cases; not a user study",
            "mode": "MODEL_WITH_FALLBACK" if use_model else "RULE_FALLBACK_ONLY",
            "model_parsed_jds": sum(item["mode"].startswith("MODEL") for item in jd_results),
            "model_span_repaired_jds": sum(item["mode"] == "MODEL_SPAN_REPAIRED" for item in jd_results),
            "fallback_jds": sum(item["mode"] == "RULE_FALLBACK" for item in jd_results),
            "safe_stopped_jds": sum(item["mode"] == "SAFE_STOP" for item in jd_results),
            "jd_count": len(jd_results), "claim_count": len(claim_results),
            "jd_precision": round(tp / (tp + fp), 4) if tp + fp else 0,
            "jd_recall": round(tp / (tp + fn), 4) if tp + fn else 0,
            "claim_state_accuracy": round(exact_claims / len(claim_results), 4),
            "grounded_claim_rate": round(accepted / len(claim_results), 4),
            "unsupported_claim_block_rate": round(blocked / len(negatives), 4) if negatives else 0,
            "jd_cases": jd_results, "claim_cases": claim_results}


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--model", action="store_true", help="Use configured model API; may incur cost")
    args = argument_parser.parse_args()
    print(json.dumps(run(args.model), ensure_ascii=False, indent=2))
