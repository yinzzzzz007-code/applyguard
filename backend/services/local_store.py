"""Local-only resume draft on disk. The file is gitignored and must not be pushed."""

from __future__ import annotations

import json
import os
import re
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
_SAVE_LOCK = Lock()
_UNSPECIFIED = object()


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
    return {**form, "savedAt": form.get("savedAt") or payload.get("saved_at")}


def _date_span(value: Any, label: str, *, ongoing: bool = False) -> tuple[date, date] | None:
    if value is None or value == "":
        return None
    if ongoing and value in ("至今", "现在", "Present", "present", "Current", "current", "Now", "now"):
        return date.max, date.max
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
        raise ValueError(f"{label}格式不正确，请用日期控件选择")
    try:
        if len(value) == 4:
            return date(int(value), 1, 1), date(int(value), 12, 31)
        if len(value) == 7:
            year, month = map(int, value.split("-"))
            return date(year, month, 1), date(year, month, monthrange(year, month)[1])
        day = date.fromisoformat(value)
        return day, day
    except ValueError as exc:
        raise ValueError(f"{label}不是有效日期") from exc


def _validate_fields(form: dict[str, Any]) -> None:
    basic = form["basic"]
    phone, email = basic.get("phone"), basic.get("email")
    if phone is not None and (not isinstance(phone, str) or phone.strip() and not re.fullmatch(
            r"(?:1[3-9]\d{9}|\+86[1][3-9]\d{9}|\+(?!86)[1-9]\d{6,14})", re.sub(r"[\s()\-]", "", phone))):
        raise ValueError("手机号码格式不正确，请检查号码或国际区号")
    if email is not None and (not isinstance(email, str) or email.strip() and not re.fullmatch(
            r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", email.strip())):
        raise ValueError("电子邮箱格式不正确")
    for section, label in (("education", "教育"), ("internships", "实习"), ("projects", "项目"), ("awards", "获奖")):
        rows = form.get(section)
        if rows is None:
            continue
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"{label}经历格式无效")
        for index, row in enumerate(rows, 1):
            prefix = f"{label}第 {index} 条"
            if section == "awards":
                _date_span(row.get("date"), f"{prefix}时间")
                continue
            start = _date_span(row.get("start"), f"{prefix}开始时间")
            end = _date_span(row.get("end"), f"{prefix}结束时间", ongoing=section != "education")
            if start and end and start[0] > end[1]:
                raise ValueError(f"{prefix}结束时间早于开始时间")


def save_resume_draft(form: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(form, dict):
        raise ValueError("草稿必须是 JSON 对象")
    expected = form.get("expected_saved_at", _UNSPECIFIED)
    if isinstance(form.get("form"), dict) and "basic" not in form:
        form = form["form"]
    if not (form.get("candidateId") or form.get("candidate_id")):
        raise ValueError("草稿缺少候选人编号")
    if not isinstance(form.get("basic"), dict):
        raise ValueError("草稿缺少基本信息")
    _validate_fields(form)
    with _SAVE_LOCK:
        if expected is not _UNSPECIFIED:
            current = load_resume_draft()
            if expected != (current or {}).get("savedAt"):
                raise ValueError("经历库已在其他操作中更新。请重新读取已有资料后再保存。")
        path = draft_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        saved_at = _utc_now()
        envelope = {"saved_at": saved_at, "form": {**form, "savedAt": saved_at, "dirty": False}}
        encoded = json.dumps(envelope, ensure_ascii=False, indent=2)
        if len(encoded.encode("utf-8")) > 400_000:
            raise ValueError("草稿过大，无法保存")
        with NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as temp:
            temp_path = Path(temp.name)
            try:
                temp.write(encoded)
            except BaseException:
                temp.close()
                temp_path.unlink(missing_ok=True)
                raise
        try:
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)
    return {
        "saved": True,
        "saved_at": saved_at,
        "notice": "已写入本机后端草稿。该文件位于 data/local/，已被 git 忽略，push 不会带上。",
    }
