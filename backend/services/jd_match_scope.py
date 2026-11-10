"""Keep evidence matching on 任职要求 and 加分项, not 职位描述."""

from __future__ import annotations

import re
from typing import Any


# Longer labels come first so 工作职责 is not read as 职责.
_HEADER = re.compile(
    r"^\s*(?:[【\[（(]\s*)?(?:(?:[一二三四五六七八九十]+|\d{1,2})\s*[、.．]\s*)?"
    r"(?P<label>加分项或注意事项|加分项|优先条件|nice[\s-]to[\s-]have|"
    r"preferred(?:\s+(?:qualifications|requirements|skills))?|bonus|"
    r"任职资格|任职要求|岗位要求|工作要求|基本要求|"
    r"required(?:\s+(?:qualifications|skills))?|requirements|qualifications|"
    r"职位描述|岗位描述|工作职责|岗位职责|工作内容|job\s+description|responsibilities|职责|"
    r"面向对象|招聘对象)"
    r"\s*(?:[】\])）)])?\s*[:：]?(?=\s|$)",
    re.IGNORECASE,
)
_BONUS = {"加分项或注意事项", "加分项", "优先条件", "nice to have", "nice-to-have", "bonus"}
_DESCRIPTION = {
    "职位描述", "岗位描述", "工作职责", "岗位职责", "工作内容", "职责",
    "job description", "responsibilities",
}
_OTHER = {"面向对象", "招聘对象"}


def qualification_spans(source: str) -> list[tuple[int, int]] | None:
    """Return 任职要求/加分项 ranges.

    ``None`` means the JD has no section headers, so matching keeps every
    parsed requirement. An empty list means a 职位描述 (or similar) section
    exists and nothing is in scope.
    """
    if not isinstance(source, str) or not source:
        return None
    headers = _headers(source)
    kinds = {kind for _, kind in headers}
    if "requirement" not in kinds and "bonus" not in kinds:
        return [] if "description" in kinds else None
    spans: list[tuple[int, int]] = []
    for index, (start, kind) in enumerate(headers):
        end = headers[index + 1][0] if index + 1 < len(headers) else len(source)
        if kind in {"requirement", "bonus"}:
            spans.append((start, end))
    return spans


def select_requirements_for_matching(parsed_jd: dict[str, Any]) -> list[dict[str, Any]]:
    """Requirements whose quote sits in 任职要求 or 加分项."""
    requirements = [item for item in parsed_jd.get("requirements") or [] if isinstance(item, dict)]
    source = parsed_jd.get("source_text")
    if not isinstance(source, str):
        return requirements
    spans = qualification_spans(source)
    if spans is None:
        return requirements
    return [item for item in requirements if _quote_in_spans(source, _quote(item), spans)]


def _headers(source: str) -> list[tuple[int, str]]:
    headers: list[tuple[int, str]] = []
    offset = 0
    for line in source.splitlines(keepends=True):
        kind = _header_kind(line)
        if kind:
            headers.append((offset, kind))
        offset += len(line)
    return headers


def _header_kind(line: str) -> str | None:
    matched = _HEADER.match(line)
    if not matched:
        return None
    label = re.sub(r"\s+", " ", matched.group("label").casefold())
    if label in _OTHER:
        return "other"
    if label in _DESCRIPTION:
        return "description"
    if label in _BONUS or label.startswith("preferred"):
        return "bonus"
    return "requirement"


def _quote(item: dict[str, Any]) -> str:
    evidence = item.get("evidence_text")
    if isinstance(evidence, str) and evidence.strip():
        return evidence
    text = item.get("text")
    return text if isinstance(text, str) else ""


def _quote_in_spans(source: str, quote: str, spans: list[tuple[int, int]]) -> bool:
    if not quote or not spans:
        return False
    start = 0
    while start <= len(source):
        index = source.find(quote, start)
        if index < 0:
            return False
        end = index + len(quote)
        if any(span_start <= index and end <= span_end for span_start, span_end in spans):
            return True
        start = index + 1
