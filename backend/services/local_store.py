"""Local-only resume draft on disk. The file is gitignored and must not be pushed."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def local_dir() -> Path:
    override = os.getenv("APPLYGUARD_LOCAL_DIR", "").strip()
    return Path(override) if override else DATA_DIR / "local"


def draft_path() -> Path:
    return local_dir() / "resume-draft.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_resume_draft() -> dict[str, Any] | None:
    path = draft_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("本机草稿损坏，无法读取") from exc
    if not isinstance(payload, dict):
        raise ValueError("本机草稿格式无效")
    form = payload.get("form") if isinstance(payload.get("form"), dict) else payload
    if not isinstance(form, dict):
        raise ValueError("本机草稿缺少表单")
    return form


def save_resume_draft(form: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(form, dict):
        raise ValueError("草稿必须是 JSON 对象")
    if isinstance(form.get("form"), dict) and "basic" not in form:
        form = form["form"]
    if not (form.get("candidateId") or form.get("candidate_id")):
        raise ValueError("草稿缺少候选人编号")
    if not isinstance(form.get("basic"), dict):
        raise ValueError("草稿缺少基本信息")
    folder = local_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = draft_path()
    envelope = {
        "saved_at": _utc_now(),
        "form": form,
    }
    encoded = json.dumps(envelope, ensure_ascii=False, indent=2)
    if len(encoded.encode("utf-8")) > 400_000:
        raise ValueError("草稿过大，无法保存")
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(path)
    return {
        "saved": True,
        "saved_at": envelope["saved_at"],
        "notice": "已写入本机后端草稿。该文件位于 data/local/，已被 git 忽略，push 不会带上。",
    }
