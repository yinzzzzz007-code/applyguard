from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Protocol


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

            for claim in experience.get("claims", []):
                claim_id = claim.get("claim_id")
                if not isinstance(claim_id, str) or claim_id in claim_ids:
                    raise ValueError("Career Vault claim_id values must be unique")
                claim_ids.add(claim_id)
                claim_evidence_ids = claim.get("evidence_ids", [])
                if not claim_evidence_ids or not set(claim_evidence_ids).issubset(source_ids):
                    raise ValueError("Career Vault claims must reference evidence in their experience")


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
