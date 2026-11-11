"""Local-only resume / workflow drafts on disk. Files are gitignored and must not be pushed."""

from __future__ import annotations

import hashlib
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
_WORKFLOW_LOCK = Lock()
_UNSPECIFIED = object()
_WORKFLOW_MAX_BYTES = 800_000


def local_dir() -> Path:
    override = os.getenv("APPLYGUARD_LOCAL_DIR", "").strip()
    return Path(override) if override else DATA_DIR / "local"


def draft_path() -> Path:
    return local_dir() / "resume-draft.json"


def workflow_draft_path() -> Path:
    return local_dir() / "workflow-draft.json"


def workflow_source_fingerprint(
    jd: str,
    *,
    resume_saved_at: str | None = None,
    job_id: str | None = None,
    job_content_hash: str | None = None,
) -> str:
    """Hash of JD + resume version + optional job binding; used to stale-check drafts."""
    raw = "\n".join(
        [
            "wf-src-v1",
            (jd or "").strip(),
            resume_saved_at or "",
            job_id or "",
            job_content_hash or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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


def _workflow_shape_ok(workflow: Any) -> bool:
    if not isinstance(workflow, dict):
        return False
    claims = workflow.get("resume_claims")
    return (
        isinstance(workflow.get("application_id"), str)
        and isinstance(workflow.get("candidate_id"), str)
        and isinstance(workflow.get("parsed_jd"), dict)
        and isinstance(workflow.get("evidence_match"), dict)
        and isinstance(workflow.get("resume_selection"), dict)
        and isinstance(claims, list)
        and len(claims) <= 20
        and all(
            isinstance(row, dict)
            and isinstance(row.get("claim_id"), str)
            and isinstance(row.get("text"), str)
            and len(row["text"]) <= 420
            for row in claims
        )
        and isinstance(workflow.get("claim_verification"), list)
        and isinstance(workflow.get("field_controls"), list)
        and isinstance(workflow.get("human_confirmation"), dict)
        and isinstance(workflow.get("risk_result"), dict)
        and isinstance(workflow.get("ats_form_mapping"), dict)
        and isinstance(workflow.get("step_trace"), list)
    )


def load_workflow_draft(
    *,
    current_jd: str | None = None,
    current_job_id: str | None = None,
    current_job_hash: str | None = None,
) -> dict[str, Any] | None:
    """Return stored live workflow, or None. Marks stale when source fingerprint drifts."""
    path = workflow_draft_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("本机工作流草稿损坏，无法读取") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ValueError("本机工作流草稿格式无效")
    workflow = payload.get("workflow")
    jd = payload.get("jd")
    if not _workflow_shape_ok(workflow) or not isinstance(jd, str):
        raise ValueError("本机工作流草稿缺少有效分析结果")
    if workflow.get("_prerecorded"):
        raise ValueError("预录演示结果不会写入本机工作流草稿")

    resume = None
    try:
        resume = load_resume_draft()
    except ValueError:
        resume = None
    resume_saved_at = resume.get("savedAt") if isinstance(resume, dict) else None
    stored_fp = payload.get("source_fingerprint")
    compare_jd = jd if current_jd is None else current_jd
    compare_job_id = payload.get("active_job_id") if current_job_id is None else current_job_id
    compare_job_hash = payload.get("job_content_hash") if current_job_hash is None else current_job_hash
    expected_fp = workflow_source_fingerprint(
        compare_jd,
        resume_saved_at=resume_saved_at,
        job_id=compare_job_id if isinstance(compare_job_id, str) else None,
        job_content_hash=compare_job_hash if isinstance(compare_job_hash, str) else None,
    )
    stale = not isinstance(stored_fp, str) or stored_fp != expected_fp
    stale_reason = None
    if stale:
        if resume_saved_at != payload.get("resume_saved_at"):
            stale_reason = "经历库已更新，请回岗位说明重新分析后再使用证据匹配与后续步骤。"
        elif current_jd is not None and current_jd.strip() != jd.strip():
            stale_reason = "岗位原文已变更，请重新分析后再继续。"
        else:
            stale_reason = "岗位或经历源头已变化，已作废旧结果，请重新分析。"

    drafts = payload.get("drafts") if isinstance(payload.get("drafts"), dict) else {}
    form = payload.get("form") if isinstance(payload.get("form"), dict) else None
    return {
        "exists": True,
        "stale": stale,
        "stale_reason": stale_reason,
        "saved_at": payload.get("saved_at"),
        "jd": jd,
        "active_job_id": payload.get("active_job_id"),
        "job_content_hash": payload.get("job_content_hash"),
        "resume_saved_at": payload.get("resume_saved_at"),
        "source_fingerprint": stored_fp,
        "form": form,
        "drafts": drafts,
        "workflow": workflow,
    }


def save_workflow_draft(body: dict[str, Any]) -> dict[str, Any]:
    """Persist a live workflow snapshot under data/local/workflow-draft.json."""
    if not isinstance(body, dict):
        raise ValueError("工作流草稿必须是 JSON 对象")
    if body.get("clear") is True:
        return clear_workflow_draft()
    workflow = body.get("workflow")
    jd = body.get("jd")
    if not _workflow_shape_ok(workflow):
        raise ValueError("工作流草稿缺少有效分析结果")
    if not isinstance(jd, str) or len(jd.strip()) < 20:
        raise ValueError("工作流草稿缺少岗位原文")
    if workflow.get("_prerecorded"):
        raise ValueError("预录演示结果不能写入本机工作流草稿")

    resume = None
    try:
        resume = load_resume_draft()
    except ValueError:
        resume = None
    resume_saved_at = body.get("resume_saved_at")
    if not isinstance(resume_saved_at, str):
        resume_saved_at = resume.get("savedAt") if isinstance(resume, dict) else None
    job_id = body.get("active_job_id")
    job_hash = body.get("job_content_hash")
    if job_id is not None and not isinstance(job_id, str):
        raise ValueError("active_job_id 无效")
    if job_hash is not None and not isinstance(job_hash, str):
        raise ValueError("job_content_hash 无效")
    drafts = body.get("drafts") if isinstance(body.get("drafts"), dict) else {}
    form = body.get("form") if isinstance(body.get("form"), dict) else None
    fingerprint = workflow_source_fingerprint(
        jd,
        resume_saved_at=resume_saved_at if isinstance(resume_saved_at, str) else None,
        job_id=job_id if isinstance(job_id, str) else None,
        job_content_hash=job_hash if isinstance(job_hash, str) else None,
    )
    saved_at = _utc_now()
    envelope = {
        "version": 1,
        "saved_at": saved_at,
        "jd": jd,
        "active_job_id": job_id,
        "job_content_hash": job_hash,
        "resume_saved_at": resume_saved_at,
        "source_fingerprint": fingerprint,
        "form": form,
        "drafts": drafts,
        "workflow": workflow,
    }
    encoded = json.dumps(envelope, ensure_ascii=False, indent=2)
    if len(encoded.encode("utf-8")) > _WORKFLOW_MAX_BYTES:
        raise ValueError("工作流草稿过大，无法保存")
    path = workflow_draft_path()
    with _WORKFLOW_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        "source_fingerprint": fingerprint,
        "notice": "已写入本机工作流草稿（data/local/workflow-draft.json）。源头变更后会作废并要求重新分析。",
    }


def clear_workflow_draft() -> dict[str, Any]:
    path = workflow_draft_path()
    with _WORKFLOW_LOCK:
        if path.is_file():
            path.unlink()
    return {"saved": True, "cleared": True, "notice": "已清除本机工作流草稿。"}
