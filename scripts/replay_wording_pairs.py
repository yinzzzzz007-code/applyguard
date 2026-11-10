"""Replay only complete historical pairs. Keep source checks fixed for identical texts.
New repair outputs get fresh atomic checks; old labels apply ONLY to the frozen proposals.
"""
import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.atomic_verifier import AtomicVerifier
from backend.services.model_client import HttpModelClient
from backend.services.wording_review import review_edit, may_apply_wording
from backend.services.fact_lock import locked_edit_findings, wording_invariants
from backend.services.edit_guard import preservation
from backend.services.asu_resume import proposal_violations
from scripts.evaluate_asu_ablation import fixture

ARCHIVE = ROOT / "docs/testing/runs/2026-10-30"
RUN = next((ARCHIVE / "frozen-asu").glob("*_asu-ablation-60"))
BASE = next((ARCHIVE / "main").glob("20261030_172733*_asu-reviewed-replay/report.json"))
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def audit_cached(path, output):
    """Reapply today's non-model guards to dated decisions without relabeling repairs."""
    cache = read(path)
    if hashlib.sha256(BASE.read_bytes()).hexdigest() != cache["baseline_sha256"]:
        raise ValueError("Baseline changed")
    source = {r["id"]:r for r in read(RUN / "dataset.json")}
    index = {(r["id"],r["arm"]):r for r in cache["rows"]}
    batches = {cid:f.parent for f in RUN.glob("batch-*/original-checks.json") for cid in read(f)}
    result = []
    for r in read(BASE)["records"]:
        if r["label"] not in {"SAFE","WRONG"} or r["replayed_v3_accept"] is None:
            continue
        row = {k:r[k] for k in ("id","arm","label","text_sha256","changed")}
        row["old_accepted"] = r["replayed_v3_accept"]
        result.append(row)
        saved = index.get((r["id"],r["arm"]))
        if not saved or saved["outcome"] == "error":
            row["outcome"] = "incomplete"
            continue
        if not r["changed"]:
            row["outcome"] = "unchanged"
            continue
        assert hashlib.sha256(saved["proposal"].encode()).hexdigest() == r["text_sha256"]
        if saved["candidate"] != r["proposal"]:
            raise ValueError("New repaired text requires fresh final checks for this audit")
        cid = "claim_" + r["id"]
        original = read(batches[cid]/"original-checks.json")[cid]
        final = read(batches[cid]/(r["arm"]+"-checks.json"))[cid]
        _, _, hits = fixture([source[r["id"]]])
        hard = list(dict.fromkeys(wording_invariants(r["original"],r["proposal"]) +
                                  proposal_violations(r["original"],r["proposal"],hits[cid]) +
                                  locked_edit_findings(r["original"],r["proposal"],original)))
        loss = (r.get("replayed_losses") or {}) if original.get("complete") else {}
        passed = may_apply_wording(saved["wording"], original, final, hard, False, r["original"],r["proposal"],loss)
        row.update(outcome="adopted_frozen" if passed else "held_frozen",
                   requested_repair=saved["wording"]["repair_attempted"], issues=hard,
                   initial_sdk_equivalent=saved["wording"]["equivalent"],
                   original_support=original["relation"], frozen_proposal_support=final["relation"])
        if passed:
            row["final_support"] = ("INSUFFICIENT" if final["relation"]=="SUPPORTED" and
                                   original["relation"]!="SUPPORTED" else final["relation"])
        if hard and saved["wording"]["equivalent"]:
            row["new_repair_not_measured"] = True
    output.parent.mkdir(exist_ok=True,parents=True)
    output.write_text(json.dumps({"date_utc":datetime.now(timezone.utc).isoformat(),
                      "requested_model":cache["requested_model"],"input_run":path.name,
                      "baseline_sha256":cache["baseline_sha256"],"rows":result},
                      ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume',type=Path,help='Keep successful pairs, retry only failed or missing ones')
    parser.add_argument('--workers',type=int,choices=[1,2,3],default=1)
    parser.add_argument('--audit-cache',type=Path,help='Offline audit of frozen proposals against final code')
    parser.add_argument('--audit-output',type=Path,default=Path('output/test-reports/wording-audit.json'))
    args = parser.parse_args()
    if args.audit_cache:
        audit_cached(args.audit_cache, args.audit_output)
        return
    old = [r for r in read(BASE)["records"] if r["label"] in {"WRONG", "SAFE"}
           and r["replayed_v3_accept"] is not None]
    source = {r["id"]:r for r in read(RUN / "dataset.json")}
    batches = {cid:f.parent for f in RUN.glob("batch-*/original-checks.json") for cid in read(f)}
    client = HttpModelClient(task="complex", max_tokens=4500, timeout=75, require_complete=True)
    def evaluate(row):
        cid = "claim_" + row["id"]
        assert hashlib.sha256(row["proposal"].encode()).hexdigest() == row["text_sha256"]
        record = {k:row[k] for k in ("id","arm","label","original","proposal","changed")}
        record["old_accepted"] = row["replayed_v3_accept"]
        if not row["changed"]:
            return {**record, "outcome":"unchanged"}
        batch = batches[cid]
        original_check = read(batch / "original-checks.json")[cid]
        _, contexts, hits = fixture([source[row["id"]]])
        first_check = read(batch / (row["arm"]+"-checks.json"))[cid]
        started = time.monotonic()
        text, trace = review_edit(client.wording_step, row["original"], row["proposal"])
        record.update(wording=trace, candidate=text, initial_material=first_check["relation"],
                      old_losses=row["replayed_losses"], original_material=original_check["relation"])
        try:
            final_check = first_check if text == row["proposal"] else AtomicVerifier(client).verify(
                [{"claim_id":cid,"text":text}],contexts,hits)[cid]
            hard = proposal_violations(row["original"],text,hits[cid]) + locked_edit_findings(row["original"],text,original_check)
            loss = row.get("replayed_losses") or {}
            if not original_check.get("complete"):
                loss = {}
            elif text != row["proposal"]:
                loss = preservation(client,[{"claim_id":cid,"text":row["original"]}],
                                    [{"claim_id":cid,"text":text}],hits,{cid:original_check})[cid]
            record["preservation"] = loss
            passed = may_apply_wording(trace, original_check, final_check, hard, False, row["original"], text, loss)
            record["outcome"] = ("accepted_frozen" if text == row["proposal"] else "accepted_repair") if passed else "kept_original"
            record["final_material"] = final_check["relation"]
            if trace.get("error"):
                record["outcome"] = "error"
        except Exception as exc:
            record.update(outcome="error", error=type(exc).__name__)
        record["seconds"] = round(time.monotonic()-started, 2)
        return record
    start = time.monotonic()
    date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = ROOT / "output/test-reports" / ("wording-pairs-"+date+".json")
    path.parent.mkdir(exist_ok=True,parents=True)
    report = {"date_utc":date,"requested_model":client.model,"baseline_sha256":hashlib.sha256(BASE.read_bytes()).hexdigest(),"rows":[]}
    if args.resume:
        previous = read(args.resume)
        if (previous["baseline_sha256"] != report["baseline_sha256"] or
                previous["requested_model"] != report["requested_model"]):
            raise ValueError("Different baseline or model")
        report["resumed_from"] = args.resume.name
        # A newly protected detail can invalidate a saved positive verdict.
        report["rows"] = [
            r for r in previous["rows"] if r["outcome"] != "error"
            and not (r.get("wording", {}).get("equivalent")
                     and wording_invariants(r["original"], r["candidate"]))
        ]
        done = {(r["id"],r["arm"]) for r in report["rows"]}
        old = [r for r in old if (r["id"],r["arm"]) not in done]
    # Diagnose the previously suspected false positives first.
    old.sort(key=lambda r: not (r["changed"] and r["label"]=="SAFE" and not r["replayed_v3_accept"]))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(evaluate,row):row for row in old}
        for future in as_completed(futures):
            if future.cancelled():
                continue
            row = futures[future]
            try:
                report["rows"].append(future.result())
            except Exception as exc:
                report["rows"].append({k:row[k] for k in ("id","arm","label","changed")} |
                                      {"outcome":"error","error":type(exc).__name__})
            if report["rows"][-1].get('wording',{}).get('provider_reason') == 'insufficient_balance':
                for remaining in futures:
                    remaining.cancel()
            report["seconds"]=round(time.monotonic()-start,2)
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(path,flush=True)
if __name__ == "__main__":
    main()
