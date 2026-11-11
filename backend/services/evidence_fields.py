"""Experience-typed verification fields and material kinds for local evidence.

Material kind ≠ experience type. Association ≠ every field is supported.
"""

from __future__ import annotations

import re
from typing import Any

# Material kinds (what the file is)
MATERIAL_KINDS: dict[str, str] = {
    "AWARD_CERTIFICATE": "获奖证书",
    "INTERNSHIP_CERTIFICATE": "实习证明",
    "PROJECT_REPORT": "项目报告",
    "CODE_REPO": "代码仓库说明",
    "WORK_PRODUCT": "工作成果",
    "CERTIFICATE": "通用证书",
    "DOCUMENT": "其他材料",
}

# Experience verification schemas (what to check against a vault entry)
EXPERIENCE_FIELD_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "project": [
        ("name", "名称"),
        ("period", "时间"),
        ("organization", "所属组织"),
        ("role", "个人角色"),
        ("responsibilities", "负责工作"),
        ("tech_stack", "技术栈"),
        ("outcomes", "成果与指标"),
    ],
    "internship": [
        ("company", "公司"),
        ("department", "部门"),
        ("title", "岗位"),
        ("period", "时间"),
        ("duties", "职责"),
        ("outcomes", "工作产出与指标"),
    ],
    "award": [
        ("award_name", "奖项名称"),
        ("issuer", "颁发单位"),
        ("grade", "级别"),
        ("date", "获奖时间"),
        ("recipient", "获奖人或团队"),
    ],
}

# Keys allowed in normalized_fields (union of material extracts + legacy award keys)
ALL_FIELD_KEYS: tuple[str, ...] = (
    # award / certificate
    "recipient",
    "award_name",
    "grade",
    "issuer",
    "date",
    # internship
    "company",
    "department",
    "title",
    "period",
    "duties",
    "outcomes",
    # project
    "name",
    "organization",
    "role",
    "responsibilities",
    "tech_stack",
    # shared / material meta
    "material_label",
)

_GRADE = re.compile(r"([一二三特]等奖|金奖|银奖|铜奖|优胜奖)")
_AWARD_NAME = re.compile(
    r"((?:校级|省级|国家级|院级)?[\u4e00-\u9fffA-Za-z0-9·]{2,40}(?:竞赛|比赛|大赛|奖学金|奖))",
)
_ISSUER = re.compile(r"(?:颁发|主办|承办|单位)[:：\s]*([^\n]{2,40})")
_DATE = re.compile(r"(20\d{2})\s*[.\-年/]\s*(\d{1,2})")
_PERSON = re.compile(r"(?:获奖人|姓名|同学)[:：\s]*([\u4e00-\u9fff·]{2,8})")
_COMPANY = re.compile(
    r"(?:安排至|实习单位|所在单位|公司)[:：\s]*([^\n，,（(]{2,40})"
    r"|([\u4e00-\u9fffA-Za-z0-9（）()]{4,40}(?:有限公司|股份有限公司|科技|集团))"
)
_DEPARTMENT = re.compile(r"([^\n，,（(]{2,20}(?:事业部|部|中心|组|实验室))")
_ROLE = re.compile(r"(?:岗位|职位|担任|角色)[:：\s]*([^\n，,]{2,20})")
_PERIOD = re.compile(
    r"(20\d{2}\s*[.\-年/]\s*\d{1,2}\s*(?:日)?)\s*(?:至|—|-|~)\s*"
    r"(20\d{2}\s*[.\-年/]\s*\d{1,2}\s*(?:日)?|至今|现在)"
)
_TECH = re.compile(
    r"\b(?:Python|Java|JavaScript|TypeScript|React|Vue|Go|Rust|SQL|PyTorch|"
    r"TensorFlow|Docker|Kubernetes|Spring|Node\.?js|C\+\+|Linux)\b",
    re.I,
)
_METRIC = re.compile(r"(?:提升|降低|增长|减少|达到|完成|覆盖)?\s*\d+(?:\.\d+)?\s*%|"
                     r"\d+(?:\.\d+)?\s*(?:倍|万|人天|QPS|ms|秒)")

