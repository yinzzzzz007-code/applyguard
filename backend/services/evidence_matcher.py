from __future__ import annotations

import re
from calendar import monthrange
from datetime import date
from typing import Any

from backend.services.jd_match_scope import select_requirements_for_matching
from backend.services.resume_draft_vault import is_form_confirmed_evidence


_NON_ALNUM = re.compile(r"[^a-z0-9+#.]+")
# Keep CJK / fullwidth letters so Chinese JD terms are not wiped to empty strings.
_KEEP_CHARS = re.compile(r"[^a-z0-9+#.\u3400-\u9fff]+")
_ALIASES = {
    "rest api": "http api",
    "restful api": "http api",
    "automated tests": "automated testing",
    "unit testing": "automated testing",
    "unit tests": "automated testing",
    "node": "node.js",
    "nodejs": "node.js",
    "postgres": "postgresql",
    "large language model": "llm",
    "large language models": "llm",
    "llm fine tuning": "llm fine tuning",
    "etl pipeline": "etl",
    "etl pipelines": "etl",
    "data pipeline": "data pipelines",
    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "reactjs": "react",
    "ember": "emberjs",
}
_MENTION_VARIANTS = {
    "data pipelines": {"etl pipeline", "etl pipelines"},
    "llm fine tuning": {"fine tuned a language model"},
    "pytorch": {"pytorch", "py torch"},
    "tensorflow": {"tensorflow", "tensor flow"},
}
# Chinese JD phrases → English vault terms (deterministic soft bridges, not free semantics).
_CJK_BRIDGES = {
    "本科": {"bsc", "bachelor", "undergraduate", "student"},
    "学历": {"bsc", "bachelor", "degree", "student"},
    "计算机": {"software", "computer", "engineering", "python"},
    "人工智能": {"machine learning", "llm", "pytorch", "model evaluation"},
    "数据科学": {"computer", "software", "python", "machine learning", "data pipelines"},
    "大数据": {"computer", "software", "python", "data pipelines", "machine learning"},
    "数学": {"math", "mathematics"},
    "深度学习": {"pytorch", "machine learning", "model evaluation", "llm"},
    "机器学习": {"pytorch", "machine learning", "model evaluation", "llm"},
    "推荐系统": {"machine learning", "model evaluation", "pytorch", "llm"},
    "推荐": {"machine learning", "model evaluation", "pytorch"},
    "召回": {"machine learning", "model evaluation"},
    "排序": {"machine learning", "model evaluation"},
    "模型算法": {"pytorch", "model evaluation", "llm", "machine learning"},
    "模型": {"pytorch", "model evaluation", "llm"},
    "编程": {"python", "java", "c++", "typescript"},
    "神经网络": {"pytorch", "machine learning", "llm"},
    "多模态": {"llm", "machine learning", "model evaluation"},
    "强化学习": {"machine learning", "model evaluation", "pytorch"},
    "自动化测试": {"automated testing"},
    "接口服务": {"http api"},
    "数据处理": {"data pipelines", "etl"},
    "数据管道": {"data pipelines", "etl"},
    "后端开发": {"python", "http api"},
    "版本协作": {"git"},
    "版本控制": {"git"},
    "微调": {"llm fine tuning"},
    "评测": {"model evaluation"},
}

# Majors that satisfy「计算机 / 软件 / 人工智能或相关专业」on Chinese internship JDs.
_CS_RELATED_MAJOR_MARKERS = (
    "计算机", "软件工程", "软件技术", "人工智能", "智能科学", "数据科学", "大数据",
    "网络工程", "信息安全", "物联网", "电子信息", "信息工程", "计算机科学", "信息管理",
)

# English requirement terms → Chinese vault wording (skills stay English).
_EN_CJK_VARIANTS = {
    "automated testing": ("自动化测试", "单元测试"),
    "http api": ("接口服务",),
    "git": ("版本协作", "版本控制"),
    "data pipelines": ("数据管道", "数据处理"),
    "etl": ("数据管道",),
    "data quality": ("数据质量",),
    "model evaluation": ("评测",),
    "llm fine tuning": ("微调",),
    "machine learning": ("机器学习",),
}


