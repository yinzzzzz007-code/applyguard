"""Conservative claim-level checks against candidate-owned Vault records."""

from __future__ import annotations

import re
import math
from typing import Any

from backend.services.career_vault import _validate_metric_calculation
from backend.services.schema_validation import validate_contract


_FACTS = re.compile(r"\b(?:owner|owned|led|lead|solely|entire|all|personally|single-handedly|individually|production|deployed|delivered|completed|shipped|managed|architected|multi-gpu|distributed|cuda|kubernetes|docker|aws)\b|\b\d{4}-\d{2}\b|\b\d+(?:\.\d+)?%?(?![\w])", re.I)
_SKILLS = ("Python", "PyTorch", "LoRA", "React", "TypeScript", "Node.js", "PostgreSQL", "SQL", "Git",
           "CUDA", "ETL", "LLM", "Java", "Docker", "Kubernetes", "distributed training")


def _mentions(term: str, text: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text, re.I))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+|[\u3400-\u9fff]+", text.casefold()))


_REWORD = set("a an the and or of in on for to with its their my i we was were is are at by as this that created built developed implemented helped contributed worked main core successfully".split())
_LEAD = re.compile(r"\b(?:owner|owned|led|lead|managed|architected|solely|single-handedly)\b|主导|负责人|独立负责", re.I)
_PLANNED = re.compile(r"\b(?:planned|planning|proposed|not yet|prototype only)\b|计划|拟开展|尚未|未交付", re.I)
_DELIVERED = re.compile(r"\b(?:built|deployed|delivered|completed|shipped|released)\b|已完成|已交付|上线", re.I)
_TEAM = re.compile(r"\bteam\b|团队", re.I)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?%?(?![\w.])")


def _metric_errors(metric: dict[str, Any], claim_text: str) -> list[str]:
    errors = []
    try:
        _validate_metric_calculation(metric)  # B adapter calls the retained ASu arithmetic function.
    except ValueError:
        return ["Structured metric arithmetic is incomplete or inconsistent."]
    calculation = metric.get("calculation", {})
    expected = calculation.get("displayed_percent", calculation.get("displayed_change"))
    if expected is not None:
        for text in (metric.get("value", ""), claim_text):
            for match in re.finditer(r"(\d+(?:\.\d+)?)\s*(%|percentage points?|percent|个百分点)", text, re.I):
                if not math.isclose(float(match[1]), expected, abs_tol=0.5):
                    errors.append("Claim/metric percentage differs from the structured calculation.")
                pp = "point" in match[2].lower() or match[2] == "个百分点"
                expected_pp = calculation.get("change_type") == "percentage_points"
                if pp != expected_pp:
                    errors.append("Percentage points and relative percentages use different denominators.")
    ratio = re.search(r"(\d+)\s+(?:of|out of)\s+(\d+)", claim_text, re.I)
    if ratio and "numerator" in calculation and (float(ratio[1]), float(ratio[2])) != (calculation["numerator"], calculation["denominator"]):
        errors.append("Claim numerator/denominator differs from the source metric.")
    return errors


