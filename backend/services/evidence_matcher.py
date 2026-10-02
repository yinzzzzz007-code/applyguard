from __future__ import annotations

import re
from typing import Any


_NON_ALNUM = re.compile(r"[^a-z0-9+#.]+")
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
}
_MENTION_VARIANTS = {
    "data pipelines": {"etl pipeline", "etl pipelines"},
    "llm fine tuning": {"fine tuned a language model"},
}


def _plain_normalise(value: str) -> str:
    return _NON_ALNUM.sub(" ", value.casefold()).strip()


def _normalise(value: str) -> str:
    cleaned = _plain_normalise(value)
    return _ALIASES.get(cleaned, cleaned)


def _mentions(term: str, text: str) -> bool:
    """Match complete terms or explicit aliases; never match inside another word."""
    normalised_text = _plain_normalise(text)
    if term == "model evaluation":
        return bool(
            re.search(r"(?<![a-z0-9+#])model(?![a-z0-9+#])", normalised_text)
            and re.search(r"(?<![a-z0-9+#])evaluation(?![a-z0-9+#])", normalised_text)
        )
    variants = {term, *_MENTION_VARIANTS.get(term, set())}
    variants.update(alias for alias, canonical in _ALIASES.items() if canonical == term)
    return any(
        re.search(rf"(?<![a-z0-9+#]){re.escape(variant)}(?![a-z0-9+#])", normalised_text)
        for variant in variants
    )


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


class EvidenceMatcher:
    """A deterministic, explainable proposal baseline; it does not parse JD text."""

    def match(self, parsed_jd: dict[str, Any], experiences: list[dict[str, Any]]) -> dict[str, Any]:
        candidate_ids = {experience["candidate_id"] for experience in experiences}
        if len(candidate_ids) != 1:
            raise ValueError("Evidence Matcher requires experiences from exactly one candidate")
        candidate_id = next(iter(candidate_ids))
        matches: list[dict[str, Any]] = []
        uncovered: list[dict[str, Any]] = []

        for requirement in parsed_jd["requirements"]:
            requirement_terms = {_normalise(term) for term in requirement.get("normalized_terms", []) if term.strip()}
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

    def _score_requirement(
        self,
        requirement: dict[str, Any],
        requirement_terms: set[str],
        experience: dict[str, Any],
    ) -> dict[str, Any] | None:
        skill_terms = {_normalise(skill) for skill in experience.get("skills", [])}
        responsibility_text = " ".join(
            [experience.get("summary", ""), *experience.get("responsibilities", []), experience.get("title", ""), experience.get("role", "")]
        )
        claims = [
            claim for claim in experience.get("claims", [])
            if any(_mentions(term, claim["text"]) for term in requirement_terms)
        ]
        if not claims:
            return None
        supported_terms = {term for term in requirement_terms if any(_mentions(term, claim["text"]) for claim in claims)}
        keyword_hits = sorted(requirement_terms.intersection(skill_terms).intersection(supported_terms))
        responsibility_hits = sorted(term for term in supported_terms if _mentions(term, responsibility_text))
        if not keyword_hits and not responsibility_hits:
            return None
        claim_ids = [claim["claim_id"] for claim in claims]
        evidence_ids = sorted({evidence_id for claim in claims for evidence_id in claim.get("evidence_ids", [])})
        sources = experience.get("evidence_sources", [])
        source_by_id = {source["evidence_id"]: source for source in sources}
        linked_sources = [source_by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in source_by_id]
        source_confidences = [float(source.get("confidence", 0.0)) for source in linked_sources]
        claim_confidences = [float(claim.get("confidence", 0.0)) for claim in claims]
        confidence_score = min([*source_confidences, *claim_confidences], default=0.0) if linked_sources else 0.0

        conflicts = self._conflicts(experience, claims, linked_sources)
        missing_evidence = self._missing_evidence(experience, claims, linked_sources)
        unsupported_terms = sorted(requirement_terms - supported_terms)
        if unsupported_terms:
            missing_evidence.append(f"No linked claim explicitly supports: {', '.join(unsupported_terms)}.")
        verification_score = self._verification_score(experience, claims, linked_sources)
        keyword_overlap = len(keyword_hits) / len(requirement_terms)
        responsibility_overlap = len(responsibility_hits) / len(requirement_terms)
        metric_bonus = 0.1 if any(
            set(metric.get("evidence_ids", [])).intersection(evidence_ids)
            for metric in experience.get("metrics", [])
        ) else 0.0
        conflict_penalty = 0.3 if conflicts else 0.0
        missing_penalty = 0.25 if missing_evidence else 0.0
        relevance = _clamp(
            0.45 * keyword_overlap
            + 0.15 * responsibility_overlap
            + 0.15 * verification_score
            + 0.15 * confidence_score
            + metric_bonus
            - conflict_penalty
            - missing_penalty
        )
        evidence_strength = self._evidence_strength(relevance, verification_score, confidence_score, conflicts, missing_evidence)
        ready_for_selection = evidence_strength == "STRONG" and not conflicts and not missing_evidence
        rationale = self._rationale(keyword_hits, responsibility_hits, evidence_ids, conflicts, missing_evidence)

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
            "score_breakdown": {
                "keyword_overlap": _clamp(keyword_overlap),
                "responsibility_overlap": _clamp(responsibility_overlap),
                "verification_score": _clamp(verification_score),
                "confidence_score": _clamp(confidence_score),
                "metric_bonus": metric_bonus,
                "conflict_penalty": conflict_penalty,
                "missing_evidence_penalty": missing_penalty,
            },
        }

    @staticmethod
    def _conflicts(
        experience: dict[str, Any], claims: list[dict[str, Any]], sources: list[dict[str, Any]]
    ) -> list[str]:
        conflicts: list[str] = []
        if experience.get("verification_state") != "VERIFIED":
            conflicts.append(f"Experience verification state is {experience.get('verification_state', 'UNVERIFIED')}.")
        for claim in claims:
            if claim.get("verification_state") != "VERIFIED":
                conflicts.append(f"Claim {claim['claim_id']} verification state is {claim.get('verification_state', 'UNVERIFIED')}.")
        for source in sources:
            if source.get("verification_status") == "CONFLICTING":
                conflicts.append(f"Evidence {source['evidence_id']} is marked CONFLICTING.")
        return sorted(conflicts)

    @staticmethod
    def _missing_evidence(
        experience: dict[str, Any], claims: list[dict[str, Any]], sources: list[dict[str, Any]]
    ) -> list[str]:
        missing: list[str] = []
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