def _plain_normalise(value: str) -> str:
    return _NON_ALNUM.sub(" ", value.casefold()).strip()


def _term_normalise(value: str) -> str:
    return _KEEP_CHARS.sub(" ", value.casefold()).strip()


def _normalise(value: str) -> str:
    cleaned = _term_normalise(value)
    if not cleaned:
        return ""
    ascii_form = _plain_normalise(value)
    if ascii_form:
        return _ALIASES.get(ascii_form, ascii_form)
    return cleaned


def _has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def _cs_related_major_in(text: str) -> bool:
    fold = (text or "").casefold()
    return any(marker.casefold() in fold for marker in _CS_RELATED_MAJOR_MARKERS)


def _requirement_asks_related_cs_major(requirement: dict[str, Any], terms: set[str]) -> bool:
    blob = f"{requirement.get('text') or ''} {requirement.get('evidence_text') or ''} {' '.join(terms)}"
    return any(key in blob for key in ("计算机", "人工智能", "软件工程", "软件相关", "数据科学", "大数据"))


_DEGREES = (r"专科|大专|associate", r"本科|学士|bachelor", r"硕士|master", r"博士|ph\.?d\.?|doctorate")
_GRADUATION_DAY = re.compile(r"(20\d{2})[.\-/年](\d{1,2})[.\-/月](\d{1,2})")


def _education_checks(requirement: dict[str, Any], degree: str, major: str, end: str) -> list[dict[str, str]]:
    text = str(requirement.get("evidence_text") or requirement.get("text") or "")
    checks = []
    minimum = next((i for i, pattern in enumerate(_DEGREES) if re.search(pattern, text, re.I)), None)
    if minimum is not None:
        level = next((i for i, pattern in enumerate(_DEGREES) if re.search(pattern, degree, re.I)), None)
        checks.append({"label": "学历", "value": degree, "state": (
            "UNKNOWN" if level is None else "MATCH" if level >= minimum else "MISMATCH")})
    if "相关专业" in text:
        related = _requirement_asks_related_cs_major(requirement, set()) and _cs_related_major_in(major)
        checks.append({"label": "相关专业", "value": major, "state": "MATCH" if related else "UNKNOWN"})
    dates = _GRADUATION_DAY.findall(text) if "毕业" in text else []
    if len(dates) == 2:
        state = "UNKNOWN"
        try:
            lower, upper = (date(*map(int, parts)) for parts in dates)
            if lower <= upper and re.fullmatch(r"\d{4}-\d{2}", end):
                year, month = map(int, end.split("-"))
                first, last = date(year, month, 1), date(year, month, monthrange(year, month)[1])
                if lower <= first and last <= upper:
                    state = "MATCH"
                elif last < lower or first > upper:
                    state = "MISMATCH"
        except ValueError:
            pass
        checks.append({"label": "毕业时间窗口", "value": end, "state": state})
    elif re.search(r"20\d{2}\s*届", text) and "毕业" in text:
        checks.append({"label": "毕业届别", "value": end, "state": "UNKNOWN"})
    return checks


def profile_checks(parsed: dict[str, Any], form: Any) -> dict[str, list[dict[str, str]]]:
    """Separate self-reported profile signals from claim evidence and approvals."""
    if not isinstance(form, dict):
        return {}
    extras = form.get("extras")
    skills = str(extras.get("skills") or "") if isinstance(extras, dict) else ""
    result = {}
    for req in select_requirements_for_matching(parsed):
        if req["category"] == "EDUCATION":
            options = [_education_checks(req, str(row.get("degree") or ""), str(row.get("major") or ""),
                       str(row.get("end") or "")) for row in form.get("education") or [] if isinstance(row, dict)]
            checks = max(options, key=lambda rows: (all(row["state"] == "MATCH" for row in rows),
                         sum(row["state"] == "MATCH" for row in rows)), default=[])
            if checks:
                result[req["requirement_id"]] = checks
        elif req["category"] in {"SKILL", "RESPONSIBILITY"}:
            found = [term for term in req["normalized_terms"]
                     if (term in skills if _has_cjk(term) else _mentions(_normalise(term), skills))]
            if found:
                result[req["requirement_id"]] = [{"label": "技能栏本人填写", "value": "、".join(found), "state": "DECLARED"}]
    return result


