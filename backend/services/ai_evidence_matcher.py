"""Optional AI semantic scoring over the deterministic evidence matcher.

The model may only rank existing claim IDs. Verification gaps, conflicts, and
evidence IDs stay deterministic; failures fall back to the rule baseline.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any

from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.jd_match_scope import select_requirements_for_matching
from backend.services.model_client import ModelClient, ModelFailure
from backend.services.prompts import EVIDENCE_MATCH_PROMPT_VERSION, EVIDENCE_MATCH_SYSTEM_PROMPT


def _ai_match_enabled() -> bool:
    flag = (os.getenv("APPLYGUARD_AI_MATCH") or "on").strip().lower()
    return flag not in {"0", "false", "off", "disabled", "no"}


def _compact_experiences(experiences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for experience in experiences:
        rows.append({
            "experience_id": experience["experience_id"],
            "title": experience.get("title") or experience.get("role") or "",
            "skills": list(experience.get("skills") or [])[:16],
            "claims": [
                {"claim_id": claim["claim_id"], "text": (claim.get("text") or "")[:240]}
                for claim in experience.get("claims") or []
                if isinstance(claim.get("claim_id"), str)
            ][:12],
        })
    return rows


def _compact_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "requirement_id": item["requirement_id"],
        "type": item.get("type"),
        "category": item.get("category"),
        "text": (item.get("text") or item.get("evidence_text") or "")[:220],
        "normalized_terms": list(item.get("normalized_terms") or [])[:8],
    } for item in requirements]


def _boost_score_10(score_10: float) -> float:
    """Lift conservative mid-range model scores; keep near-zero scores unchanged."""
    if score_10 <= 2:
        return round(max(0.0, score_10), 1)
    # e.g. 5 -> 7.0, 6.5 -> 8.7, 8 -> 10, 9.2 -> 10
    return round(min(10.0, score_10 * 1.2 + 1.0), 1)


def _normalize_model_score(raw: Any) -> tuple[float, float] | None:
    """Accept model 0-10 scores (preferred) or legacy 0-1; return (unit_0_1, display_0_10)."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        return None
    value = float(raw)
    if value > 1.0:
        display = _boost_score_10(max(0.0, min(10.0, value)))
        return display / 10.0, display
    unit = max(0.0, min(1.0, value))
    display = _boost_score_10(unit * 10.0)
    return display / 10.0, display


