"""Replay the source-bound fact lock against dated, cached model outputs."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.fact_lock import locked_edit_findings, source_bound_ledger
from scripts.evaluate_asu_ablation import fixture
REVIEW = ROOT / "output/test-reports/20261030_172733_803092_asu-reviewed-replay/report.json"
RUN = ROOT / "output/test-reports/20261030_165352_150056_asu-ablation-60"


def main():
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    checks = {}
    for file in RUN.glob("batch-*/original-checks.json"):
        for cid, row in json.loads(file.read_text(encoding="utf-8")).items():
            checks[cid] = row
    counts = Counter()
    dataset = {row["id"]: row for row in json.loads(
        (RUN / "dataset.json").read_text(encoding="utf-8"))}
    for cid, check in checks.items():
        if check.get("relation") != "SUPPORTED":
            continue
        claims, _, hits = fixture([dataset[cid.removeprefix("claim_")]])
        ledger = source_bound_ledger(claims[0]["text"], check, hits[cid])
        counts["supported_originals"] += 1
        counts["supported_atoms"] += sum(a.get("relation") == "SUPPORTED"
                                          for a in check.get("atoms", []))
        counts["source_bound_atoms"] += len(ledger)
    records = []
    for row in review["records"]:
        assert hashlib.sha256(row["proposal"].encode()).hexdigest() == row["text_sha256"]
        cid = "claim_" + row["id"]
        original_check = checks.get(cid)
        findings = locked_edit_findings(row["original"], row["proposal"], original_check)
        old = row.get("replayed_v3_accept")
        new = old and not findings if old is not None else None
        label = row["label"]
        if label not in {"SAFE", "WRONG", "AMBIGUOUS"}:
            raise ValueError("Unexpected review label")
        counts["all"] += 1
        counts["label_" + label] += 1
        if findings:
            counts["lock_flagged_" + label] += 1
        if old is not None and label != "AMBIGUOUS":
            counts["fully_checked"] += 1
            counts["old_accept_" + label] += bool(old)
            counts["new_accept_" + label] += bool(new)
        records.append({
            "id": row["id"], "arm": row["arm"], "label": label,
            "original_supported": original_check is not None and
                                  original_check.get("relation") == "SUPPORTED",
            "changed": row["changed"], "findings": findings,
            "old_accept": old, "new_accept": new,
            "proposal_sha256": row["text_sha256"],
        })
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    out = ROOT / "output/test-reports" / (
        now.strftime("%Y%m%d_%H%M%S_%f") + "_fact-lock-replay")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "date": now.isoformat(), "status": "COMPLETE_OFFLINE_REPLAY",
        "source_report_sha256": hashlib.sha256(REVIEW.read_bytes()).hexdigest(),
        "source_run": str(RUN.relative_to(ROOT)),
        "label_origin": review.get("limitations", []),
        "counts": dict(sorted(counts.items())), "records": records,
        "limitations": [
            "Same outputs used for diagnosing guard rules: not an independent test set.",
            "Labels were reviewed by Codex, not independently annotated by humans.",
            "No new model generation, no SAG retrieval comparison and no paid calls.",
            "Only complete cached pipeline outcomes enter old/new acceptance counts.",
        ],
    }
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Source-bound fact lock: cached-output replay",
        "", "Date: " + now.isoformat(), "",
        "This is an offline diagnostic on the existing 57 outputs. "
        "It does not establish a reduction in future model errors.",
        "", "Counts: " + json.dumps(report["counts"], ensure_ascii=False), "",
        "The new guard requires the original to be fully supported, preserves "
        "qualifiers, quantities, technology and explicit attribution, and leaves "
        "ordinary restyling to the existing atomic verifier.",
        "", "Labels are Codex-reviewed and require independent human review.", "",
    ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    # The independent reviewer receives no prior label or automatic decision.
    worksheet = ROOT / "eval/asu_ablation/fact-lock-human-review-2026-10-31.json"
    queue = []
    for row in sorted(review["records"], key=lambda item: item["text_sha256"]):
            queue.append({
                "sample_id": hashlib.sha256((row["id"] + ":" + row["arm"]).encode()).hexdigest()[:16],
                "source_original": dataset[row["id"]]["source"],
                "original_resume_text": row["original"],
                "proposed_resume_text": row["proposal"],
                "reviewer_label": None, "reason": None, "reviewer": None, "reviewed_at": None,
            })
    if not worksheet.exists():
        worksheet.write_text(json.dumps({
            "created_at": now.isoformat(), "instructions": "Judge proposal against source and original. "
            "Use SAFE, WRONG or AMBIGUOUS. Blind queue: prior labels and automated decisions omitted.",
            "records": queue}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(out), "counts": report["counts"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
