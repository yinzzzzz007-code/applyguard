"""Rule-only comparison on the frozen fictional edit challenge."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.asu_resume import proposal_violations
from backend.services.edit_invariants import lost_qualifiers
from backend.services.fact_lock import locked_edit_findings

DATASETS = {
    "dev": ROOT / "eval/asu_ablation/fact-lock-challenge-2026-10-31.json",
    "eval": ROOT / "eval/asu_ablation/fact-lock-challenge-2026-10-31.json",
    "confirmation": ROOT / "eval/asu_ablation/fact-lock-confirmation-2026-10-31.json",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=list(DATASETS), required=True)
    args = parser.parse_args()
    raw = DATASETS[args.split].read_bytes()
    cases = [row for row in json.loads(raw)["cases"] if row["split"] == args.split]
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    records = []
    counts = Counter()
    for row in cases:
        old = row["original"]
        new = row["proposal"]
        baseline_findings = ([x["detail"] for x in lost_qualifiers(old, new)] +
                             proposal_violations(old, new))
        new_findings = locked_edit_findings(old, new,
                        {"relation": "SUPPORTED", "complete": True})
        baseline_block = bool(baseline_findings)
        new_block = baseline_block or bool(new_findings)
        truth = row["expected"]
        counts["cases"] += 1
        counts[f"{truth}_cases"] += 1
        counts[f"baseline_{truth}_{'block' if baseline_block else 'pass'}"] += 1
        counts[f"new_{truth}_{'block' if new_block else 'pass'}"] += 1
        records.append({
            "id": row["id"], "category": row["category"], "expected": truth,
            "baseline_block": baseline_block, "new_block": new_block,
            "baseline_findings": baseline_findings, "new_findings": new_findings,
            "text_sha256": hashlib.sha256((old + "\n" + new).encode()).hexdigest(),
        })
    out = ROOT / "output/test-reports" / (
        now.strftime("%Y%m%d_%H%M%S_%f") + "_fact-lock-" + args.split)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "date": now.isoformat(), "status": "COMPLETE_RULE_ONLY",
        "split": args.split, "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "baseline": "deterministic lost_qualifiers + proposal_violations",
        "candidate": "baseline + locked_edit_findings",
        "counts": dict(sorted(counts.items())), "records": records,
        "limits": ["Fictional author-labeled text, not independent human annotation.",
                   "Pairs were manually constructed; they are not model outputs.",
                   "Original source was stipulated by the fixture, not verified by SAG.",
                   "No LLM atomic judge or preservation judge was run on new cases.",
                   "Rates apply only to this rule-only challenge, not the full app."],
    }
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "report.md").write_text(
        f"# Fact lock {args.split} challenge\n\nDate: {now.isoformat()}\n\n"
        f"Dataset SHA256: {report['dataset_sha256']}\n\n"
        f"Counts: {json.dumps(report['counts'], ensure_ascii=False)}\n\n"
        + "\n".join("- " + limit for limit in report["limits"]) + "\n",
        encoding="utf-8")
    print(json.dumps({"directory": str(out), "counts": report["counts"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
