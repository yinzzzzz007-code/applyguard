"""Optional SAG retrieval signal layered over the unchanged B matcher.

SAG's source-scoped REST search is used only after a user explicitly configures
it. A retrieved chunk is not proof: it must map to an existing, verified
ApplyGuard Evidence ID already linked to a baseline match.
"""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class SAGSearchClient:
    """Minimal client for SAG's /api/v1/sources/{source_id}/search API."""

    def __init__(self, base_url: str, source_id: str, token: str, *, timeout: float = 8.0):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("SAG auxiliary requires a loopback HTTP endpoint")
        if not source_id or not token:
            raise ValueError("SAG source ID and token are required")
        if not 0 < timeout <= 30:
            raise ValueError("SAG timeout must be within (0, 30] seconds")
        self.base_url = base_url.rstrip("/")
        self.source_id = source_id
        self.token = token
        self.timeout = timeout

    def search(self, query: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/api/v1/sources/{quote(self.source_id, safe='')}/search"
        payload = json.dumps({"query": query[:4000], "strategy": "multi", "top_k": 8}).encode("utf-8")
        request = Request(url, payload, {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError("SAG search response is too large")
        result = json.loads(body)
        if not isinstance(result, dict) or not isinstance(result.get("sections"), list):
            raise ValueError("SAG search response has no sections list")
        return result["sections"]


def augment_match_with_sag(
    parsed_jd: dict[str, Any],
    experiences: list[dict[str, Any]],
    baseline: dict[str, Any],
    *,
    client: SAGSearchClient | None = None,
    manifest: dict[str, Any] | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    """Add traceable SAG hits; explicit ``rerank`` only nudges already-ready matches.

    With no SAG configuration this returns the baseline unchanged. Failures
    degrade to baseline, never promote an unsupported or conflicting claim.
    """
    if client is None and manifest is None and mode is None:
        mode = os.getenv("APPLYGUARD_SAG_MODE", "off").lower()
        if mode == "off":
            return baseline
        if mode not in {"shadow", "rerank"}:
            return baseline
        path = os.getenv("APPLYGUARD_SAG_MAPPING_PATH", "")
        try:
            manifest = json.loads(Path(path).read_text(encoding="utf-8")) if path else None
            client = SAGSearchClient(
                os.environ["APPLYGUARD_SAG_BASE_URL"],
                os.environ["APPLYGUARD_SAG_SOURCE_ID"],
                os.environ["APPLYGUARD_SAG_TOKEN"],
                timeout=float(os.getenv("APPLYGUARD_SAG_TIMEOUT", "8")),
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return baseline
    if mode not in {"shadow", "rerank"} or client is None or not isinstance(manifest, dict):
        return baseline
    candidate_id = baseline.get("candidate_id")
    if manifest.get("candidate_id") != candidate_id or manifest.get("source_id") != client.source_id:
        return baseline

    verified: dict[str, str] = {}
    duplicate_evidence_ids: set[str] = set()
    for experience in experiences:
        if experience.get("candidate_id") != candidate_id:
            continue
        for source in experience.get("evidence_sources", []):
            if source.get("verification_status") == "VERIFIED":
                evidence_id = source["evidence_id"]
                if evidence_id in verified:
                    duplicate_evidence_ids.add(evidence_id)
                verified[evidence_id] = experience["experience_id"]
    if duplicate_evidence_ids:
        return baseline
    links: dict[str, str] = {}
    manifest_links = manifest.get("links")
    if not isinstance(manifest_links, list):
        return baseline
    for entry in manifest_links:
        if not isinstance(entry, dict):
            continue
        chunk_id, evidence_id = entry.get("chunk_id"), entry.get("evidence_id")
        if isinstance(chunk_id, str) and isinstance(evidence_id, str) and evidence_id in verified:
            if chunk_id in links and links[chunk_id] != evidence_id:
                return baseline  # ambiguous mapping is never silently accepted
            links[chunk_id] = evidence_id
    if not links:
        return baseline

    result = copy.deepcopy(baseline)
    matches_by_requirement: dict[str, list[dict[str, Any]]] = {}
    for match in result.get("matches", []):
        matches_by_requirement.setdefault(match["requirement_id"], []).append(match)
    try:
        for requirement in parsed_jd.get("requirements", []):
            requirement_id = requirement.get("requirement_id")
            candidates = matches_by_requirement.get(requirement_id, [])
            if not candidates:
                continue
            query = requirement.get("text") or " ".join(requirement.get("normalized_terms", []))
            if not isinstance(query, str) or not query.strip():
                continue
            hits = client.search(query)
            for hit in hits:
                if not isinstance(hit, dict) or hit.get("source_id") != client.source_id:
                    continue
                chunk_id = hit.get("chunk_id")
                evidence_id = links.get(chunk_id) if isinstance(chunk_id, str) else None
                if not evidence_id:
                    continue
                score = hit.get("score")
                if (not isinstance(score, (int, float)) or isinstance(score, bool)
                        or not math.isfinite(score) or score < 0):
                    continue
                for match in candidates:
                    if verified[evidence_id] != match["experience_id"] or evidence_id not in match.get("evidence_ids", []):
                        continue
                    support = {"evidence_id": evidence_id, "source_id": client.source_id, "chunk_id": chunk_id, "retrieval_score": float(score)}
                    if support not in match.setdefault("sag_support", []):
                        match["sag_support"].append(support)
            if mode == "rerank":
                for match in candidates:
                    if not match.get("ready_for_selection") or match.get("conflicts") or match.get("missing_evidence"):
                        continue
                    count = len({hit["evidence_id"] for hit in match.get("sag_support", [])})
                    if not count:
                        continue
                    old_score = match["relevance_score"]
                    bonus = round(min(1.0 - old_score, 0.03 * min(count, 2)), 4)
                    match["relevance_score"] = round(old_score + bonus, 4)
                    match["score_breakdown"]["sag_bonus"] = bonus
                    match["rationale"] += f" SAG 辅助检索命中 {count} 条已关联、已验证证据；仅调整排序，不改变核验状态。"
        if mode == "rerank":
            order = {item["requirement_id"]: index for index, item in enumerate(parsed_jd.get("requirements", []))}
            result["matches"].sort(key=lambda item: (order.get(item["requirement_id"], len(order)), -item["relevance_score"], item["experience_id"]))
    except (OSError, ValueError, TypeError, KeyError, TimeoutError):
        return baseline
    result["sag_auxiliary"] = {"mode": mode, "source_id": client.source_id}
    return result
