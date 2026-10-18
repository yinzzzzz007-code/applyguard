"""Run a small, reproducible FELM/CRAG pilot without storing source datasets.

FELM is downloaded to memory only when --felm-zip is omitted. CRAG is read
from the official repository's checked-in 10-row example file. This script
does not run CRAG's LLM judge or claim that either dataset measures resume/JD
matching validity.
"""

from __future__ import annotations

import argparse
import bz2
import hashlib
import io
import json
import random
import re
import sys
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FELM_URL = "https://huggingface.co/datasets/sjtu-lit/felm/resolve/main/data.zip"
FELM_DOMAINS = ("wk", "science", "math", "reasoning", "writing_rec")
SEED = 20261018
STOP_WORDS = set(
    "the a an in on of for to with from is are was were did do does has have what which who "
    "how many much more most than between and or that this it its as per average days year "
    "first second least total".split()
)


def _read_felm(path: Path | None) -> tuple[bytes, dict[str, list[dict[str, Any]]], dict[str, int]]:
    if path is None:
        with urllib.request.urlopen(FELM_URL, timeout=45) as response:
            archive_bytes = response.read()
    else:
        archive_bytes = path.read_bytes()
    by_domain: dict[str, list[dict[str, Any]]] = {}
    excluded: dict[str, int] = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for domain in FELM_DOMAINS:
            rows = [
                json.loads(line)
                for line in archive.read(f"data/test/{domain}.jsonl").decode("utf-8").splitlines()
                if line.strip()
            ]
            cases: list[dict[str, Any]] = []
            malformed = 0
            for row in rows:
                segments = row.get("segmented_response", [])
                labels = row.get("labels", [])
                comments = row.get("comment", [])
                if not segments or len(labels) != len(segments) or len(comments) != len(segments):
                    malformed += 1
                    continue
                refs, error_types = row.get("ref", []), row.get("type", [])
                for index, label in enumerate(labels):
                    comment = str(comments[index] or "")
                    # Error cases need the dataset's own correction note; positive
                    # cases are sampled from the factual labels.
                    if label is False and not comment.strip():
                        continue
                    reference = refs[0] if len(refs) == 1 else refs[index] if len(refs) == len(segments) else None
                    error_type = error_types[0] if len(error_types) == 1 else (
                        error_types[index] if len(error_types) == len(segments) else None
                    )
                    cases.append(
                        {
                            "domain": domain,
                            "record_id": str(row["index"]),
                            "segment_index": index,
                            "label": bool(label),
                            "segment": segments[index],
                            "comment": comment,
                            "reference": reference,
                            "error_type": error_type,
                        }
                    )
            by_domain[domain] = cases
            excluded[domain] = malformed
    return archive_bytes, by_domain, excluded