FIELD_STATUS_SUPPORTED = "SUPPORTED"
FIELD_STATUS_NOT_MENTIONED = "NOT_MENTIONED"
FIELD_STATUS_CONFLICT = "CONFLICT"
FIELD_STATUS_PENDING = "PENDING"

FIELD_STATUS_LABELS = {
    FIELD_STATUS_SUPPORTED: "支持",
    FIELD_STATUS_NOT_MENTIONED: "未提及",
    FIELD_STATUS_CONFLICT: "冲突",
    FIELD_STATUS_PENDING: "待确认",
}


def clean_normalized_fields(fields: dict[str, Any] | None) -> dict[str, str]:
    raw = fields if isinstance(fields, dict) else {}
    cleaned: dict[str, str] = {}
    for key in ALL_FIELD_KEYS:
        value = str(raw.get(key) or "").strip()
        if value:
            cleaned[key] = value
    return cleaned


def guess_material_kind(text: str, relative_path: str = "") -> str:
    blob = f"{relative_path}\n{text or ''}"
    lower_path = (relative_path or "").lower()
    if any(m in blob for m in ("实习证明", "实习期满", "安排至", "实习工作内容")):
        return "INTERNSHIP_CERTIFICATE"
    if any(m in blob for m in ("README", "仓库", "GitHub", "GitLab", "开源项目")) or "readme" in lower_path:
        return "CODE_REPO"
    if any(m in blob for m in ("项目报告", "结题报告", "验收报告", "项目总结")):
        return "PROJECT_REPORT"
    if any(m in blob for m in ("工作总结", "交付物", "成果说明", "绩效")):
        return "WORK_PRODUCT"
    if any(m in blob for m in ("奖", "竞赛", "比赛", "奖学金")):
        return "AWARD_CERTIFICATE"
    if "证书" in blob or "certificate" in lower_path:
        return "CERTIFICATE"
    return "DOCUMENT"


def material_kind_label(kind: str) -> str:
    return MATERIAL_KINDS.get(kind, kind or "其他材料")


def infer_fields_for_kind(text: str, kind: str | None = None) -> dict[str, str]:
    """Extract suggested structured fields from OCR/text. Kind guides which keys to fill."""
    kind = kind or guess_material_kind(text)
    fields: dict[str, str] = {}
    if not (text or "").strip():
        return fields

    if kind in {"AWARD_CERTIFICATE", "CERTIFICATE"}:
        if m := _PERSON.search(text):
            fields["recipient"] = m.group(1)
        if m := _GRADE.search(text):
            fields["grade"] = m.group(1)
        if m := _AWARD_NAME.search(text):
            fields["award_name"] = m.group(1)
        if m := _ISSUER.search(text):
            fields["issuer"] = m.group(1).strip(" 。.;；")
        if m := _DATE.search(text):
            fields["date"] = f"{m.group(1)}-{int(m.group(2)):02d}"
    elif kind == "INTERNSHIP_CERTIFICATE":
        if m := _COMPANY.search(text):
            fields["company"] = (m.group(1) or m.group(2) or "").strip()
        if m := _DEPARTMENT.search(text):
            fields["department"] = m.group(1).strip()
        if m := _ROLE.search(text):
            fields["title"] = m.group(1).strip()
        if m := _PERIOD.search(text):
            fields["period"] = f"{m.group(1)} — {m.group(2)}"
        elif m := _DATE.search(text):
            fields["period"] = f"{m.group(1)}-{int(m.group(2)):02d}"
        # Keep issuer as issuing party of the certificate when present
        if m := _ISSUER.search(text):
            fields["issuer"] = m.group(1).strip(" 。.;；")
    elif kind in {"PROJECT_REPORT", "CODE_REPO", "WORK_PRODUCT", "DOCUMENT"}:
        if m := _ROLE.search(text):
            fields["role"] = m.group(1).strip()
        if m := _PERIOD.search(text):
            fields["period"] = f"{m.group(1)} — {m.group(2)}"
        techs = sorted({m.group(0) for m in _TECH.finditer(text)}, key=str.lower)
        if techs:
            fields["tech_stack"] = "、".join(techs[:8])
        metrics = [m.group(0).strip() for m in _METRIC.finditer(text)]
        if metrics:
            fields["outcomes"] = "；".join(metrics[:4])
        if kind == "CODE_REPO" and "readme" in text.lower()[:80]:
            first = next((ln.strip("# ").strip() for ln in text.splitlines() if ln.strip()), "")
            if first and len(first) <= 60:
                fields["name"] = first
    else:
        # Fallback: try light award + org hints without forcing a full award form
        if m := _GRADE.search(text):
            fields["grade"] = m.group(1)
        if m := _DATE.search(text):
            fields["date"] = f"{m.group(1)}-{int(m.group(2)):02d}"

    return clean_normalized_fields(fields)


