"""Parse one JD while checking every model-produced fact against its source."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from backend.services.model_client import ModelClient, ModelFailure
from backend.services.prompts import JD_PARSE_SYSTEM_PROMPT
from backend.services.schema_validation import validate_contract
from backend.services.third_party.resume_matcher_keywords import _sanitize_user_input, _validate_string_list_field


_TERMS = ("Python", "PyTorch", "LoRA", "React", "TypeScript", "Node.js", "PostgreSQL",
          "SQL", "Git", "CUDA", "ETL", "LLM", "Java", "Docker", "Kubernetes",
          "automated testing", "data pipelines", "data quality", "model evaluation", "HTTP API",
          "distributed training", "C++", "PCB design", "firmware", "microcontrollers")
_TERM_ALIASES = {"HTTP API": ("HTTP API", "HTTP APIs", "Python APIs"),
                 "automated testing": ("automated testing", "automated tests", "unit tests"),
                 "data pipelines": ("data pipeline", "data pipelines"),
                 "data quality": ("data quality", "data-quality"),
                 "microcontrollers": ("microcontroller", "microcontrollers")}
_STOP = {"a", "an", "and", "the", "for", "with", "of", "to", "in", "on", "or", "is", "are",
         "we", "you", "who", "be", "our", "have", "has", "experience", "job", "role", "skill", "skills", "using"}
_INSTRUCTION = re.compile(r"ignore\s+(?:all\s+)?previous|disregard|new instructions|system\s*:|忽略.{0,8}(指令|要求)|系统指令", re.I)
_NEGATIVE = re.compile(r"\bnot\s+(?:a\s+)?required\b|\bno\b.{0,60}\brequired\b|\bwithout\b.{0,40}\bexperience\b|不要求|无需|不需要|不必", re.I)
_PREFERRED = re.compile(r"\bpreferred\b|nice.to.have|\bbonus\b|优先|加分", re.I)
_EDUCATION = re.compile(r"bachelor(?:'s)?|master(?:'s)?|ph\.?d\.?|degree|本科|硕士|博士|学历", re.I)
_EXPERIENCE = re.compile(r"\d+\+?\s*(?:years?|年)|工作经验|工作经历", re.I)
_RESPONSIBILITY = re.compile(r"\b(?:build|develop|design|write|implement|maintain)\b|负责|开发|设计|维护", re.I)


class JDParseError(ValueError):
    pass


def _words(value: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9+#]+|[\u3400-\u9fff]+", value.casefold()) if word not in _STOP}


def _injection(value: str) -> bool:
    return bool(_INSTRUCTION.search(value)) or _sanitize_user_input(value) != value


def _spans(source: str) -> list[str]:
    return [span.strip() for span in re.split(r"\n|;|；|。|(?<=\.)\s+", source) if span.strip()]


def _grounded_text(text: str, evidence: str) -> bool:
    words = _words(text)
    if not words:
        return False
    return all(word in evidence.casefold() if re.search(r"[\u3400-\u9fff]", word)
               else word in _words(evidence) for word in words)


def _term_in_evidence(term: str, evidence: str) -> bool:
    """Accept exact substrings; keep English multi-word grounding via tokens."""
    if not isinstance(term, str) or not term.strip():
        return False
    cleaned = term.strip()
    if cleaned.casefold() in evidence.casefold():
        return True
    if re.search(r"[\u3400-\u9fff]", cleaned):
        # Reject invented CJK compounds that are not contiguous in the quote.
        return False
    return _grounded_text(cleaned, evidence)


def _seed_terms_from_evidence(evidence: str) -> list[str]:
    seeded = [term for term in _TERMS if any(
        re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", evidence, re.I)
        for alias in _TERM_ALIASES.get(term, (term,)))]
    for part in re.split(r"[，,、/；;：:\|\s]+", evidence):
        part = part.strip(" 。；;（）()【】[]“”\"'")
        if not part or len(part) < 2 or len(part) > 24:
            continue
        if re.search(r"[\u3400-\u9fffA-Za-z]", part) and part not in seeded:
            seeded.append(part)
    return seeded[:12]


def _coerce_grounded_terms(item: dict[str, Any]) -> dict[str, Any] | None:
    """Drop model terms that are not present in evidence_text (common on CJK JDs)."""
    evidence = item.get("evidence_text")
    terms = item.get("normalized_terms")
    if not isinstance(evidence, str) or not isinstance(terms, list):
        return None
    original = [term.strip() for term in terms if isinstance(term, str) and term.strip()]
    grounded = [term for term in original if _term_in_evidence(term, evidence)]
    if not grounded:
        if original:
            # Keep fabricated-skill rejection: do not replace invented terms with seeded ones.
            return None
        grounded = _seed_terms_from_evidence(evidence)
    if not grounded:
        return None
    coerced = dict(item)
    coerced["normalized_terms"] = grounded
    return coerced


def _source_supported(item: dict[str, Any], source: str) -> bool:
    evidence = item.get("evidence_text")
    if not isinstance(evidence, str) or evidence not in source:
        return False
    contexts = [span for span in _spans(source) if evidence in span or span in evidence]
    if not contexts or not any(not _injection(span) and not _NEGATIVE.search(span) for span in contexts):
        return False
    if _injection(evidence) or _NEGATIVE.search(evidence):
        return False
    if not isinstance(item.get("text"), str) or not _grounded_text(item["text"], evidence):
        return False
    terms = item.get("normalized_terms")
    return isinstance(terms, list) and bool(terms) and all(
        isinstance(term, str) and _term_in_evidence(term, evidence) for term in terms
    )


def _preferred_context(evidence: str, source: str) -> bool:
    preferred = False
    contexts = []
    for span in _spans(source):
        if re.fullmatch(
            r"(?:preferred(?: qualifications| requirements| skills)?|nice.to.have|优先条件|加分项(?:或注意事项)?)\s*[:：]?",
            span,
            re.I,
        ):
            preferred = True
        elif re.fullmatch(
            r"(?:requirements|required(?: qualifications| skills)?|responsibilities|基本要求|任职要求|岗位要求|岗位职责|岗位描述)\s*[:：]?",
            span,
            re.I,
        ):
            preferred = False
        if evidence in span or span in evidence:
            contexts.append(preferred or bool(_PREFERRED.search(span)))
    return bool(contexts) and all(contexts)


def _repair_quote(item: dict[str, Any], source: str) -> dict[str, Any] | None:
    """Replace a fabricated quote only when the JD itself contains every claimed term."""
    text = item.get("text")
    terms = item.get("normalized_terms")
    confidence = item.get("confidence")
    if not isinstance(text, str) or not isinstance(terms, list) or not terms or not all(isinstance(term, str) for term in terms):
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence):
        return None
    wanted = _words(text).union(*(_words(term) for term in terms))
    if not wanted:
        return None
    for span in _spans(source):
        if _injection(span) or _NEGATIVE.search(span):
            continue
        if _grounded_text(text, span) and all(_grounded_text(term, span) for term in terms) and len(span) <= 500:
            repaired = dict(item)
            repaired["evidence_text"] = span
            repaired["confidence"] = min(confidence, 0.7)
            return repaired
    return None


def _canonical_terms(raw_terms: list[str], evidence: str) -> list[str]:
    recognised = [term for term in _TERMS if any(
        re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", evidence, re.I)
        for alias in _TERM_ALIASES.get(term, (term,)))]
    available = set().union(*(_words(raw) for raw in raw_terms))
    normalised: list[str] = []
    consumed: set[str] = set()
    for term in recognised:
        for alias in _TERM_ALIASES.get(term, (term,)):
            if _words(alias).issubset(available):
                normalised.append(term)
                consumed.update(_words(alias))
                break
    normalised.extend(raw for raw in raw_terms if not _words(raw).issubset(consumed))
    return list(dict.fromkeys(normalised))


class JDParser:
    def __init__(self, model: ModelClient | None = None) -> None:
        self.model = model

    def parse(self, source: str) -> tuple[dict[str, Any], str, str | None]:
        if not isinstance(source, str) or len(source.strip()) < 20 or len(source) > 20000:
            raise JDParseError("jd_text must contain 20 to 20000 characters")
        failure: str | None = None
        if self.model is not None:
            for _ in range(2):
                try:
                    raw = self.model.complete_json(JD_PARSE_SYSTEM_PROMPT, _sanitize_user_input(source))
                    parsed, repaired = self._adapt(raw, source)
                    return parsed, "MODEL_SPAN_REPAIRED" if repaired else "MODEL", None
                except (ModelFailure, JDParseError, ValueError, TypeError, KeyError) as exc:
                    detail = str(exc).strip()
                    failure = f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
                    if len(failure) > 160:
                        failure = failure[:157] + "..."
                    if isinstance(exc, ModelFailure) and not exc.retryable:
                        break
        try:
            return self._fallback(source), "RULE_FALLBACK", failure
        except JDParseError as exc:
            raise JDParseError("JD could not be parsed safely") from exc

    def _adapt(self, raw: dict[str, Any], source: str) -> tuple[dict[str, Any], bool]:
        if not isinstance(raw, dict) or not isinstance(raw.get("requirements"), list) or not raw["requirements"]:
            raise JDParseError("Model output has no requirements")
        if len(raw["requirements"]) > 40:
            raise JDParseError("Too many requirements; output must not be silently truncated")
        title = raw.get("title") or "UNKNOWN"
        company = raw.get("company") or "UNKNOWN"
        if not isinstance(title, str) or not isinstance(company, str):
            raise JDParseError("Invalid title or company")
        if title != "UNKNOWN" and title.casefold() not in source.casefold():
            raise JDParseError("Title was not present in JD")
        if company != "UNKNOWN" and company.casefold() not in source.casefold():
            raise JDParseError("Company was not present in JD")
        requirements = []
        repaired_any = False
        for number, item in enumerate(raw["requirements"], 1):
            if not isinstance(item, dict):
                raise JDParseError("Requirement is not an object")
            coerced = _coerce_grounded_terms(item)
            if coerced is None:
                raise JDParseError("Requirement is not grounded in JD")
            if coerced.get("normalized_terms") != item.get("normalized_terms"):
                repaired_any = True
            item = coerced
            if not _source_supported(item, source):
                repaired = _repair_quote(item, source)
                if repaired is not None:
                    repaired = _coerce_grounded_terms(repaired) or repaired
                if repaired is None or not _source_supported(repaired, source):
                    raise JDParseError("Requirement is not grounded in JD")
                item = repaired
                repaired_any = True
            if item.get("type") == "HARD" and _preferred_context(item["evidence_text"], source):
                raise JDParseError("Requirement is not grounded in JD")
            terms = _canonical_terms(_validate_string_list_field(item, "normalized_terms"), item["evidence_text"])
            requirements.append({"requirement_id": f"req_{number:03d}", "type": item.get("type"),
                                 "category": item.get("category"), "text": item["text"],
                                 "normalized_terms": terms,
                                 "evidence_text": item["evidence_text"], "confidence": item.get("confidence")})
        result = {"jd_id": "jd_" + hashlib.sha256(source.encode()).hexdigest()[:12],
                  "title": title, "company": company, "source_text": source, "requirements": requirements}
        validate_contract("parsed-jd", result)
        return result, repaired_any

    def _fallback(self, source: str) -> dict[str, Any]:
        requirements = []
        section_preferred = False
        section_category = None
        for line in _spans(source):
            if _injection(line) or _NEGATIVE.search(line):
                continue
            if re.fullmatch(
                r"(?:preferred(?: qualifications| requirements| skills)?|nice.to.have|优先条件|加分项(?:或注意事项)?)\s*[:：]?",
                line,
                re.I,
            ):
                section_preferred, section_category = True, None
                continue
            if re.fullmatch(
                r"(?:requirements|required(?: qualifications| skills)?|基本要求|任职要求|岗位要求)\s*[:：]?",
                line,
                re.I,
            ):
                section_preferred, section_category = False, None
                continue
            if re.fullmatch(r"(?:responsibilities|职责|岗位职责|岗位描述)\s*[:：]?", line, re.I):
                section_preferred, section_category = False, "RESPONSIBILITY"
                continue
            line_preferred = section_preferred or bool(_PREFERRED.search(line))
            for fragment in re.split(r",|\band\b", line, flags=re.I):
                fragment = fragment.strip()
                terms = [term for term in _TERMS if any(
                    re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", fragment, re.I)
                    for alias in _TERM_ALIASES.get(term, (term,)))]
                category = "EDUCATION" if _EDUCATION.search(fragment) else "EXPERIENCE" if _EXPERIENCE.search(fragment) else section_category or ("RESPONSIBILITY" if _RESPONSIBILITY.search(fragment) else "SKILL")
                if not terms and category in {"EDUCATION", "EXPERIENCE"}:
                    terms = [fragment]
                if not terms:
                    continue
                requirements.append({"requirement_id": f"req_{len(requirements)+1:03d}",
                                     "type": "PREFERRED" if line_preferred else "HARD", "category": category,
                                     "text": fragment, "normalized_terms": terms, "evidence_text": fragment,
                                     "confidence": 0.45})
        if not requirements or len(requirements) > 40:
            raise JDParseError("No reliable requirements found")
        first_line = source.splitlines()[0].strip()
        title_match = None if re.search(r"company\s+(seeks|needs|requires)", first_line, re.I) else re.match(
            r"^(.{3,60}?(?:Engineer|Developer|Intern|Analyst|Scientist))(?=\.|\s+(?:requires|needs|seeks)\b|$)",
            first_line, re.I)
        title = title_match.group(1) if title_match else "UNKNOWN"
        result = {"jd_id": "jd_" + hashlib.sha256(source.encode()).hexdigest()[:12],
                  "title": title, "company": "UNKNOWN", "source_text": source,
                  "requirements": requirements}
        validate_contract("parsed-jd", result)
        return result