def _mentions(term: str, text: str) -> bool:
    """Match complete terms, CJK substrings, aliases, or explicit CJK→EN bridges."""
    if not term or not text:
        return False
    normalised_text = _plain_normalise(text)
    raw_fold = text.casefold()
    if _has_cjk(term):
        if term.casefold() in raw_fold:
            return True
        bridges = _CJK_BRIDGES.get(term) or {
            bridge for key, vals in _CJK_BRIDGES.items() if key in term for bridge in vals
        }
        return any(_mentions(bridge, text) for bridge in bridges)
    if any(phrase in raw_fold for phrase in _EN_CJK_VARIANTS.get(term, ())):
        return True
    if term == "model evaluation":
        return bool(
            re.search(r"(?<![a-z0-9+#])model(?![a-z0-9+#])", normalised_text)
            and re.search(r"(?<![a-z0-9+#])evaluation(?![a-z0-9+#])", normalised_text)
        )
    if term == "react":
        normalised_text = re.sub(r"\breact native\b", "", normalised_text)
    variants = {term, *_MENTION_VARIANTS.get(term, set())}
    variants.update(alias for alias, canonical in _ALIASES.items() if canonical == term)
    return any(
        re.search(rf"(?<![a-z0-9+#]){re.escape(variant)}(?![a-z0-9+#])", normalised_text)
        for variant in variants
        if variant
    )


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