def experience_values(target_type: str, item: dict[str, Any]) -> dict[str, str]:
    """Map a vault entry onto the experience verification schema. Empty values omitted."""
    values: dict[str, str] = {}
    if target_type == "project":
        name = str(item.get("title") or item.get("name") or "").strip()
        org = str(item.get("organization") or "").strip()
        role = str(item.get("role") or "").strip()
        start = str(item.get("start") or item.get("start_date") or "").strip()
        end = str(item.get("end") or item.get("end_date") or "").strip()
        desc = str(item.get("description") or item.get("summary") or "").strip()
        period = " — ".join(p for p in (start, end) if p)
        if name:
            values["name"] = name
        if period:
            values["period"] = period
        if org:
            values["organization"] = org
        if role:
            values["role"] = role
        if desc:
            values["responsibilities"] = desc
            techs = sorted({m.group(0) for m in _TECH.finditer(desc)}, key=str.lower)
            if techs:
                values["tech_stack"] = "、".join(techs[:8])
            metrics = [m.group(0).strip() for m in _METRIC.finditer(desc)]
            if metrics:
                values["outcomes"] = "；".join(metrics[:4])
    elif target_type == "internship":
        company = str(item.get("organization") or item.get("company") or "").strip()
        title = str(item.get("title") or item.get("role") or "").strip()
        role = str(item.get("role") or "").strip()
        start = str(item.get("start") or item.get("start_date") or "").strip()
        end = str(item.get("end") or item.get("end_date") or "").strip()
        desc = str(item.get("description") or item.get("summary") or "").strip()
        period = " — ".join(p for p in (start, end) if p)
        department = str(item.get("department") or "").strip()
        if not department and title:
            if m := _DEPARTMENT.search(title):
                department = m.group(1)
        if company:
            values["company"] = company
        if department:
            values["department"] = department
        if title or role:
            values["title"] = title or role
        if period:
            values["period"] = period
        if desc:
            values["duties"] = desc
            metrics = [m.group(0).strip() for m in _METRIC.finditer(desc)]
            if metrics:
                values["outcomes"] = "；".join(metrics[:4])
    elif target_type == "award":
        name = str(item.get("name") or item.get("award_name") or "").strip()
        issuer = str(item.get("issuer") or "").strip()
        date = str(item.get("date") or "").strip()
        desc = str(item.get("description") or "").strip()
        recipient = str(item.get("recipient") or "").strip()
        grade = str(item.get("grade") or "").strip()
        if not grade:
            blob = f"{name}\n{desc}"
            if m := _GRADE.search(blob):
                grade = m.group(1)
        if name:
            values["award_name"] = name
        if issuer:
            values["issuer"] = issuer
        if grade:
            values["grade"] = grade
        if date:
            values["date"] = date
        if recipient:
            values["recipient"] = recipient
        elif m := _PERSON.search(desc):
            values["recipient"] = m.group(1)
    return values


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", (text or "").lower())


def _year_tokens(text: str) -> set[str]:
    return set(re.findall(r"20\d{2}", text or ""))


