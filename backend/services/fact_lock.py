"""Source-bound facts and conservative edit checks for supported resume text.

This guard does not declare a proposal true. It only prevents a previously
supported detail from silently disappearing before the normal atomic verifier.
"""
from __future__ import annotations

import re
from collections import Counter

from backend.services.edit_invariants import equivalent_point_detail, lost_qualifiers

NUMBER = re.compile(r"(?<![0-9A-Za-z_.])-?\d+(?:\.\d+)?\s*(?:%|％|个百分点|percentage\s+points?|pp\b|"
                    r"milliseconds?\b|ms\b|毫秒|秒|人|个|次|年|万元|万|GB\b|MB\b)?", re.I)
TECH = re.compile(r"(?<![A-Za-z0-9])(?:Python|JavaScript|TypeScript|Java|C\+\+|C#|"
                  r"PostgreSQL|SQL|Vue|React|Redis|Docker|Kubernetes|PyTorch|TensorFlow|"
                  r"Go|Rust|Spark|Flink)(?![A-Za-z0-9])", re.I)
CLAUSE = re.compile(r"[，,；;。.!?\n]+")
ROLE = re.compile(r"(?P<person>[\u4e00-\u9fff]{1,6}?(?:同学)?|[A-Z][a-z]{1,18})\s*"
                  r"(?P<verb>只负责|仅负责|负责|实现|开发|主导|协助|led|built|"
                  r"implemented|developed|assisted|helped|supported|owned)", re.I)
REVERSE_ROLE = re.compile(r"(?P<item>[^，,；;。.!?\n]{1,30}?)由(?P<person>[\u4e00-\u9fff]{1,4}?)"
                          r"(?:协助)?(?:负责|开发|实现)")
OWNER = re.compile(r"(?P<person>[\u4e00-\u9fff]{2,4})(?:是|为|担任)(?:项目)?负责人")
PASSIVE_OWNER = re.compile(r"(?:该)?项目由(?P<person>[\u4e00-\u9fff]{2,4})(?:负责|牵头)")
NEGATIVE_ROLE = re.compile(r"(?:未|没有|不|并未)(?:参与|负责|开发|实现)")


def source_bound_ledger(original: str, check: dict | None, sources: list[dict]) -> list[dict]:
    """Expose only checked facts with exact quotes from the current source snapshot."""
    if not isinstance(check, dict) or not check.get("complete"):
        return []
    by_id = {s.get("source_id"): s for s in sources if isinstance(s, dict)}
    rows = []
    for atom in check.get("atoms", []):
        if atom.get("relation") != "SUPPORTED":
            continue
        citations = atom.get("citations", [])
        if not isinstance(citations, list) or not citations:
            continue
        bindings = []
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            source = by_id.get(citation.get("source_id"))
            quote = citation.get("quote")
            if (source and isinstance(quote, str) and len(quote.strip()) >= 3
                    and quote in source.get("text", "")
                    and citation.get("source_sha256") == source.get("sha256")
                    and citation.get("source_version") == source.get("version")):
                bindings.append({"source_id": source["source_id"], "quote": quote,
                                 "source_sha256": source["sha256"],
                                 "source_version": source["version"]})
        if len(bindings) == len(citations):
            rows.append({"atom_id": atom.get("atom_id"), "text": atom["text"],
                         "bindings": bindings})
    return rows


def _numeric_key(value: str) -> str:
    value = re.sub(r"\s+", "", value).casefold()
    return re.sub(r"milliseconds?|毫秒", "ms", value)


def _numbers(text: str) -> Counter:
    return Counter(_numeric_key(m.group()) for m in NUMBER.finditer(text))


def _relative_percent(text: str, value: str) -> bool:
    number = re.match(r"-?\d+(?:\.\d+)?", value)
    if not number:
        return False
    same = re.escape(number.group()) + r"\s*[%％]"
    return bool(re.search(r"(?:" + same + r".{0,18}(?:relative|相对)|"
                          r"(?:relative|相对).{0,18}" + same + r")", text, re.I))


def _technologies(text: str) -> set[str]:
    return {m.group().casefold() for m in TECH.finditer(text)}


def _role_pairs(text: str) -> set[tuple[str, str]]:
    """Preserve explicit person-to-technology links within the same clause."""
    pairs = set()
    for clause in CLAUSE.split(text):
        for match in ROLE.finditer(clause):
            if match["person"] in {"协助", "独立", "仅仅", "只", "仅", "未", "不", "没", "没有",
                                    "并未", "负责", "实现", "开发", "主导"}:
                continue
            # Stop at a second role declaration in the same clause.
            remainder = clause[match.end():]
            next_role = ROLE.search(remainder)
            if next_role:
                remainder = remainder[:next_role.start()]
            for tech in _technologies(remainder):
                pairs.add((match["person"].casefold(), tech))
        for match in REVERSE_ROLE.finditer(clause):
            for tech in _technologies(match["item"]):
                pairs.add((match["person"].casefold(), tech))
    return pairs


def _negative_role_tech(text: str) -> set[str]:
    denied = set()
    for clause in CLAUSE.split(text):
        for match in NEGATIVE_ROLE.finditer(clause):
            denied.update(_technologies(clause[match.end():match.end() + 35]))
    return denied


def locked_edit_findings(original: str, proposal: str, original_check: dict | None) -> list[str]:
    """Require review on provable losses, preserving ordinary paraphrase elsewhere."""
    if not isinstance(original_check, dict) or original_check.get("relation") != "SUPPORTED":
        return []
    findings = []
    if not original_check.get("complete"):
        return ["原句事实拆分不完整，不能自动采用润色。"]
    for item in lost_qualifiers(original, proposal):
        findings.append("遗漏已核验限定条件：" + item["detail"])
    old_numbers, new_numbers = _numbers(original), _numbers(proposal)
    old_forms = {_numeric_key(m.group()): m.group().strip()
                 for m in NUMBER.finditer(original)}
    for value in old_numbers - new_numbers:
        if (equivalent_point_detail(old_forms[value], original, proposal)
                and not _relative_percent(proposal, old_forms[value])):
            continue
        findings.append("遗漏或改变原有数字／单位：" + value)
    for tech in sorted(_technologies(original) - _technologies(proposal)):
        findings.append("遗漏原有技术：" + tech)
    for person, tech in sorted(_role_pairs(original) - _role_pairs(proposal)):
        findings.append("改变人物与技术的归属：" + person + " / " + tech)
    for tech in sorted(_negative_role_tech(original) - _negative_role_tech(proposal)):
        findings.append("删除未负责该技术的限制：" + tech)
    old_owners = {m["person"] for pattern in (OWNER, PASSIVE_OWNER)
                  for m in pattern.finditer(original)}
    new_owners = {m["person"] for pattern in (OWNER, PASSIVE_OWNER)
                  for m in pattern.finditer(proposal)}
    for person in sorted(old_owners - new_owners):
        findings.append("遗漏原文明确的负责人：" + person)
    return list(dict.fromkeys(findings))
