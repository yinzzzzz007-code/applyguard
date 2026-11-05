"""Convert local resume-draft.json into Career Vault experience shapes for the workflow."""

from __future__ import annotations

import re
from datetime import date
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
        # Keep short multi-line descriptions intact: later lines often contain scope or negation.
        if len(desc) <= 420:
            return desc
        # Longer source material stays in the vault; use the first bounded paragraph.
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
    form_confirmed: bool = False,
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
    # Education rows are user-authored profile fields; treat the filled form as confirmed evidence.
    claim_state = "VERIFIED" if form_confirmed else "UNVERIFIED"
    source_status = "VERIFIED" if form_confirmed else "UNVERIFIED"
    claim_confidence = 0.88 if form_confirmed else 0.55
    source_confidence = 0.85 if form_confirmed else 0.4
    source_note = (
        f"来自本机经历库已填写的{kind}信息（表单确认为准）"
        if form_confirmed
        else f"来自本机经历库草稿的{kind}条目（尚未关联本地证据原件）"
    )
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
                "confidence": claim_confidence,
                "verification_state": claim_state,
            }
        ],
        "evidence_sources": [
            {
                "evidence_id": evidence_id,
                "type": "OTHER",
                "source_type": "OTHER",
                "description": source_note,
                "uri": None,
                "source_reference": f"local-draft://{exp_id}",
                "confidence": source_confidence,
                "verification_status": source_status,
            }
        ],
        "verification_state": claim_state,
    }


def is_form_confirmed_evidence(source: dict[str, Any] | None) -> bool:
    """Only education profile rows bypass experience verification."""
    if not isinstance(source, dict):
        return False
    reference = str(source.get("source_reference") or "")
    description = str(source.get("description") or "")
    return (
        source.get("verification_status") == "VERIFIED"
        and reference.startswith("local-draft://")
        and "已填写的教育信息（表单确认为准）" in description
    )


def claim_is_form_confirmed(claim_id: str, experiences: list[dict[str, Any]]) -> bool:
    for experience in experiences:
        sources = {
            source["evidence_id"]: source
            for source in experience.get("evidence_sources", [])
            if isinstance(source, dict) and source.get("evidence_id")
        }
        for claim in experience.get("claims", []):
            if claim.get("claim_id") != claim_id:
                continue
            refs = claim.get("evidence_ids") or []
            return bool(refs) and all(is_form_confirmed_evidence(sources.get(evidence_id)) for evidence_id in refs)
    return False


def _education_claim_text(school: str, degree: str, major: str, start: str, end: str) -> str:
    bits = [part for part in (school, degree, major) if part]
    span = " — ".join(part for part in (_ym(start) or start, _ym(end) or end) if part)
    enrolled = False
    end_ym = _ym(end)
    if end_ym:
        try:
            year, month = (int(part) for part in end_ym.split("-", 1))
            # Future (or current-year) end dates mean the candidate is still enrolled.
            today = date.today()
            enrolled = date(year, month, 1) >= date(today.year, today.month, 1)
        except ValueError:
            enrolled = False
    elif start and not end:
        enrolled = True
    status = "在读" if enrolled else ""
    head = " · ".join(bits) if bits else "教育经历"
    if status and status not in head:
        head = f"{head}（{status}）"
    if span:
        return f"{head} · {span}"[:420]
    return head[:420]


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

    for idx, row in enumerate(form.get("education") or []):
        if not isinstance(row, dict):
            continue
        school = str(row.get("school") or "").strip()
        degree = str(row.get("degree") or "").strip()
        major = str(row.get("major") or "").strip()
        if not school and not major and not degree:
            continue
        start = str(row.get("start") or "")
        end = str(row.get("end") or "")
        text = _education_claim_text(school, degree, major, start, end)
        push(
            _one_experience(
                candidate_id=candidate_id,
                exp_id=str(row.get("id") or f"education_{idx}"),
                organization=school or "教育经历",
                title=degree or major or "教育经历",
                role="在读" if "在读" in text else (degree or "教育"),
                start=start,
                end=end,
                description=text,
                kind="教育",
                form_confirmed=True,
            )
        )

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
                # 实习与项目、竞赛一样，必须关联原件并核验。
                form_confirmed=False,
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
                # 项目须关联本地证据后才能视为已核验。
                form_confirmed=False,
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
                # 比赛 / 获奖须关联本地证据后才能视为已核验。
                form_confirmed=False,
            )
        )

    return out
