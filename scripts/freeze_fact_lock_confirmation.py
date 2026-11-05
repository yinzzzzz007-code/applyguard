"""Create a second fictional confirmation set; refuse overwrite after freezing."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "eval/asu_ablation/fact-lock-confirmation-2026-10-31.json"

PAIRS = [
    ("scope", "仅参与 Spark 日志清洗，未设计平台架构。",
     "只参与 Spark 日志清洗，没有设计平台架构。",
     "主导 Spark 平台架构设计。"),
    ("denominator", "Nora validated 8 of 32 invoices with Python.",
     "Using Python, Nora validated 8 out of 32 invoices.",
     "Nora validated 8 of 23 invoices with Python."),
    ("planned", "The Docker rollout is planned for 2027 and is not deployed.",
     "Not yet deployed, the Docker rollout is planned for 2027.",
     "The Docker rollout was completed in 2027."),
    ("unit_wording", "The Go importer took 250 ms before and 200 ms after tuning.",
     "After tuning, the Go importer took 200 milliseconds, down from 250 milliseconds.",
     "After tuning, the Go importer took 180 ms, down from 250 ms."),
    ("owner", "李宁是项目负责人；赵明仅实现 React 页面。",
     "项目由李宁负责；赵明仅实现 React 页面。",
     "赵明负责整个项目并实现 React 页面。"),
    ("causal_credit", "Lina measured a 10% latency reduction in a local trial.",
     "In a local trial, Lina measured latency 10% lower.",
     "Lina delivered a 10% latency reduction in production."),
    ("unlisted_technology", "Mira tested a Kafka consumer but did not deploy it.",
     "Mira tested the Kafka consumer; it was not deployed.",
     "Mira tested a RabbitMQ consumer and deployed it."),
    ("english_attribution", "Mina tested Docker; Ben implemented SQL queries.",
     "Docker was tested by Mina; Ben implemented SQL queries.",
     "Mina implemented SQL queries; Ben tested Docker."),
    ("pilot", "试点仅覆盖2家门店，尚未全量上线。",
     "只在2家门店试点，尚未全量上线。",
     "试点已覆盖20家门店并全面上线。"),
    ("percentage_points", "准确率从60%升至63%，提高3个百分点。",
     "准确率从60%升至63%。",
     "准确率从60%升至63%，相对提高3%。"),
]


def main():
    if DEST.exists():
        raise SystemExit("Confirmation set is frozen; refusing overwrite.")
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    cases = []
    for index, (category, original, safe, wrong) in enumerate(PAIRS, 1):
        for label, proposal in (("SAFE", safe), ("WRONG", wrong)):
            cases.append({"id": f"confirm-{index:02d}-{label.lower()}",
                          "split": "confirmation", "category": category,
                          "source": "Fictional signed record: " + original,
                          "original": original, "proposal": proposal,
                          "expected": label})
    data = {"frozen_at": now, "author": "Codex; no human adjudication",
            "protocol": "Additional fictional author-labeled confirmation cases, "
                        "frozen after development repairs and before first evaluation. "
                        "Do not tune rules against these and call them still unseen.",
            "cases": cases}
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    DEST.write_bytes(raw)
    print(json.dumps({"path": str(DEST), "sha256": hashlib.sha256(raw).hexdigest(),
                      "cases": len(cases)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