def _valid_score_item(
    item: Any,
    requirement_ids: set[str],
    experience_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    requirement_id = item.get("requirement_id")
    experience_id = item.get("experience_id")
    claim_ids = item.get("claim_ids")
    score = item.get("score", item.get("semantic_score"))
    rationale = item.get("rationale")
    if requirement_id not in requirement_ids or experience_id not in experience_by_id:
        return None
    if not isinstance(claim_ids, list) or not claim_ids or len(claim_ids) > 3:
        return None
    normalized = _normalize_model_score(score)
    if normalized is None:
        return None
    unit, display = normalized
    if not isinstance(rationale, str) or not rationale.strip():
        rationale = "Model linked existing claims to this requirement."
    experience = experience_by_id[experience_id]
    known = {claim["claim_id"]: claim for claim in experience.get("claims") or []}
    linked = []
    for claim_id in claim_ids:
        if not isinstance(claim_id, str) or claim_id not in known:
            return None
        if claim_id not in {row["claim_id"] for row in linked}:
            linked.append(known[claim_id])
    if not linked:
        return None
    return {
        "requirement_id": requirement_id,
        "experience_id": experience_id,
        "claims": linked,
        "semantic_score": unit,
        "score_10": display,
        "rationale": rationale.strip()[:240],
    }


def merge_ai_match(
    parsed_jd: dict[str, Any],
    experiences: list[dict[str, Any]],
    baseline: dict[str, Any],
    raw: dict[str, Any],
    *,
    matcher: EvidenceMatcher | None = None,
) -> dict[str, Any]:
    """Replace baseline rows with validated AI-linked scores; keep rule rows AI skipped."""
    matcher = matcher or EvidenceMatcher()
    scoped = select_requirements_for_matching(parsed_jd)
    requirement_by_id = {item["requirement_id"]: item for item in scoped}
    experience_by_id = {item["experience_id"]: item for item in experiences}
    scores = raw.get("scores") if isinstance(raw, dict) else None
    if not isinstance(scores, list) or not scores:
        raise ValueError("Model match output has no scores")

    ai_rows: list[dict[str, Any]] = []
    per_requirement: dict[str, int] = {}
    for item in scores:
        parsed = _valid_score_item(item, set(requirement_by_id), experience_by_id)
        if parsed is None:
            continue
        count = per_requirement.get(parsed["requirement_id"], 0)
        if count >= 2:
            continue
        requirement = requirement_by_id[parsed["requirement_id"]]
        terms = matcher._requirement_terms(requirement)
        scored = matcher.score_linked_claims(
            requirement,
            terms,
            experience_by_id[parsed["experience_id"]],
            parsed["claims"],
            semantic_score=parsed["semantic_score"],
            model_rationale=parsed["rationale"],
            require_keyword_hit=False,
        )
        if scored is None:
            continue
        breakdown = scored.setdefault("score_breakdown", {})
        breakdown["ai_score_10"] = parsed["score_10"]
        breakdown["ai_semantic_score"] = parsed["semantic_score"]
        ai_rows.append(scored)
        per_requirement[parsed["requirement_id"]] = count + 1

    if not ai_rows:
        raise ValueError("No grounded AI match rows survived validation")

    ai_keys = {(row["requirement_id"], row["experience_id"]) for row in ai_rows}
    kept_baseline = [
        row for row in baseline.get("matches", [])
        if (row.get("requirement_id"), row.get("experience_id")) not in ai_keys
    ]
    matches = sorted(
        [*ai_rows, *kept_baseline],
        key=lambda row: (-float(row.get("relevance_score") or 0), row.get("requirement_id", ""), row.get("experience_id", "")),
    )

    uncovered: list[dict[str, Any]] = []
    for requirement in scoped:
        rid = requirement["requirement_id"]
        rows = [row for row in matches if row["requirement_id"] == rid]
        if any(row.get("ready_for_selection") for row in rows):
            continue
        uncovered.append({
            "requirement_id": rid,
            "missing_evidence": matcher._uncovered_notes(rows) if rows else [
                "No claim with linked evidence states this requirement."
            ],
            "reason": (
                "No experience has sufficiently verified, conflict-free evidence for selection."
                if rows else
                "The matcher found no linked claims for this requirement."
            ),
        })

    result = {
        "match_id": baseline["match_id"],
        "jd_id": baseline["jd_id"],
        "candidate_id": baseline["candidate_id"],
        "matches": matches,
        "uncovered_requirements": uncovered,
        "ai_match": {
            "mode": "MODEL",
            "prompt_version": EVIDENCE_MATCH_PROMPT_VERSION,
            "scored_rows": len(ai_rows),
        },
    }
    if "sag_auxiliary" in baseline:
        result["sag_auxiliary"] = baseline["sag_auxiliary"]
    return result


def augment_match_with_ai(
    parsed_jd: dict[str, Any],
    experiences: list[dict[str, Any]],
    baseline: dict[str, Any],
    model: ModelClient | None,
    *,
    matcher: EvidenceMatcher | None = None,
) -> dict[str, Any]:
    """Run one AI scoring pass when enabled; otherwise return the deterministic baseline."""
    if model is None or not _ai_match_enabled():
        return baseline
    scoped = select_requirements_for_matching(parsed_jd)
    if not scoped:
        return baseline
    payload = {
        "requirements": _compact_requirements(scoped),
        "experiences": _compact_experiences(experiences),
    }
    try:
        raw = model.complete_json(EVIDENCE_MATCH_SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False))
        return merge_ai_match(parsed_jd, experiences, baseline, raw, matcher=matcher)
    except (ModelFailure, ValueError, TypeError, KeyError) as exc:
        detail = str(exc).strip() or type(exc).__name__
        if len(detail) > 160:
            detail = detail[:157] + "..."
        fallback = dict(baseline)
        fallback["ai_match"] = {
            "mode": "RULE_FALLBACK",
            "prompt_version": EVIDENCE_MATCH_PROMPT_VERSION,
            "failure": f"{type(exc).__name__}: {detail}",
        }
        return fallback