class EvidenceMatcher:
    """A deterministic, explainable proposal baseline; it does not parse JD text.

    When the JD marks 任职要求 / 加分项 separately from 职位描述, only the first
    two sections are scored. Unsectioned text is left unchanged.
    """

    def match(self, parsed_jd: dict[str, Any], experiences: list[dict[str, Any]]) -> dict[str, Any]:
        candidate_ids = {experience["candidate_id"] for experience in experiences}
        if len(candidate_ids) != 1:
            raise ValueError("Evidence Matcher requires experiences from exactly one candidate")
        candidate_id = next(iter(candidate_ids))
        matches: list[dict[str, Any]] = []
        uncovered: list[dict[str, Any]] = []

        for requirement in select_requirements_for_matching(parsed_jd):
            requirement_terms = self._requirement_terms(requirement)
            if not requirement_terms:
                uncovered.append(
                    {
                        "requirement_id": requirement["requirement_id"],
                        "missing_evidence": ["No normalized requirement terms were supplied by the parsed-JD fixture."],
                        "reason": "The deterministic matcher cannot evaluate an unnormalized requirement.",
                    }
                )
                continue

            requirement_matches = [
                result
                for experience in experiences
                if (result := self._score_requirement(requirement, requirement_terms, experience)) is not None
            ]
            requirement_matches.sort(key=lambda item: (-item["relevance_score"], item["experience_id"]))
            matches.extend(requirement_matches)

            if not any(result["ready_for_selection"] for result in requirement_matches):
                uncovered.append(
                    {
                        "requirement_id": requirement["requirement_id"],
                        "missing_evidence": self._uncovered_notes(requirement_matches),
                        "reason": "No experience has sufficiently verified, conflict-free evidence for selection.",
                    }
                )

        return {
            "match_id": f"match_{parsed_jd['jd_id'].removeprefix('jd_')}_{candidate_id.removeprefix('cand_')}",
            "jd_id": parsed_jd["jd_id"],
            "candidate_id": candidate_id,
            "matches": matches,
            "uncovered_requirements": uncovered,
        }

    @staticmethod
    def _requirement_terms(requirement: dict[str, Any]) -> set[str]:
        terms: set[str] = set()
        raw_terms = requirement.get("normalized_terms", [])
        for term in raw_terms:
            if isinstance(term, str) and term.strip():
                normalised = _normalise(term)
                if normalised:
                    terms.add(normalised)
        text = requirement.get("text") or requirement.get("evidence_text") or ""
        # Only enrich from prose for Chinese JDs; English fixtures must keep exact term sets.
        has_cjk = _has_cjk(text if isinstance(text, str) else "") or any(
            isinstance(term, str) and _has_cjk(term) for term in raw_terms
        )
        if has_cjk and isinstance(text, str):
            for token in re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,24}", text):
                normalised = _normalise(token)
                if normalised:
                    terms.add(normalised)
            for cjk in re.findall(r"[\u3400-\u9fff]{2,12}", text):
                if cjk in _CJK_BRIDGES:
                    terms.add(cjk)
        return terms

    def _score_requirement(
        self,
        requirement: dict[str, Any],
        requirement_terms: set[str],
        experience: dict[str, Any],
    ) -> dict[str, Any] | None:
        claims = [
            claim for claim in experience.get("claims", [])
            if any(_mentions(term, claim["text"]) for term in requirement_terms)
        ]
        if requirement.get("category") == "EDUCATION":
            source_ids = {source["evidence_id"] for source in experience.get("evidence_sources", [])
                          if is_form_confirmed_evidence(source)}
            if source_ids:
                claims = [claim for claim in experience.get("claims", [])
                          if source_ids.intersection(claim.get("evidence_ids", []))]
        if not claims:
            return None
        return self.score_linked_claims(requirement, requirement_terms, experience, claims)

    def score_linked_claims(
        self,
        requirement: dict[str, Any],
        requirement_terms: set[str],
        experience: dict[str, Any],
        claims: list[dict[str, Any]],
        *,
        semantic_score: float | None = None,
        model_rationale: str | None = None,
        require_keyword_hit: bool = True,
    ) -> dict[str, Any] | None:
        """Score an explicit claim set; optional AI semantic_score may relax term-gap notes."""
        if not claims:
            return None
        skill_terms = {term for skill in experience.get("skills", []) if (term := _normalise(skill))}
        responsibility_text = " ".join(
            [experience.get("summary", ""), *experience.get("responsibilities", []), experience.get("title", ""), experience.get("role", "")]
        )
        claim_blob = " ".join(
            str(part)
            for part in (
                experience.get("title", ""),
                experience.get("organization", ""),
                experience.get("summary", ""),
                *(claim.get("text") or "" for claim in claims),
            )
        )
        personal_education = requirement.get("category") == "EDUCATION" and any(
            is_form_confirmed_evidence(source) for source in experience.get("evidence_sources", []))
        education = _education_checks(requirement, experience.get("title", ""), claim_blob,
                                      experience.get("end_date") or "") if personal_education else []
        profile_match = bool(education) and all(check["state"] == "MATCH" for check in education)
        related_major_hit = (not education or profile_match) and _requirement_asks_related_cs_major(requirement, requirement_terms) and _cs_related_major_in(
            claim_blob
        )
        supported_terms = {
            term for term in requirement_terms if any(_mentions(term, claim["text"]) for claim in claims)
        }
        if related_major_hit:
            for term in requirement_terms:
                if any(key in term for key in ("计算机", "人工智能", "软件", "相关专业", "本科", "学历", "专业")):
                    supported_terms.add(term)
        keyword_hits = sorted(
            term
            for term in supported_terms
            if term in skill_terms or any(_mentions(term, skill) for skill in experience.get("skills", []))
        )
        responsibility_hits = sorted(term for term in supported_terms if _mentions(term, responsibility_text))
        if related_major_hit and "相关专业" not in responsibility_hits:
            responsibility_hits = sorted({*responsibility_hits, "相关专业"})
        if require_keyword_hit and not keyword_hits and not responsibility_hits and semantic_score is None and not (related_major_hit or education):
            return None
        claim_ids = list(dict.fromkeys(claim["claim_id"] for claim in claims))
        evidence_ids = sorted({evidence_id for claim in claims for evidence_id in claim.get("evidence_ids", [])})
        sources = experience.get("evidence_sources", [])
        source_by_id = {source["evidence_id"]: source for source in sources}
        linked_sources = [source_by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in source_by_id]
        source_confidences = [float(source.get("confidence", 0.0)) for source in linked_sources]
        claim_confidences = [float(claim.get("confidence", 0.0)) for claim in claims]
        confidence_score = min([*source_confidences, *claim_confidences], default=0.0) if linked_sources else 0.0

        conflicts = self._conflicts(experience, claims, linked_sources)
        missing_evidence = self._missing_evidence(experience, claims, linked_sources)
        missing_evidence.extend(f"个人资料待核对：{check['label']}（{check['value'] or '未填写'}）"
                                for check in education if check["state"] != "MATCH")
        unsupported = requirement_terms - supported_terms
        requirement_text = requirement.get("text", "")
        language_alternatives = re.search(r"至少一门编程语言|at least one programming language", requirement_text, re.I)
        if language_alternatives:
            # The languages listed after “for example” are alternatives.
            if supported_terms:
                unsupported = set()
        unsupported_terms = sorted(unsupported)
        # AI may attest paraphrase coverage; still never invent evidence IDs or clear verification gaps.
        ai_covers_terms = isinstance(semantic_score, (int, float)) and float(semantic_score) >= 0.55
        if related_major_hit or profile_match:
            ai_covers_terms = True
        if unsupported_terms and not ai_covers_terms:
            missing_evidence.append(f"No linked claim explicitly supports: {', '.join(unsupported_terms)}.")
        verification_score = self._verification_score(experience, claims, linked_sources)
        term_denom = max(len(supported_terms if language_alternatives and supported_terms else requirement_terms), 1)
        keyword_overlap = len(keyword_hits) / term_denom
        responsibility_overlap = len(responsibility_hits) / term_denom
        metric_bonus = 0.1 if any(
            set(metric.get("evidence_ids", [])).intersection(evidence_ids)
            for metric in experience.get("metrics", [])
        ) else 0.0
        conflict_penalty = 0.3 if conflicts else 0.0
        missing_penalty = 0.25 if missing_evidence else 0.0
        if missing_evidence and (keyword_hits or responsibility_hits or ai_covers_terms) and (
            any(_has_cjk(term) for term in requirement_terms) or ai_covers_terms
        ):
            missing_penalty = min(missing_penalty, 0.1)
        lexical = _clamp(
            0.45 * keyword_overlap
            + 0.15 * responsibility_overlap
            + 0.15 * verification_score
            + 0.15 * confidence_score
            + metric_bonus
            - conflict_penalty
            - missing_penalty
        )
        if isinstance(semantic_score, (int, float)):
            semantic = _clamp(float(semantic_score))
        else:
            semantic = None
        # 数据科学 / 大数据等对「相关专业」按强覆盖处理，避免模型保守打成中等分。
        if related_major_hit or profile_match:
            semantic = max(semantic or 0.0, 0.95)
        if semantic is not None:
            # Prefer the model score so keyword sparsity does not crush on-topic matches.
            relevance = _clamp(0.15 * lexical + 0.85 * semantic - conflict_penalty * 0.5)
        else:
            relevance = lexical
            if related_major_hit:
                relevance = max(relevance, 0.9)
        evidence_strength = self._evidence_strength(relevance, verification_score, confidence_score, conflicts, missing_evidence)
        ready_for_selection = evidence_strength == "STRONG" and not conflicts and not missing_evidence
        rationale = self._rationale(keyword_hits, responsibility_hits, evidence_ids, conflicts, missing_evidence)
        if related_major_hit:
            rationale = f"{rationale} 相关专业：数据科学/计算机类专业视为满足相关专业要求。"
        if model_rationale:
            rationale = f"{rationale} AI: {model_rationale.strip()[:180]}"
        breakdown = {
            "keyword_overlap": _clamp(keyword_overlap),
            "responsibility_overlap": _clamp(responsibility_overlap),
            "verification_score": _clamp(verification_score),
            "confidence_score": _clamp(confidence_score),
            "metric_bonus": metric_bonus,
            "conflict_penalty": conflict_penalty,
            "missing_evidence_penalty": missing_penalty,
        }
        if semantic is not None:
            breakdown["ai_semantic_score"] = _clamp(semantic)
            breakdown["ai_score_10"] = round(_clamp(semantic) * 10.0, 1)
        return {
            "requirement_id": requirement["requirement_id"],
            "experience_id": experience["experience_id"],
            "claim_ids": claim_ids,
            "relevance_score": relevance,
            "evidence_strength": evidence_strength,
            "confidence": _clamp((verification_score + confidence_score) / 2),
            "rationale": rationale,
            "conflicts": conflicts,
            "evidence_ids": evidence_ids,
            "missing_evidence": missing_evidence,
            "ready_for_selection": ready_for_selection,
            "score_breakdown": breakdown,
        }

    @staticmethod
    def _conflicts(
        experience: dict[str, Any], claims: list[dict[str, Any]], sources: list[dict[str, Any]]
    ) -> list[str]:
        conflicts: list[str] = []
        for source in sources:
            if source.get("verification_status") == "CONFLICTING":
                conflicts.append(f"Evidence {source['evidence_id']} is marked CONFLICTING.")
        return sorted(conflicts)

    @staticmethod
    def _missing_evidence(
        experience: dict[str, Any], claims: list[dict[str, Any]], sources: list[dict[str, Any]]
    ) -> list[str]:
        missing: list[str] = []
        if experience.get("verification_state") != "VERIFIED" or any(claim.get("verification_state") != "VERIFIED" for claim in claims):
            missing.append("Experience or claim still needs evidence review.")
        if not claims:
            missing.append("No claim is stored for this experience.")
        if not sources:
            missing.append("No evidence source is linked to the matching claim(s).")
        elif any(source.get("verification_status") != "VERIFIED" for source in sources):
            missing.append("A linked evidence source is not VERIFIED.")
        linked_ids = {source["evidence_id"] for source in sources}
        if any(not set(claim.get("evidence_ids", [])).issubset(linked_ids) for claim in claims):
            missing.append("A claim references an evidence_id absent from this experience.")
        return missing

    @staticmethod
    def _verification_score(
        experience: dict[str, Any], claims: list[dict[str, Any]], sources: list[dict[str, Any]]
    ) -> float:
        states = [experience.get("verification_state")]
        states.extend(claim.get("verification_state") for claim in claims)
        states.extend(source.get("verification_status", "UNVERIFIED") for source in sources)
        values = {"VERIFIED": 1.0, "PARTIALLY_VERIFIED": 0.6, "NEEDS_REVIEW": 0.4, "UNVERIFIED": 0.2, "CONFLICTING": 0.0}
        return sum(values.get(state, 0.0) for state in states) / len(states) if states else 0.0

    @staticmethod
    def _evidence_strength(
        relevance: float,
        verification: float,
        confidence: float,
        conflicts: list[str],
        missing: list[str],
    ) -> str:
        if relevance >= 0.65 and verification >= 0.8 and confidence >= 0.75 and not conflicts and not missing:
            return "STRONG"
        if relevance >= 0.35 and not conflicts:
            return "MEDIUM"
        return "WEAK"

    @staticmethod
    def _rationale(
        keyword_hits: list[str],
        responsibility_hits: list[str],
        evidence_ids: list[str],
        conflicts: list[str],
        missing: list[str],
    ) -> str:
        parts = [f"Skill overlap: {', '.join(keyword_hits) or 'none'}."]
        if responsibility_hits:
            parts.append(f"Responsibility overlap: {', '.join(responsibility_hits)}.")
        parts.append(f"Linked evidence: {', '.join(evidence_ids) or 'none'}.")
        if conflicts:
            parts.append("Conflict penalty applied.")
        if missing:
            parts.append("Missing-evidence penalty applied.")
        return " ".join(parts)

    @staticmethod
    def _uncovered_notes(matches: list[dict[str, Any]]) -> list[str]:
        notes = {note for match in matches for note in match["missing_evidence"]}
        if any(match["conflicts"] for match in matches):
            notes.add("Conflicting or unverified evidence prevents selection.")
        if any(not match["ready_for_selection"] for match in matches):
            notes.add("Matching claim confidence or verification is below the selection threshold.")
        if not notes:
            notes.add("No claim with linked evidence states this requirement.")
        return sorted(notes)
