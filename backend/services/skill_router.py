"""C orchestration: every module has a validated boundary and auditable failure stop."""
from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.services.career_vault import CareerVault
from backend.services.claim_validator import ClaimValidator
from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.jd_parser import JDParser, JDParseError
from backend.services.model_client import ModelClient
from backend.services.prompts import JD_PARSE_PROMPT_VERSION
from backend.services.resume_selector import ResumeSelector
from backend.services.risk_engine import RiskEngine
from backend.services.schema_validation import validate_contract

STEPS = ("Career Vault", "JD Parser", "Evidence Matcher", "Resume Selector", "Claim Validator",
         "ATS Form Mapper", "Risk Check", "Human Confirmation", "Audit Record")


class WorkflowStopped(ValueError):
    def __init__(self, message: str, trace_id: str, step_trace: list[dict[str, Any]],
                 audit_record: dict[str, Any], code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.trace_id, self.step_trace, self.audit_record, self.code = trace_id, step_trace, audit_record, code


def validate_request_ids(request: dict[str, Any]) -> None:
    for key, prefix in (("candidate_id", "cand_"), ("application_id", "app_"), ("trace_id", "trace_")):
        value = request.get(key)
        if key == "candidate_id" or value is not None:
            if not isinstance(value, str) or not re.fullmatch(prefix + r"[a-zA-Z0-9_]{1,100}", value):
                raise ValueError(f"{key} must be a valid {prefix} identifier")


class SkillRouter:
    def __init__(self, vault_path: Path, form_mapping: dict[str, Any], model: ModelClient | None = None,
                 *, selector: ResumeSelector | None = None) -> None:
        self.vault_path, self.form_mapping, self.model = vault_path, form_mapping, model
        self.selector = selector or ResumeSelector()

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        validate_request_ids(request)
        candidate_id = request["candidate_id"]
        application_id = request.get("application_id") or "app_demo_001"
        trace_id = request.get("trace_id") or f"trace_{uuid.uuid4().hex[:12]}"
        trace: list[dict[str, Any]] = []
        modes = {"career_vault": "DETERMINISTIC_SEED", "evidence_matcher": "DETERMINISTIC",
                 "resume_selector": "DETERMINISTIC", "claim_validator": "DETERMINISTIC",
                 "ats_form_mapper": "FIXTURE", "risk_check": "DETERMINISTIC",
                 "human_confirmation": "STOP_ONLY", "audit_record": "IN_MEMORY",
                 "jd_prompt_version": JD_PARSE_PROMPT_VERSION,
                 "requested_parse_mode": str(request.get("parse_mode") or "dynamic").upper()}

        def audit(event: str) -> dict[str, Any]:
            record = {"audit_id": f"audit_{uuid.uuid4().hex[:12]}", "application_id": application_id,
                      "version": 1, "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                      "event": event, "actor": "applyguard.mock-workflow", "trace_id": trace_id, "decision": "PENDING"}
            validate_contract("audit-record", record)
            return record

        def execute(name: str, operation: Callable[[], Any]) -> Any:
            try:
                result = operation()
            except Exception as exc:
                trace.append({"step": name, "status": "FAILED", "reason": type(exc).__name__})
                trace.extend({"step": later, "status": "SKIPPED"} for later in STEPS[STEPS.index(name) + 1:8])
                trace.append({"step": "Audit Record", "status": "CREATED"})
                record = audit("APPLICATION_DRAFT_PARSE_FAILED" if name == "JD Parser" else "APPLICATION_DRAFT_STEP_FAILED")
                message = str(exc) if isinstance(exc, JDParseError) else f"{name} failed validation or execution; workflow stopped safely"
                code = "VALIDATION_ERROR" if isinstance(exc, ValueError) else "INTERNAL_ERROR"
                raise WorkflowStopped(message, trace_id, trace, record, code) from exc
            trace.append({"step": name, "status": "COMPLETED"})
            return result

        def load_vault():
            items = CareerVault.from_json(self.vault_path).list_experiences(candidate_id)
            if not items:
                raise ValueError("Empty Career Vault")
            for item in items:
                validate_contract("experience", item)
            return items

        experiences = execute("Career Vault", load_vault)
        parsed, parser_mode, failure = execute("JD Parser", lambda: JDParser(self.model).parse(request.get("jd_text")))
        trace[-1].update(mode=parser_mode)
        if failure:
            trace[-1]["fallback_reason"] = failure
        modes["jd_parser"] = parser_mode

        def match():
            result = EvidenceMatcher().match(parsed, experiences)
            validate_contract("evidence-match", result)
            return result
        matched = execute("Evidence Matcher", match)

        def select():
            result = self.selector.select(matched, experiences, application_id, max_claims=3)
            for claim in result.claims:
                validate_contract("resume-claim", claim)
            if len({claim["claim_id"] for claim in result.claims}) != len(result.claims):
                raise ValueError("Duplicate selected Claim IDs")
            return result
        selection = execute("Resume Selector", select)

        def verify():
            results = ClaimValidator().verify_all(selection.claims, experiences, candidate_id, matched)
            if {item["claim_id"] for item in results} != {item["claim_id"] for item in selection.claims} or len(results) != len(selection.claims):
                raise ValueError("Verification results do not cover every selected claim exactly once")
            for result in results:
                validate_contract("claim-verification", result)
            return results
        verified = execute("Claim Validator", verify)
        claim_by_id = {item["claim_id"]: item for item in selection.claims}
        for result in verified:
            if result["state"] == "BLOCKED":
                claim_by_id[result["claim_id"]]["status"] = "BLOCKED"
        risk_engine = RiskEngine()

        def map_fixture():
            mapping = copy.deepcopy(self.form_mapping)
            mapping["application_id"] = application_id
            validate_contract("form-mapping", mapping)
            for field in mapping["fields"]:
                refs = field["source_claim_ids"]
                if any(key not in claim_by_id for key in refs):
                    field["action"] = "BLOCKED"
                elif refs and field["value"] != " ".join(claim_by_id[key]["text"] for key in refs):
                    field["action"] = "REQUIRES_CONFIRMATION" if field["action"] != "BLOCKED" else "BLOCKED"
            for control in risk_engine.field_controls(mapping, verified):
                for field in mapping["fields"]:
                    if field["field_id"] == control["field_id"]:
                        field["action"] = control["action"]
            if any(field["action"] == "BLOCKED" for field in mapping["fields"]):
                mapping["consistency_state"] = "BLOCKED"
            elif any(field["action"] == "REQUIRES_CONFIRMATION" for field in mapping["fields"]):
                mapping["consistency_state"] = "NEEDS_REVIEW"
            validate_contract("form-mapping", mapping)
            return mapping
        mapping = execute("ATS Form Mapper", map_fixture)
        trace[-1]["mode"] = "FIXTURE"

        def assess():
            result = risk_engine.assess(application_id, verified, mapping, matched)
            validate_contract("risk-result", result)
            return result
        risk = execute("Risk Check", assess)
        trace.append({"step": "Human Confirmation", "status": "BLOCKED" if risk["action"] == "BLOCKED" else "PENDING"})
        record = audit("APPLICATION_DRAFT_BLOCKED" if risk["action"] == "BLOCKED" else "APPLICATION_DRAFT_PREPARED")
        trace.append({"step": "Audit Record", "status": "CREATED"})
        return {"trace_id": trace_id, "application_id": application_id, "candidate_id": candidate_id,
                "execution_mode": "DYNAMIC_MODEL" if parser_mode.startswith("MODEL") else "DETERMINISTIC_FALLBACK",
                "mock_notice": "C results are computed; ATS mapping is a simulator fixture and audit storage is in-memory.",
                "workflow_status": "BLOCKED" if risk["action"] == "BLOCKED" else "AWAITING_HUMAN_CONFIRMATION",
                "parsed_jd": parsed, "evidence_match": matched, "resume_claims": selection.claims,
                "resume_selection": {"mode": "DETERMINISTIC_EVIDENCE_CONSTRAINED", "removed_claims": selection.removed_claims,
                                     "max_claims": 3, "max_characters": 420},
                "claim_verification": verified, "ats_form_mapping": mapping, "risk_result": risk,
                "field_controls": risk_engine.field_controls(mapping, verified),
                "human_confirmation": {"required": True,
                                       "reason": "Blocked content must be corrected before review." if risk["action"] == "BLOCKED" else "User must review the application before submission.",
                                       "allowed_actions": ["EDIT", "CANCEL"] if risk["action"] == "BLOCKED" else ["CONFIRM", "EDIT", "CANCEL"]},
                "audit_record": record, "step_trace": trace, "component_modes": modes}
