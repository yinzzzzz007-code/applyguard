"""Local, atomic resume drafts. User edits never inherit seed evidence silently."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.schema_validation import validate_contract


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


class DraftStore:
    def __init__(self, directory: Path, seed_path: Path) -> None:
        self.directory = directory
        self.seed_path = seed_path

    def _path(self, candidate_id: str) -> Path:
        if not re.fullmatch(r"cand_[a-zA-Z0-9_]{1,100}", candidate_id):
            raise ValueError("candidate_id must be a valid cand_ identifier")
        return self.directory / f"{candidate_id}.json"

    def load(self, candidate_id: str) -> dict[str, Any] | None:
        path = self._path(candidate_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        if payload.get("candidate_id") != candidate_id or not isinstance(payload.get("form"), dict):
            raise ValueError("stored draft is invalid")
        return payload

    def save(self, candidate_id: str, form: dict[str, Any]) -> dict[str, Any]:
        self._path(candidate_id)
        if form.get("candidateId") != candidate_id:
            raise ValueError("draft candidate does not match request")
        for key in ("basic", "intention", "education", "internships", "projects", "extras"):
            if not isinstance(form.get(key), (list if key in ("education", "internships", "projects") else dict)):
                raise ValueError(f"draft {key} has invalid type")
        if not isinstance(form.get("awards", []), list) or len(form.get("awards", [])) > 30:
            raise ValueError("draft awards must be a list of at most 30 entries")
        vault = self.to_vault(candidate_id, form)
        for experience in vault["experiences"]:
            validate_contract("experience", experience)
        for award in vault["awards"]:
            validate_contract("award", award)
        saved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        saved_form = {**form, "savedAt": saved_at, "dirty": False}
        version = hashlib.sha256(json.dumps(vault, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        payload = {**vault, "saved_at": saved_at, "version": version,
                   "form": saved_form, "vault": vault}
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.directory,
                                             prefix=".draft-", suffix=".tmp", delete=False) as stream:
                tmp_name = stream.name
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_name, self._path(candidate_id))
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
        return payload

    def to_vault(self, candidate_id: str, form: dict[str, Any]) -> dict[str, Any]:
        with self.seed_path.open("r", encoding="utf-8") as stream:
            seed = json.load(stream)
        source = {exp["experience_id"]: exp for exp in seed["experiences"]}
        experiences: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        for entry in [*form["internships"], *form["projects"]]:
            if not isinstance(entry, dict):
                raise ValueError("experience entry must be an object")
            description = _text(entry.get("description"))
            if not description:
                continue
            raw_id = _text(entry.get("id"))
            exp_id = raw_id if re.fullmatch(r"exp_[a-zA-Z0-9_]+", raw_id) else "exp_" + hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]
            if exp_id in used_ids:
                raise ValueError("duplicate experience identifier")
            used_ids.add(exp_id)
            title = _text(entry.get("title")) or _text(entry.get("role")) or "未命名经历"
            role = _text(entry.get("role")) or title
            organization = _text(entry.get("organization")) or "未填写组织"
            start = _text(entry.get("start")) or None
            end = _text(entry.get("end")) or None
            source_id = _text(entry.get("sourceExperienceId"))
            original = source.get(source_id)
            original_description = "\n".join([original["summary"], *original.get("responsibilities", [])]) if original else ""
            unchanged = bool(candidate_id == seed["candidate_id"] and original and original["experience_id"] == exp_id and
                             original.get("title", original["role"]) == title and original["role"] == role and
                             original["organization"] == organization and original.get("start_date") == start and
                             original.get("end_date") == end and original_description == description)
            if unchanged:
                experiences.append(copy.deepcopy(original))
            else:
                experiences.append({"experience_id": exp_id, "candidate_id": candidate_id,
                                    "title": title, "organization": organization, "role": role,
                                    "start_date": start, "end_date": end, "summary": description,
                                    "responsibilities": [], "skills": [], "metrics": [], "claims": [],
                                    "evidence_sources": [], "verification_state": "UNVERIFIED"})
        awards = [copy.deepcopy(award) for award in form.get("awards", [])
                  if isinstance(award, dict) and _text(award.get("name"))]
        if len({award.get("id") for award in awards}) != len(awards):
            raise ValueError("duplicate award identifier")
        return {"candidate_id": candidate_id,
                "profile": {"display_name": _text(form["basic"].get("name")),
                            "education": "；".join(_text(e.get("school")) for e in form["education"] if isinstance(e, dict)),
                            "consent": "仅用于本地模拟；编辑内容需重新核验"},
                "experiences": experiences,
                "awards": awards}