class ClaimValidator:
    def verify(self, claim: dict[str, Any], experiences: list[dict[str, Any]], candidate_id: str,
               evidence_match: dict[str, Any] | None = None) -> dict[str, Any]:
        claim_id = claim.get("claim_id", "")
        text = claim.get("text", "")
        reasons: list[str] = []
        fragments: list[str] = []
        review = False
        scores: list[float] = []
        found = [(item, experience) for experience in experiences for item in experience.get("claims", [])
                 if item.get("claim_id") == claim_id]
        if len(found) != 1:
            fragments.append("claim_id")
            reasons.append("Claim ID is not present exactly once in the candidate Vault.")
        else:
            original, experience = found[0]
            if experience.get("candidate_id") != candidate_id:
                fragments.append("candidate ownership")
                reasons.append("Claim belongs to another candidate.")
            sources = {item["evidence_id"]: item for item in experience.get("evidence_sources", [])}
            linked_ids = claim.get("evidence_ids", [])
            if not linked_ids:
                fragments.append("evidence_ids")
                reasons.append("Claim has no linked evidence.")
            elif set(linked_ids) != set(original.get("evidence_ids", [])):
                fragments.append("evidence_ids")
                reasons.append("Claim must retain all Vault evidence links required for its original statement.")
            for evidence_id in linked_ids:
                if evidence_id not in sources or evidence_id not in original.get("evidence_ids", []):
                    fragments.append(evidence_id)
                    reasons.append("Evidence ID is missing or does not belong to this claim and experience.")
                elif sources[evidence_id].get("verification_status", "UNVERIFIED") == "CONFLICTING":
                    fragments.append(evidence_id)
                    reasons.append("Evidence source is conflicting.")
                elif sources[evidence_id].get("verification_status", "UNVERIFIED") != "VERIFIED":
                    review = True
                    reasons.append("Linked evidence requires verification or review.")
                if evidence_id in sources:
                    confidence = sources[evidence_id].get("confidence", 0)
                    if not isinstance(confidence, (int, float)) or not math.isfinite(confidence):
                        confidence = 0
                    scores.append(confidence)
                    if confidence < 0.65:
                        review = True
                        reasons.append("Evidence confidence is missing or below the review threshold (0.65).")
            if original.get("verification_state") != "VERIFIED" or experience.get("verification_state") != "VERIFIED":
                review = True
                reasons.append("Vault claim or experience is not fully verified.")
            evidence_text = " ".join(sources[key].get("description", "") for key in linked_ids if key in sources)
            source_text = original.get("text", "")
            linked_metrics = [metric for metric in experience.get("metrics", [])
                              if set(metric.get("evidence_ids", [])).issubset(set(linked_ids))]
            for metric in linked_metrics:
                metric_errors = _metric_errors(metric, text)
                if metric_errors:
                    fragments.append(next((m.group() for m in _NUMBER.finditer(text)), metric["metric_id"]))
                    reasons.extend(metric_errors)
            if _PLANNED.search(evidence_text) and _DELIVERED.search(text):
                fragments.append(_DELIVERED.search(text).group())
                reasons.append("Evidence describes planned work, but the claim states completed delivery.")
            if _LEAD.search(text) and re.search(r"\b(?:participated|contributed|member|assisted)\b|参与|协助|成员", evidence_text, re.I) and not _LEAD.search(evidence_text):
                fragments.append(_LEAD.search(text).group())
                reasons.append("Participation evidence does not establish ownership or leadership.")
            if _TEAM.search(evidence_text) and _NUMBER.search(text) and not _TEAM.search(text):
                fragments.append(text)
                reasons.append("A team metric is being attributed to the individual without supporting attribution.")
            if re.search(r"\b(?:not|never|no)\b|并未|没有", evidence_text, re.I):
                review = True
                reasons.append("Evidence contains a negative statement; its relation to the claim requires review.")
            for date in re.findall(r"\b\d{4}-\d{2}\b", text):
                if date not in (experience.get("start_date"), experience.get("end_date")):
                    fragments.append(date)
                    reasons.append("Claim date does not match the linked experience dates.")
            if text != original.get("text"):
                for skill in _SKILLS:
                    if _mentions(skill, text) and not _mentions(skill, source_text):
                        fragments.append(skill)
                        reasons.append("A claimed skill is not stated by the linked Vault claim or responsibilities.")
                source_facts = {match.group().casefold() for match in _FACTS.finditer(source_text)}
                for match in _FACTS.finditer(text):
                    fact = match.group()
                    if fact.casefold() in source_facts:
                        continue
                    if fact in (experience.get("start_date"), experience.get("end_date")):
                        continue
                    documented = False
                    for metric in linked_metrics:
                        if set(metric.get("evidence_ids", [])).issubset(set(linked_ids)):
                            try:
                                _validate_metric_calculation(metric)
                                documented = fact in {m.group() for m in _FACTS.finditer(metric.get("value", ""))}
                            except ValueError:
                                documented = False
                        if documented:
                            break
                    if not documented:
                        fragments.append(fact)
                        reasons.append("Claim adds a role, delivery state, technology, date, or metric absent from evidence.")
                support_text = source_text + " " + evidence_text + " " + " ".join(metric.get("value", "") for metric in linked_metrics)
                additions = _tokens(text) - _tokens(support_text) - _REWORD
                if additions:
                    fragments.extend(sorted(additions))
                    reasons.append("New factual wording has no support in the linked claim or source material.")
                if not fragments:
                    review = True
                    reasons.append("Reworded claim needs human review of its full meaning.")
            if evidence_match is not None:
                matching = [match for match in evidence_match.get("matches", []) if claim_id in match.get("claim_ids", [])
                            and match.get("experience_id") == experience["experience_id"]]
                if any(match.get("conflicts") for match in matching):
                    fragments.append(text)
                    reasons.append("B reports conflicting evidence for this claim.")
                if not matching or any(not match.get("ready_for_selection", False) or match.get("missing_evidence") for match in matching):
                    review = True
                    reasons.append("B matching did not establish a ready, conflict-free selection.")
        fragments = list(dict.fromkeys(fragments))
        state = "BLOCKED" if fragments else "NEEDS_REVIEW" if review else "VERIFIED"
        score = 0.0 if fragments or not found else min([*scores, float(claim.get("evidence_support_score", 0)), float(found[0][0].get("confidence", 0))])
        result = {"claim_id": claim_id, "state": state, "grounded": state == "VERIFIED",
                  "support_score": round(score, 4), "unsupported_fragments": fragments,
                  "explanation": " ".join(dict.fromkeys(reasons)) if reasons else "Candidate-owned verified evidence supports the unchanged Vault claim."}
        validate_contract("claim-verification", result)
        return result

    def verify_all(self, claims: list[dict[str, Any]], experiences: list[dict[str, Any]], candidate_id: str,
                   evidence_match: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return [self.verify(claim, experiences, candidate_id, evidence_match) for claim in claims]