def _sample_felm(by_domain: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    for domain in FELM_DOMAINS:
        cases = by_domain[domain]
        for label in (False, True):
            candidates = [case for case in cases if case["label"] is label]
            rng.shuffle(candidates)
            if len(candidates) < 2:
                raise ValueError(f"FELM {domain} has fewer than two label={label} cases")
            selected.extend(candidates[:2])
    return selected


def _felm_validator_results(cases: list[dict[str, Any]]) -> tuple[Counter, list[dict[str, Any]]]:
    from backend.services.claim_validator import ClaimValidator

    counts: Counter = Counter()
    rows: list[dict[str, Any]] = []
    validator = ClaimValidator()
    for ordinal, case in enumerate(cases):
        evidence_id = f"ev_felm_{ordinal}"
        claim_id = f"claim_felm_{ordinal}"
        candidate_id = "cand_felm_sample"
        experience = {
            "experience_id": f"exp_felm_{ordinal}",
            "candidate_id": candidate_id,
            "organization": "Synthetic FELM test record",
            "role": "Test claim",
            "summary": case["segment"],
            "responsibilities": [],
            "skills": [],
            "metrics": [],
            "claims": [
                {
                    "claim_id": claim_id,
                    "text": case["segment"],
                    "evidence_ids": [evidence_id],
                    "confidence": 0.95,
                    "verification_state": "VERIFIED",
                }
            ],
            "evidence_sources": [
                {
                    "evidence_id": evidence_id,
                    "type": "REFERENCE",
                    "description": (
                        f"Annotation correction: {case['comment']}"
                        if not case["label"]
                        else f"Source assertion: {case['segment']}"
                    ),
                    "source_reference": case["reference"],
                    "confidence": 0.95,
                    "verification_status": "VERIFIED",
                }
            ],
            "verification_state": "VERIFIED",
        }
        result = validator.verify(
            {
                "claim_id": claim_id,
                "text": case["segment"],
                "evidence_ids": [evidence_id],
                "evidence_support_score": 0.95,
            },
            [experience],
            candidate_id,
        )
        expected = "FACT" if case["label"] else "ERROR"
        counts[(expected, result["state"])] += 1
        rows.append(
            {
                "domain": case["domain"],
                "record_id": case["record_id"],
                "segment_index": case["segment_index"],
                "expected": expected,
                "error_type": case["error_type"],
                "actual_state": result["state"],
            }
        )
    return counts, rows


def _read_crag(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    raw = path.read_bytes()
    with bz2.open(io.BytesIO(raw), "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    return raw, rows


def _crag_distractor_results(rows: list[dict[str, Any]]) -> tuple[Counter, Counter, list[str]]:
    from backend.services.evidence_matcher import EvidenceMatcher

    seed_path = ROOT / "data" / "career-vault.seed.json"
    experiences = json.loads(seed_path.read_text(encoding="utf-8"))["experiences"]
    matcher = EvidenceMatcher()
    counts: Counter = Counter()
    distribution: Counter = Counter()
    ids: list[str] = []
    for row in rows:
        interaction_id = row["interaction_id"]
        suffix = interaction_id.replace("-", "_")
        terms = sorted(
            {
                token.lower().strip("-.")
                for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", row["query"])
                if token.lower().strip("-.") not in STOP_WORDS
            }
        )
        parsed_jd = {
            "jd_id": f"jd_crag_{suffix}",
            "requirements": [
                {
                    "requirement_id": f"req_crag_{suffix}",
                    "text": row["query"],
                    "normalized_terms": terms,
                }
            ],
        }
        result = matcher.match(parsed_jd, experiences)
        counts["questions"] += 1
        counts["with_any_match"] += bool(result["matches"])
        counts["ready_matches"] += sum(match["ready_for_selection"] for match in result["matches"])
        counts["uncovered"] += any(
            item["requirement_id"] == f"req_crag_{suffix}"
            for item in result.get("uncovered_requirements", [])
        )
        distribution[(row["domain"], row["question_type"])] += 1
        ids.append(interaction_id)
    return counts, distribution, ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--felm-zip", type=Path, help="FELM data.zip; omitted means download 260 KB archive to memory")
    parser.add_argument(
        "--crag-bz2",
        type=Path,
        default=ROOT.parent / "upstream-references" / "related-work" / "CRAG" / "example_data" / "dev_data.jsonl.bz2",
    )
    args = parser.parse_args()
    if not args.crag_bz2.is_file():
        parser.error(f"CRAG example file not found: {args.crag_bz2}; pass --crag-bz2 explicitly")

    felm_bytes, by_domain, excluded = _read_felm(args.felm_zip)
    felm_sample = _sample_felm(by_domain)
    felm_counts, felm_cases = _felm_validator_results(felm_sample)
    crag_bytes, crag_rows = _read_crag(args.crag_bz2)
    crag_counts, crag_dist, crag_ids = _crag_distractor_results(crag_rows)

    report = {
        "sampling_seed": SEED,
        "felm": {
            "source": FELM_URL,
            "archive_sha256": hashlib.sha256(felm_bytes).hexdigest(),
            "archive_bytes": len(felm_bytes),
            "selected_cases": len(felm_cases),
            "per_domain_excluded_misaligned_records": excluded,
            "outcomes": {f"{expected}:{state}": count for (expected, state), count in sorted(felm_counts.items())},
            "sample_ids": felm_cases,
            "note": "Synthetic Vault adapter: source descriptions contain FELM correction comments or factual segments.",
        },
        "crag": {
            "source_file": str(args.crag_bz2),
            "file_sha256": hashlib.sha256(crag_bytes).hexdigest(),
            "selected_cases": len(crag_rows),
            "outcomes": dict(crag_counts),
            "domain_question_type_distribution": {
                f"{domain}:{question_type}": count
                for (domain, question_type), count in sorted(crag_dist.items())
            },
            "interaction_ids": crag_ids,
            "note": "Out-of-domain QA questions tested as distractor requirements against the fictional Career Vault.",
        },
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
