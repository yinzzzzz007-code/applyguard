"""Explain role fit using the same source units and project vocabulary as the match page."""
from __future__ import annotations

import re
from functools import lru_cache
from backend.services.job_capabilities import concepts, framework_group, job_units, priority, qualifications
from backend.services.experience_relevance import match_passage, tokens

SPECIALTIES = {"训练推理基础设施", "材料研发", "具身机器人", "海关贸易", "供应链履约", "机械设计", "信息安全", "金融研究"}

@lru_cache(maxsize=512)
def sections(description, duties, requirements):
    parts = list(job_units(description))
    if duties:
        parts.extend(job_units(duties, "description"))
    if requirements:
        parts.extend(job_units(requirements, "requirement"))
    if not parts:
        parts = list(job_units(description, "description"))
    return tuple(dict.fromkeys((section, part) for section, phrase in parts
                               for part in ([phrase] if section == "description" else qualifications(phrase))))


def job_sections(job):
    return sections(*(str(job.get(k) or "") for k in ("description", "responsibilities", "requirements")))


def project_profile(resume):
    rows = []
    for kind in ("projects", "internships"):
        for row in (resume or {}).get(kind, []):
            title = str(row.get("title") or row.get("organization") or row.get("role") or "经历")
            body = " ".join(str(row.get(k) or "") for k in ("title", "role", "techStack", "description"))
            rows.append((title, body))
    return tuple(rows)


@lru_cache(maxsize=4096)
def compare(title, units, profile):
    if not profile:
        return None, (), 0.0
    ranked = []
    missing = []
    known = frozenset().union(*(concepts(body) for _, body in profile))
    grades = {"title": [], "description": [], "requirement": []}
    for section, phrase in (("title", title), *units):
        importance = priority(phrase, section)
        weight = {"general": .12, "preferred": .45, "core": 1}[importance]
        if section == "title" and not (concepts(phrase) or tokens(phrase)):
            continue
        if section == "description" and importance == "core":
            missing.extend(sorted(concepts(phrase) - known))
        winner = None
        for project, body in profile:
            # Keep negation local to each sentence rather than dropping a whole project.
            for passage in re.split(r"[。；;\n]", body):
                if not passage.strip():
                    continue
                hit = match_passage(phrase, passage)
                if hit:
                    fraction = len(concepts(phrase) & concepts(passage)) / max(1, len(concepts(phrase)))
                    score = hit[0] * (.45 + .55 * fraction) if hit[1] == "direct" else hit[0] * .58
                    if winner is None or score > winner[0]:
                        winner = (score, project, hit)
        grades["requirement" if section == "bonus" else section].append((winner[0] if winner else 0, weight))
        if winner and section != "title":
            score, project, hit = winner
            label = "、".join(hit[2][:3])
            reason = (f"{project} 有训练经历，所用框架待确认" if hit[1] == "framework"
                      else f"{label}对应「{project}」")
            ranked.append((score * weight * (1.3 if section == "description" else 1), reason))
    values = [(sum(s*w for s,w in group) / sum(w for _,w in group), part)
              for name,part in (("title", .23), ("description", .53), ("requirement", .24))
              if (group := grades[name])]
    if not values:
        return None, (), 0.0
    score = 100 * sum(s*w for s,w in values) / sum(w for _,w in values)
    core_duties = [value for value, weight in grades["description"] if weight == 1]
    if core_duties:
        covered = sum(value >= .35 for value in core_duties) / len(core_duties)
        score *= .65 + .35 * covered
    reasons = tuple(dict.fromkeys(r for _,r in sorted(ranked, reverse=True)))
    domain_penalty = 0.0
    specialties = concepts(title) & SPECIALTIES
    if specialties:
        aligned = specialties & known
        if aligned:
            score += (100 - score) * .20
            reasons = ("岗位主方向与项目记录相符：" + "、".join(sorted(aligned)), *reasons)
        elif core_duties:
            domain_penalty = 18 * max(0, 1 - 2 * covered)
            reasons = (*reasons[:1], "岗位主方向待补证：" + "、".join(sorted(specialties)), *reasons[1:])
    if missing:
        gaps = "、".join(list(dict.fromkeys(missing))[:2])
        reasons = (*reasons[:2], f"经历库尚未明确记录：{gaps}")
    return score, reasons[:3], domain_penalty
