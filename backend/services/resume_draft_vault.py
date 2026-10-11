"""Convert local resume-draft.json into Career Vault experience shapes for the workflow."""

from __future__ import annotations

import re
from typing import Any

_ID_SAFE = re.compile(r"[^a-zA-Z0-9_]+")
_YM = re.compile(r"^(\d{4})[-/.年](\d{1,2})")


def _safe_id(prefix: str, raw: str, fallback: str) -> str:
    body = _ID_SAFE.sub("_", (raw or "").strip()).strip("_").lower()
    if not body:
        body = fallback
    if not body.startswith(prefix):
        body = f"{prefix}{body}"
    return body[:96]


def _ym(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    m = _YM.match(text)
    if not m:
        return None
    return f"{m.group(1)}-{int(m.group(2)):02d}"


def _claim_text(organization: str, title: str, role: str, description: str) -> str:
    desc = (description or "").strip()
    if desc:
        # Prefer first non-empty paragraph / bullet as the resume sentence
        for line in re.split(r"[\n\r]+", desc):
            line = line.strip().lstrip("•-*·、 ").strip()
            if len(line) >= 8:
                return line[:420]
        return desc[:420]
    bits = [b for b in (organization, title or role) if b]
    return " · ".join(bits) if bits else "（未填写经历描述）"


def _one_experience(
    *,
    candidate_id: str,
    exp_id: str,
    organization: str,
    title: str,
    role: str,
    start: str,
    end: str,
    description: str,
    kind: str,
) -> dict[str, Any] | None:
    organization = (organization or "").strip() or "（未填组织）"
    role = (role or title or "").strip() or kind
    title = (title or role).strip() or kind
    summary = _claim_text(organization, title, role, description)
    if summary == "（未填写经历描述）" and organization == "（未填组织）":
        return None

    claim_id = _safe_id("claim_", exp_id.replace("exp_", "", 1), "item")
    evidence_id = _safe_id("ev_", f"draft_{exp_id.replace('exp_', '', 1)}", "draft")
    lines = [
        ln.strip()
        for ln in re.split(r"[\n\r]+", description or "")
        if ln.strip()
    ]
    return {
        "experience_id": _safe_id("exp_", exp_id, "item"),
        "candidate_id": candidate_id,
        "title": title,
        "organization": organization,
        "role": role,
        "start_date": _ym(start),
        "end_date": _ym(end),
        "summary": summary,
        "responsibilities": lines[:12] or [summary],
        "skills": [],
        "metrics": [],
        "claims": [
            {
                "claim_id": claim_id,
                "text": summary,
                "evidence_ids": [evidence_id],
                "confidence": 0.55,
                "verification_state": "UNVERIFIED",
            }
        ],
        "evidence_sources": [
            {
                "evidence_id": evidence_id,
                "type": "OTHER",
                "source_type": "OTHER",
                "description": f"来自本机经历库草稿的{kind}条目（尚未关联本地证据原件）",
                "uri": None,
                "source_reference": f"local-draft://{exp_id}",
                "confidence": 0.4,
                "verification_status": "UNVERIFIED",
            }
        ],
        "verification_state": "UNVERIFIED",
    }


def experiences_from_resume_draft(form: dict[str, Any]) -> list[dict[str, Any]]:
    """Build contract-shaped experiences from EditableResumeForm / resume-draft.json."""
    raw_cand = str(form.get("candidateId") or form.get("candidate_id") or "cand_local_draft")
    candidate_id = _safe_id("cand_", raw_cand.replace("cand_", "", 1), "local_draft")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def push(item: dict[str, Any] | None) -> None:
        if not item:
            return
        eid = item["experience_id"]
        if eid in seen:
            return
        seen.add(eid)
        out.append(item)

    for idx, row in enumerate(form.get("internships") or []):
        if not isinstance(row, dict):
            continue
        push(
            _one_experience(
                candidate_id=candidate_id,
                exp_id=str(row.get("id") or f"internship_{idx}"),
                organization=str(row.get("organization") or ""),
                title=str(row.get("title") or ""),
                role=str(row.get("role") or ""),
                start=str(row.get("start") or ""),
                end=str(row.get("end") or ""),
                description=str(row.get("description") or ""),
                kind="实习",
            )
        )

    for idx, row in enumerate(form.get("projects") or []):
        if not isinstance(row, dict):
            continue
        push(
            _one_experience(
                candidate_id=candidate_id,
                exp_id=str(row.get("id") or f"project_{idx}"),
                organization=str(row.get("organization") or ""),
                title=str(row.get("title") or ""),
                role=str(row.get("role") or ""),
                start=str(row.get("start") or ""),
                end=str(row.get("end") or ""),
                description=str(row.get("description") or ""),
                kind="项目",
            )
        )

    for idx, row in enumerate(form.get("awards") or []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        issuer = str(row.get("issuer") or "").strip()
        desc = str(row.get("description") or "").strip()
        text = desc or (f"{name}" + (f"（{issuer}）" if issuer else ""))
        push(
            _one_experience(
                candidate_id=candidate_id,
                exp_id=str(row.get("id") or f"award_{idx}"),
                organization=issuer or "获奖 / 竞赛",
                title=name,
                role="获奖 / 竞赛",
                start=str(row.get("date") or ""),
                end="",
                description=text,
                kind="获奖",
            )
        )

    return out
