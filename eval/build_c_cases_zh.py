"""Create the Chinese-claim benchmark from frozen case semantics and the current seed."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "eval" / "c_cases.json"
TARGET = ROOT / "eval" / "c_cases_zh_v2.json"
SEED = ROOT / "data" / "career-vault.seed.json"


def build() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    original = {claim["claim_id"]: claim["text"] for exp in seed["experiences"] for claim in exp["claims"]}
    cases = []
    for case in source["claim_cases"]:
        base = original[case["claim_id"]]
        suffix = case["id"].removeprefix(case["claim_id"].removeprefix("claim_") + "_")
        # Case names with the shortened python_api/fullstack_portal/ml_lora_evaluation/data_pipeline prefix.
        suffix = case["id"].split("_")[-1] if suffix == case["id"] else suffix
        if case["id"].endswith("review_contributed"):
            text = f"使用：{base}"
        elif case["id"].endswith("review_helped"):
            text = f"采用：{base}"
        elif suffix == "verified":
            text = base
        elif suffix == "owner":
            text = f"独立负责：{base}"
        elif suffix == "production":
            text = f"已上线：{base}"
        elif suffix in ("cuda", "kubernetes", "docker"):
            text = f"{base} 使用 {suffix.upper() if suffix == 'cuda' else suffix.capitalize() if suffix == 'docker' else 'Kubernetes'}。"
        elif suffix == "metric":
            text = f"{base} 提升 75%。"
        elif suffix == "date":
            text = f"{base} 完成于 2027-01。"
        else:
            raise ValueError(f"unhandled benchmark case: {case['id']}")
        cases.append({**case, "text": text})
    return {"dataset_id": "fictional_c_benchmark_zh_v2", "source_dataset_id": source["dataset_id"],
            "jd_cases": source["jd_cases"], "claim_cases": cases}


if __name__ == "__main__":
    TARGET.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(TARGET)