def _find_quote(corpus: str, needle: str, *, max_len: int = 160) -> str | None:
    if not corpus or not needle:
        return None
    idx = corpus.lower().find(needle.lower())
    if idx < 0:
        # try significant chunk (≥2 chars)
        for part in re.split(r"[\s,，、；;|/]+", needle):
            if len(part) >= 2:
                idx = corpus.lower().find(part.lower())
                if idx >= 0:
                    needle = part
                    break
        else:
            return None
    start = max(0, idx - 40)
    end = min(len(corpus), idx + len(needle) + 80)
    snippet = corpus[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(corpus):
        snippet = snippet + "…"
    return snippet[:max_len]


def _tokens(text: str) -> set[str]:
    parts = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9+.#]{1,}", text or "")
    return {p.lower() for p in parts if len(p) >= 2}


def check_experience_fields(
    target_type: str,
    experience: dict[str, Any],
    *,
    fields: dict[str, Any] | None,
    corpus: str,
    stored_checks: list[dict[str, Any]] | None = None,
    force_pending: bool = False,
) -> list[dict[str, Any]]:
    """Build per-field verification rows for an experience ↔ material pair.

    - Only fields with experience values are returned.
    - If force_pending / missing stored detail for legacy links: status=PENDING.
    - Programmatic suggestions never invent quotes; quote_available=False when none.
    """
    schema = EXPERIENCE_FIELD_SCHEMAS.get(target_type) or []
    values = experience_values(target_type, experience)
    if not schema or not values:
        return []

    stored_by_key = {
        str(row.get("key")): row
        for row in (stored_checks or [])
        if isinstance(row, dict) and row.get("key")
    }
    field_map = clean_normalized_fields(fields)
    evidence_blob = "\n".join(
        part for part in (
            corpus or "",
            " ".join(field_map.values()),
        ) if part
    )
    norm_blob = _norm(evidence_blob)
    use_stored = stored_checks is not None and not force_pending

    rows: list[dict[str, Any]] = []
    for key, label in schema:
        exp_value = values.get(key)
        if not exp_value:
            continue

        if force_pending:
            rows.append(_field_row(key, label, exp_value, FIELD_STATUS_PENDING, None, False, "legacy"))
            continue

        if use_stored:
            prev = stored_by_key.get(key)
            if not prev:
                rows.append(_field_row(key, label, exp_value, FIELD_STATUS_PENDING, None, False, "legacy"))
                continue
            status = str(prev.get("status") or FIELD_STATUS_PENDING)
            if status not in FIELD_STATUS_LABELS:
                status = FIELD_STATUS_PENDING
            quote = str(prev.get("quote") or "") or None
            quote_available = bool(prev.get("quote_available")) if "quote_available" in prev else bool(quote)
            source = str(prev.get("source") or "user")
            rows.append(_field_row(key, label, exp_value, status, quote, quote_available, source))
            continue

        status, quote, source = _suggest_field_status(
            target_type, key, exp_value, field_map, evidence_blob, norm_blob
        )
        rows.append(_field_row(key, label, exp_value, status, quote, bool(quote), source))
    return rows


def pending_field_checks(target_type: str, experience: dict[str, Any]) -> list[dict[str, Any]]:
    """Legacy / unreviewed association: every filled field is 待核对."""
    return check_experience_fields(
        target_type,
        experience,
        fields={},
        corpus="",
        stored_checks=[],
        force_pending=True,
    )


def _field_row(
    key: str,
    label: str,
    experience_value: str,
    status: str,
    quote: str | None,
    quote_available: bool,
    source: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "experience_value": experience_value,
        "status": status,
        "status_label": FIELD_STATUS_LABELS.get(status, status),
        "quote": quote or "",
        "quote_available": quote_available,
        "quote_note": "" if quote_available else "原文定位不可用",
        "source": source,  # program | model | user | legacy
    }


def _suggest_field_status(
    target_type: str,
    key: str,
    exp_value: str,
    field_map: dict[str, str],
    evidence_blob: str,
    norm_blob: str,
) -> tuple[str, str | None, str]:
    """Heuristic only — never invents quotes. source=program."""
    # Direct field map equivalents
    aliases = {
        "name": ("name", "award_name", "title"),
        "award_name": ("award_name", "name"),
        "company": ("company", "organization", "issuer"),
        "organization": ("organization", "company", "issuer"),
        "title": ("title", "role"),
        "role": ("role", "title"),
        "period": ("period", "date"),
        "date": ("date", "period"),
        "issuer": ("issuer",),
        "grade": ("grade",),
        "recipient": ("recipient",),
        "department": ("department",),
        "tech_stack": ("tech_stack",),
        "outcomes": ("outcomes",),
        "responsibilities": ("responsibilities", "duties"),
        "duties": ("duties", "responsibilities"),
    }
    mapped = ""
    for alias in aliases.get(key, (key,)):
        if field_map.get(alias):
            mapped = field_map[alias]
            break

    if key == "grade" and mapped and exp_value:
        if _norm(mapped) == _norm(exp_value) or exp_value in mapped or mapped in exp_value:
            quote = _find_quote(evidence_blob, mapped) or mapped
            return FIELD_STATUS_SUPPORTED, quote, "program"
        mapped_grade = _GRADE.search(mapped)
        exp_grade = _GRADE.search(exp_value)
        if mapped_grade and exp_grade and mapped_grade.group(1) != exp_grade.group(1):
            quote = _find_quote(evidence_blob, mapped) or mapped
            return FIELD_STATUS_CONFLICT, quote, "program"

    if key in {"date", "period"} and mapped:
        ey = _year_tokens(exp_value)
        my = _year_tokens(mapped)
        if ey and my and ey.isdisjoint(my):
            quote = _find_quote(evidence_blob, mapped) or mapped
            return FIELD_STATUS_CONFLICT, quote, "program"

    # Token overlap against corpus / mapped field
    needles = [exp_value]
    if key in {"tech_stack", "responsibilities", "duties", "outcomes"}:
        needles = [t for t in re.split(r"[\s,，、；;|/]+", exp_value) if len(t) >= 2] or [exp_value]

    for needle in needles:
        if len(needle) >= 2 and (_norm(needle) in norm_blob or needle.lower() in evidence_blob.lower()):
            quote = _find_quote(evidence_blob, needle)
            return FIELD_STATUS_SUPPORTED, quote, "program"
        if mapped and (_norm(needle) in _norm(mapped) or _norm(mapped) in _norm(needle)):
            quote = _find_quote(evidence_blob, mapped) or mapped
            return FIELD_STATUS_SUPPORTED, quote, "program"

    # Soft support: ≥2 overlapping tokens for long descriptions
    if key in {"responsibilities", "duties", "outcomes"}:
        hits = _tokens(exp_value) & _tokens(evidence_blob)
        if len(hits) >= 2:
            sample = sorted(hits, key=len, reverse=True)[0]
            quote = _find_quote(evidence_blob, sample)
            return FIELD_STATUS_SUPPORTED, quote, "program"

    if target_type == "award" and key == "award_name":
        # Grade mismatch already handled; name missing → not mentioned
        g = _GRADE.search(evidence_blob)
        if g and g.group(1) not in exp_value and _GRADE.search(exp_value):
            eg = _GRADE.search(exp_value)
            if eg and eg.group(1) != g.group(1):
                quote = _find_quote(evidence_blob, g.group(1))
                return FIELD_STATUS_CONFLICT, quote, "program"

    return FIELD_STATUS_NOT_MENTIONED, None, "program"


def summarize_field_checks(checks: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        FIELD_STATUS_SUPPORTED: 0,
        FIELD_STATUS_NOT_MENTIONED: 0,
        FIELD_STATUS_CONFLICT: 0,
        FIELD_STATUS_PENDING: 0,
    }
    for row in checks:
        status = str(row.get("status") or FIELD_STATUS_PENDING)
        if status in summary:
            summary[status] += 1
        else:
            summary[FIELD_STATUS_PENDING] += 1
    return summary


def editor_fields_for_material(kind: str) -> list[tuple[str, str]]:
    """Optional extractable fields shown when reviewing a material (not experience checks)."""
    if kind in {"AWARD_CERTIFICATE", "CERTIFICATE"}:
        return [
            ("recipient", "获奖人 / 持有人"),
            ("award_name", "证书 / 奖项名称"),
            ("grade", "级别"),
            ("issuer", "颁发单位"),
            ("date", "日期"),
        ]
    if kind == "INTERNSHIP_CERTIFICATE":
        return [
            ("company", "公司"),
            ("department", "部门"),
            ("title", "岗位"),
            ("period", "实习时间"),
            ("issuer", "证明出具方"),
        ]
    if kind in {"PROJECT_REPORT", "CODE_REPO", "WORK_PRODUCT"}:
        return [
            ("name", "项目 / 成果名称"),
            ("organization", "所属组织"),
            ("role", "个人角色"),
            ("period", "时间"),
            ("tech_stack", "技术栈"),
            ("outcomes", "成果与指标"),
        ]
    return [
        ("material_label", "材料标题"),
        ("organization", "相关组织"),
        ("period", "相关时间"),
    ]
