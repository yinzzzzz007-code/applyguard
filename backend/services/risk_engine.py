"""Deterministic risk-to-control decisions; never authorizes submission."""

from __future__ import annotations

from typing import Any
import re

from backend.services.schema_validation import validate_contract


_SENSITIVE = ("work_authorization", "visa", "salary", "expected_salary", "disability", "gender",
              "race", "legal_declaration", "certification", "attestation", "signature", "work_eligibility", "citizenship", "criminal", "birth", "ssn", "工作许可", "工作授权", "薪资", "国籍", "残疾", "法律声明")


def sensitive_field(name: str) -> bool:
    normal = re.sub(r"[\s-]+", "_", name.casefold())
    return any(re.search(r"(?:^|_)" + re.escape(term) + r"(?:_|$)", normal) for term in _SENSITIVE)


class RiskEngine:
    def field_controls(self, form_mapping: dict[str, Any], verifications: list[dict[str, Any]]) -> list[dict[str, Any]]:
        states = {item["claim_id"]: item["state"] for item in verifications}
        controls = []
        for field in form_mapping.get("fields", []):
            references = field.get("source_claim_ids", [])
            blocked = field["action"] == "BLOCKED" or any(states.get(key) in (None, "BLOCKED") for key in references)
            sensitive = sensitive_field(field["field_id"]) or sensitive_field(field["label"])
            review = field["action"] == "REQUIRES_CONFIRMATION" or any(states[key] == "NEEDS_REVIEW" for key in references if key in states)
            level = "L3" if blocked or sensitive else "L2" if review else "L1" if references else "L0"
            controls.append({"field_id": field["field_id"], "level": level,
                             "action": "BLOCKED" if blocked else "REQUIRES_CONFIRMATION" if sensitive or review else "SAFE_TO_FILL",
                             "show_sources": bool(references), "source_claim_ids": references})
        for name in form_mapping.get("unmapped_fields", []):
            controls.append({"field_id": name, "level": "L3" if sensitive_field(name) else "L2",
                             "action": "REQUIRES_CONFIRMATION", "show_sources": False, "source_claim_ids": []})
        return controls

    def assess(self, application_id: str, verifications: list[dict[str, Any]],
               form_mapping: dict[str, Any], evidence_match: dict[str, Any]) -> dict[str, Any]:
        risks: list[dict[str, Any]] = []

        def add(kind: str, severity: str, message: str, claim_ids: list[str], action: str, mitigation: str) -> None:
            risks.append({"risk_id": f"risk_{len(risks)+1:03d}", "type": kind,
                          "severity": severity, "message": message, "related_claim_ids": claim_ids,
                          "mitigation": mitigation, "recommended_action": action})

        for verification in verifications:
            if verification["state"] == "BLOCKED":
                add("UNSUPPORTED_CLAIM", "ERROR", verification["explanation"], [verification["claim_id"]],
                    "BLOCK", "Remove or edit the claim and supply verified candidate-owned evidence before reevaluation.")
            elif verification["state"] == "NEEDS_REVIEW":
                add("UNSUPPORTED_CLAIM", "WARNING", verification["explanation"], [verification["claim_id"]],
                    "CONFIRM", "Review the evidence and correct the claim before filling.")
        for match in evidence_match.get("matches", []):
            if match.get("conflicts") and any(claim_id in match.get("claim_ids", []) for claim_id in
                                              [item["claim_id"] for item in verifications]):
                add("CONFLICT", "ERROR", "Selected claim has conflicting evidence.", match["claim_ids"],
                    "BLOCK", "Resolve the evidence conflict and rerun verification.")
        for uncovered in evidence_match.get("uncovered_requirements", []):
            add("OTHER", "WARNING", f"JD requirement {uncovered.get('requirement_id', '')} has no ready evidence.", [],
                "CONFIRM", "Show the coverage gap; do not generate a claim for it without new evidence.")
        for field in form_mapping.get("unmapped_fields", []):
            sensitive = sensitive_field(field)
            add("MISSING_FIELD", "WARNING", f"ATS field {field} is missing; its value must not be guessed.", [],
                "CONFIRM", "Ask the user to supply and confirm the value." if sensitive else "Ask the user to review the missing field.")
            if sensitive:
                add("PRIVACY", "WARNING", f"Missing sensitive field {field} needs the user's own answer.", [], "CONFIRM", "Do not infer sensitive values.")
        if form_mapping.get("consistency_state") == "NEEDS_REVIEW" and not form_mapping.get("unmapped_fields"):
            add("OTHER", "WARNING", "ATS mapping needs review.", [], "CONFIRM", "Review mapped values before filling.")
        for field in form_mapping.get("fields", []):
            controls = next(control for control in self.field_controls(form_mapping, verifications) if control["field_id"] == field["field_id"])
            if controls["action"] == "BLOCKED":
                add("OTHER", "ERROR", f"ATS field {field.get('label', '')} is blocked or references an unverified claim ID.",
                    field.get("source_claim_ids", []), "BLOCK", "Correct the field and verify every linked claim before continuing.")
            elif sensitive_field(field["field_id"]) or sensitive_field(field["label"]):
                add("PRIVACY", "WARNING", f"ATS field {field.get('label', '')} requires human confirmation.",
                    field.get("source_claim_ids", []), "CONFIRM", "Show the source and ask the user to confirm.")
            elif controls["action"] == "REQUIRES_CONFIRMATION":
                add("OTHER", "WARNING", f"ATS field {field.get('label', '')} is ambiguous or needs evidence review.",
                    field.get("source_claim_ids", []), "CONFIRM", "Review the claim and mapped value.")
        if form_mapping.get("consistency_state") == "BLOCKED":
            add("CONFLICT", "ERROR", "ATS mapping is inconsistent.", [], "BLOCK", "Resolve mapping conflict.")
        block = any(item["recommended_action"] == "BLOCK" for item in risks)
        confirm = any(item["recommended_action"] == "CONFIRM" for item in risks)
        result = {"application_id": application_id, "risk_level": "BLOCK" if block else "HIGH" if confirm and
                  any(item["type"] == "PRIVACY" for item in risks) else "MEDIUM" if confirm else "LOW",
                  "action": "BLOCKED" if block else "REQUIRES_CONFIRMATION" if confirm else "SAFE_TO_FILL",
                  "risks": risks, "requires_human_confirmation": block or confirm}
        validate_contract("risk-result", result)
        return result
