from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Protocol

from backend.services.third_party.asu_metric_validation import validate_metric


_RATIO_FIELDS = {"numerator", "denominator", "displayed_percent"}
_CHANGE_FIELDS = {"baseline", "result", "change_type", "displayed_change"}


def _validate_metric_calculation(metric: dict[str, Any]) -> None:
    """Check only optional, fully structured Vault arithmetic at ingestion.

    This is not final Claim validation or verification that a source is truthful.
    """
    if "calculation" not in metric:
        return
    calculation = metric["calculation"]
    metric_id = metric.get("metric_id", "<unknown metric>")
    if not isinstance(calculation, dict) or not calculation:
        raise ValueError(f"{metric_id} calculation must be a nonempty object")
    if set(calculation) - (_RATIO_FIELDS | _CHANGE_FIELDS):
        raise ValueError(f"{metric_id} calculation has unsupported fields")
    ratio_present = set(calculation) & _RATIO_FIELDS
    change_present = set(calculation) & _CHANGE_FIELDS
    if ratio_present and ratio_present != _RATIO_FIELDS:
        raise ValueError(f"{metric_id} percentage calculation requires numerator, denominator, and displayed_percent")
    if change_present and change_present != _CHANGE_FIELDS:
        raise ValueError(f"{metric_id} change calculation requires baseline, result, change_type, and displayed_change")
    if not ratio_present and not change_present:
        raise ValueError(f"{metric_id} calculation has no supported arithmetic fields")
    for field in (_RATIO_FIELDS | _CHANGE_FIELDS) - {"change_type"}:
        if field not in calculation:
            continue
        value = calculation[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{metric_id} calculation.{field} must be a finite number")
        try:
            if not math.isfinite(value):
                raise ValueError(f"{metric_id} calculation.{field} must be a finite number")
        except OverflowError as exc:
            raise ValueError(f"{metric_id} calculation.{field} must be a finite number") from exc
    errors: list[str] = []
    validate_metric({"id": metric_id, "metric": calculation}, errors)
    if errors:
        raise ValueError("; ".join(errors))


class CareerVaultRepository(Protocol):
    """Storage boundary for the proposal JSON store and a future database store."""

    def list_experiences(self, candidate_id: str) -> list[dict[str, Any]]:
        """Return a candidate's experiences without exposing mutable storage."""


class JsonCareerVaultRepository:
    """Read-only fictional JSON storage for the proposal baseline."""

    def __init__(self, source: Path) -> None:
        with source.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        self._validate(payload)
        self._candidate_id = payload["candidate_id"]
        self._experiences = payload["experiences"]

    def list_experiences(self, candidate_id: str) -> list[dict[str, Any]]:
        if candidate_id != self._candidate_id:
            raise ValueError(f"candidate_id not found: {candidate_id}")
        return copy.deepcopy(self._experiences)

    @staticmethod
    def _validate(payload: dict[str, Any]) -> None:
        candidate_id = payload.get("candidate_id")
        experiences = payload.get("experiences")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("Career Vault requires a candidate_id")
        if not isinstance(experiences, list) or not experiences:
            raise ValueError("Career Vault requires at least one experience")

        experience_ids: set[str] = set()
        claim_ids: set[str] = set()
        evidence_ids: set[str] = set()
        for experience in experiences:
            if experience.get("candidate_id") != candidate_id:
                raise ValueError("Career Vault experience candidate_id must match the vault candidate_id")
            experience_id = experience.get("experience_id")
            if not isinstance(experience_id, str) or experience_id in experience_ids:
                raise ValueError("Career Vault experience_id values must be unique")
            experience_ids.add(experience_id)

            source_ids = {source.get("evidence_id") for source in experience.get("evidence_sources", [])}
            if any(not isinstance(source_id, str) or not source_id for source_id in source_ids) or len(source_ids) != len(experience.get("evidence_sources", [])):
                raise ValueError("Career Vault evidence_id values must be present and unique per experience")
            if evidence_ids.intersection(source_ids):
                raise ValueError("Career Vault evidence_id values must be unique across experiences")
            evidence_ids.update(source_ids)
            for source in experience.get("evidence_sources", []):
                if source.get("source_type", source.get("type")) != source.get("type"):
                    raise ValueError("Career Vault source_type must agree with the frozen type field")

            for metric in experience.get("metrics", []):
                metric_evidence_ids = metric.get("evidence_ids", [])
                if not metric_evidence_ids or not set(metric_evidence_ids).issubset(source_ids):
                    raise ValueError("Career Vault metrics must reference evidence in their experience")
                _validate_metric_calculation(metric)

            for claim in experience.get("claims", []):
                claim_id = claim.get("claim_id")
                if not isinstance(claim_id, str) or claim_id in claim_ids:
                    raise ValueError("Career Vault claim_id values must be unique")
                claim_ids.add(claim_id)
                claim_evidence_ids = claim.get("evidence_ids", [])
                if not claim_evidence_ids or not set(claim_evidence_ids).issubset(source_ids):
                    raise ValueError("Career Vault claims must reference evidence in their experience")

        awards = payload.get("awards", [])
        if awards:
            if not isinstance(awards, list):
                raise ValueError("Career Vault awards must be a list")
            award_ids: set[str] = set()
            for award in awards:
                award_id = award.get("award_id") if isinstance(award, dict) else None
                name = award.get("name") if isinstance(award, dict) else None
                if not isinstance(award_id, str) or award_id in award_ids:
                    raise ValueError("Career Vault award_id values must be unique")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Career Vault awards require a name")
                award_ids.add(award_id)


class CareerVault:
    """Domain facade used by the matcher and selector, independent from HTTP."""

    def __init__(self, repository: CareerVaultRepository) -> None:
        self._repository = repository

    @classmethod
    def from_json(cls, source: Path) -> "CareerVault":
        return cls(JsonCareerVaultRepository(source))

    def list_experiences(self, candidate_id: str) -> list[dict[str, Any]]:
        return self._repository.list_experiences(candidate_id)

    def get_experience(self, candidate_id: str, experience_id: str) -> dict[str, Any]:
        for experience in self.list_experiences(candidate_id):
            if experience["experience_id"] == experience_id:
                return experience
        raise ValueError(f"experience_id not found: {experience_id}")

    def evidence_by_id(self, candidate_id: str) -> dict[str, dict[str, Any]]:
        evidence: dict[str, dict[str, Any]] = {}
        for experience in self.list_experiences(candidate_id):
            for source in experience["evidence_sources"]:
                evidence[source["evidence_id"]] = source
        return evidence
