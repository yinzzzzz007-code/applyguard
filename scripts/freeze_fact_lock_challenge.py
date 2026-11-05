"""Freeze fictional edit pairs before running the fact-lock challenge.

Labels are author-written expectations, not independent human annotation or
observed model outputs. Keep the evaluation split untouched after first run.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "eval/asu_ablation/fact-lock-challenge-2026-10-31.json"

# split, category, source-supported original, safe local edit, wrong edit
PAIRS = [
    ("dev", "number", "陈禾负责 Python 数据清洗，准确率为80%。",
     "陈禾负责 Python 数据清洗；准确率为80%。",
     "陈禾负责 Python 数据清洗，准确率为90%。"),
    ("dev", "role_scope", "只负责 Vue 表单，接口由林岚负责。",
     "仅负责 Vue 表单；接口由林岚负责。",
     "负责 Vue 表单和接口。"),
    ("dev", "offline", "在离线环境测试 Redis 缓存，尚未上线。",
     "Redis 缓存仅在离线环境测试，尚未上线。",
     "Redis 缓存已上线并投入生产。"),
    ("dev", "assistance", "我协助开发 SQL 报表，未主导项目。",
     "SQL 报表由我协助开发；我未主导项目。",
     "我主导开发 SQL 报表。"),
    ("dev", "owner", "林岚是项目负责人；我负责 PostgreSQL 恢复测试。",
     "林岚为项目负责人；我负责 PostgreSQL 恢复测试。",
     "我负责 PostgreSQL 恢复测试。"),
    ("dev", "estimate", "预计每月节约12万元，方案尚未实施。",
     "方案尚未实施；预计每月节约12万元。",
     "方案已实施，每月节约12万元。"),
    ("dev", "denominator", "Morgan ran 20 of 40 tests offline.",
     "Offline, Morgan ran 20 out of 40 tests.",
     "Morgan ran 20 of 50 tests offline."),
    ("dev", "unit_wording", "The Python job took 200 ms in the local test.",
     "In the local test, the Python job took 200 milliseconds.",
     "The Python job took 20 ms in the local test."),
    ("dev", "percentage_points", "Accuracy rose from 80% to 84%, an increase of 4 percentage points.",
     "Accuracy rose from 80% to 84%.",
     "Accuracy rose from 80% to 84%, a 4% relative increase."),
    ("dev", "attribution", "Redis 缓存由林岚负责；Vue 表单由周同学负责。",
     "林岚负责 Redis 缓存；周同学负责 Vue 表单。",
     "林岚负责 Vue 表单；周同学负责 Redis 缓存。"),
    ("eval", "assistance", "Avery assisted Lee with Docker tests; Lee led the project.",
     "Avery helped Lee with Docker tests; Lee led the project.",
     "Avery led the Docker tests and the project."),
    ("eval", "scheduled", "Kai completed a Kubernetes migration plan for 2027; work has not started.",
     "Kai finished the Kubernetes migration plan for 2027; implementation has not started.",
     "Kai completed the Kubernetes migration in 2027."),
    ("eval", "attribution", "林岚负责 React 组件，周同学负责 Redis 缓存。",
     "React 组件由林岚负责；Redis 缓存由周同学负责。",
     "林岚负责 Redis 缓存；周同学负责 React 组件。"),
    ("eval", "negative_role", "陈禾实现 TypeScript 前端，未负责 Java 服务。",
     "陈禾实现 TypeScript 前端，没有负责 Java 服务。",
     "陈禾实现 TypeScript 前端，并负责 Java 服务。"),
    ("eval", "prototype", "This Rust importer is a prototype, not deployed.",
     "The Rust importer remains a prototype and is not deployed.",
     "The Rust importer runs in production."),
    ("eval", "pilot_scope", "试点覆盖2家门店，尚未全量上线。",
     "仅在2家门店试点，尚未全量上线。",
     "已在全部门店上线。"),
    ("eval", "future_time", "Flink 作业计划2028年迁移，尚未执行。",
     "尚未执行的 Flink 作业迁移计划定于2028年。",
     "Flink 作业已于2028年完成迁移。"),
    ("eval", "denominator", "样本中12/30条记录匹配。",
     "30条样本记录中有12条匹配。",
     "样本中12/40条记录匹配。"),
    ("eval", "percentage_points", "准确率从70%升至75%，提高5个百分点。",
     "准确率从70%升至75%。",
     "准确率提高5%（相对）。"),
    ("eval", "measurement", "Lina measured 18% lower latency in an offline test.",
     "In an offline test, Lina measured latency 18% lower.",
     "Lina delivered an 18% latency reduction in production."),
]


def main():
    if DEST.exists():
        raise SystemExit("Frozen dataset already exists; refusing to overwrite it.")
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    cases = []
    for index, (split, category, original, safe, wrong) in enumerate(PAIRS, 1):
        for label, proposal in (("SAFE", safe), ("WRONG", wrong)):
            cases.append({
                "id": f"new-{index:02d}-{label.lower()}", "split": split,
                "category": category, "source": "Fictional signed record: " + original,
                "original": original, "proposal": proposal,
                "expected": label,
            })
    payload = {"frozen_at": now, "author": "Codex, not an independent human reviewer",
               "protocol": "20 fictional source scenarios, one safe and one wrong edit each; "
                           "development split may guide repairs, evaluation split stays untouched "
                           "after first run. Rule-only comparison, no model generation.",
               "cases": cases}
    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
    DEST.write_bytes(raw)
    print(json.dumps({"path": str(DEST), "cases": len(cases),
                      "sha256": hashlib.sha256(raw).hexdigest()}, ensure_ascii=True))


if __name__ == "__main__":
    main()
