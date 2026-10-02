from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.services.third_party.resume_matcher_bullet_selector import select_bullets


_WORDS = re.compile(r"[a-z0-9+#.]+")


@dataclass(frozen=True)
class SelectionResult:
    """Selected contract-valid claims plus an auditable record of non-selection."""

    claims: list[dict[str, Any]]
    removed_claims: list[dict[str, str]]


class ResumeSelector:
    """Deterministic constrained claim selection for the B proposal baseline."""

    def select(
        self,
        evidence_match: dict[str, Any],
        experiences: list[dict[str, Any]],
        application_id: str,
        *,
        max_claims: int = 3,
        max_characters: int = 420,
    ) -> SelectionResult:
        if max_claims < 1 or max_characters < 1:
            raise ValueError("Claim count and character budgets must be positive")

        claims_by_id = {
            claim["claim_id"]: (claim, experience)
            for experience in experiences
            for claim in experience.get("claims", [])
        }
        source_by_claim = {
            claim["claim_id"]: {source["evidence_id"]: source for source in experience.get("evidence_sources", [])}
            for experience in experiences
            for claim in experience.get("claims", [])
        }
        matches_by_claim: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in claims_by_id}
        all_matches_by_claim: dict[str, list[dict[str, Any]]] = {claim_id: [] for claim_id in claims_by_id}
        for match in evidence_match["matches"]:
            for claim_id in match["claim_ids"]:
                if claim_id in all_matches_by_claim and claims_by_id[claim_id][1]["experience_id"] == match["experience_id"]:
                    all_matches_by_claim[claim_id].append(match)
                    if match.get("ready_for_selection", False):
                        matches_by_claim[claim_id].append(match)

        candidates: list[dict[str, Any]] = []
        removed: list[dict[str, str]] = []
        for claim_id, (claim, experience) in sorted(claims_by_id.items()):
            ready_matches = matches_by_claim[claim_id]
            all_matches = all_matches_by_claim[claim_id]
            if not ready_matches:
                removed.append({"claim_id": claim_id, "reason": self._initial_removal_reason(all_matches)})
                continue
            support = self._support_score(ready_matches)
            support = min(support, float(claim.get("confidence", 0.0)))
            if support < 0.65:
                removed.append({"claim_id": claim_id, "reason": "INSUFFICIENT_EVIDENCE: support score is below the selector threshold."})
                continue
            linked_ids = set(claim.get("evidence_ids", []))
            matched_ids = {evidence_id for match in ready_matches for evidence_id in match.get("evidence_ids", [])}
            evidence_ids = sorted(linked_ids.intersection(matched_ids))
            sources = source_by_claim[claim_id]
            if not evidence_ids or linked_ids != set(evidence_ids) or any(
                evidence_id not in sources or sources[evidence_id].get("verification_status") != "VERIFIED"
                for evidence_id in evidence_ids
            ):
                removed.append({"claim_id": claim_id, "reason": "INSUFFICIENT_EVIDENCE: claim evidence is missing, unrelated, or unverified."})
                continue
            requirement_ids = sorted({match["requirement_id"] for match in ready_matches})
            impact = 0.1 if any(
                set(metric.get("evidence_ids", [])).intersection(evidence_ids)
                for metric in experience.get("metrics", [])
            ) else 0.0
            selection_score = round(0.6 * max(match["relevance_score"] for match in ready_matches) + 0.3 * support + impact, 4)
            candidates.append(
                {
                    "claim_id": claim_id,
                    "text": claim["text"],
                    "evidence_ids": evidence_ids,
                    "requirement_ids": requirement_ids,
                    "evidence_support_score": support,
                    "selection_score": selection_score,
                    "selection_reason": (
                        f"Selected for requirements {', '.join(requirement_ids)}: high relevance and "
                        f"verified evidence ({', '.join(evidence_ids)})."
                        + (" A documented metric contributed to ranking." if impact else "")
                    ),
                }
            )

        candidates.sort(key=lambda item: (-item["selection_score"], -item["evidence_support_score"], item["claim_id"]))
        selected: list[dict[str, Any]] = []
        used_characters = 0
        remaining = candidates
        while remaining and len(selected) < max_claims:
            batch_ids = self._select_with_upstream_bullet_selector(remaining, max_claims - len(selected))
            batch = [candidate for candidate in remaining if candidate["claim_id"] in batch_ids]
            remaining = [candidate for candidate in remaining if candidate["claim_id"] not in batch_ids]
            for candidate in batch:
                if len(selected) >= max_claims:
                    remaining.append(candidate)
                    continue
                duplicate_of = next(
                    (chosen["claim_id"] for chosen in selected if self._similar(candidate["text"], chosen["text"])),
                    None,
                )
                if duplicate_of:
                    removed.append({"claim_id": candidate["claim_id"], "reason": f"REDUNDANT: duplicates {duplicate_of}."})
                    continue
                if used_characters + len(candidate["text"]) > max_characters:
                    removed.append({"claim_id": candidate["claim_id"], "reason": "LENGTH_LIMIT: the character budget would be exceeded."})
                    continue
                used_characters += len(candidate["text"])
                selected.append(candidate)

        for candidate in remaining:
            duplicate_of = next(
                (chosen["claim_id"] for chosen in selected if self._similar(candidate["text"], chosen["text"])),
                None,
            )
            reason = f"REDUNDANT: duplicates {duplicate_of}." if duplicate_of else "CLAIM_LIMIT: the maximum claim count was reached."
            removed.append({"claim_id": candidate["claim_id"], "reason": reason})

        removed.sort(key=lambda item: (item["claim_id"], item["reason"]))
        claims = [
            {
                "claim_id": candidate["claim_id"],
                "application_id": application_id,
                "text": candidate["text"],
                "evidence_ids": candidate["evidence_ids"],
                "requirement_ids": candidate["requirement_ids"],
                "evidence_support_score": candidate["evidence_support_score"],
                "selection_reason": candidate["selection_reason"],
                "removed_alternatives": removed,
                "status": "SELECTED",
            }
            for candidate in selected
        ]
        return SelectionResult(claims=claims, removed_claims=removed)

    @staticmethod
    def _select_with_upstream_bullet_selector(candidates: list[dict[str, Any]], max_claims: int) -> set[str]:
        """Adapt Claim candidates to Resume Matcher's retained Apache-2.0 selector."""
        separator = "\x1f"
        bullets = [f"{candidate['claim_id']}{separator}{candidate['text']}" for candidate in candidates]
        scores = {
            ("workExperience", 0, index): candidate["selection_score"]
            for index, candidate in enumerate(candidates)
        }
        selected = select_bullets(
            {"workExperience": [{"description": bullets}]},
            scores,
            max_per_entry=max_claims,
        )
        return {
            bullet.split(separator, 1)[0]
            for bullet in selected.data["workExperience"][0]["description"]
        }

    @staticmethod
    def _support_score(matches: list[dict[str, Any]]) -> float:
        scores = [0.7 * match["relevance_score"] + 0.3 * match["confidence"] for match in matches]
        return round(sum(scores) / len(scores), 4)

    @staticmethod
    def _initial_removal_reason(matches: list[dict[str, Any]]) -> str:
        if any(match["conflicts"] for match in matches):
            return "CONFLICT: evidence or verification state requires review."
        if matches:
            return "INSUFFICIENT_EVIDENCE: no match was ready for selection."
        return "LOW_RELEVANCE: no JD requirement had sufficient term overlap."

    @staticmethod
    def _similar(left: str, right: str) -> bool:
        left_words = set(_WORDS.findall(left.lower()))
        right_words = set(_WORDS.findall(right.lower()))
        if not left_words or not right_words:
            return False
        return len(left_words.intersection(right_words)) / len(left_words.union(right_words)) >= 0.65
