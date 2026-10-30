"""Recompute claims and simulated ATS controls after user edits, without paid calls."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from backend.services.career_vault import CareerVault
from backend.services.claim_validator import ClaimValidator
from backend.services.evidence_matcher import EvidenceMatcher
from backend.services.jd_parser import JDParser
from backend.services.local_evidence import attach_local_evidence
from backend.services.resume_draft_vault import experiences_from_resume_draft
from backend.services.risk_engine import RiskEngine
from backend.services.schema_validation import validate_contract


def simulator_mapping(application_id: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    return {'application_id': application_id, 'target': 'ATS_SIMULATOR',
            'fields': [{'field_id': 'candidate_summary', 'label': '候选人摘要',
                        'value': ' '.join(claim['text'] for claim in claims),
                        'source_claim_ids': [claim['claim_id'] for claim in claims],
                        'action': 'SAFE_TO_FILL' if claims else 'BLOCKED'}],
            'unmapped_fields': ['work_authorization'],
            'consistency_state': 'NEEDS_REVIEW' if claims else 'BLOCKED'}


def reverify_workflow(vault_path: Path, request: dict[str, Any], *, _skip_grounding: bool = False) -> dict[str, Any]:
    from backend.services.job_radar import validate_target
    validate_target(request)
    from backend.services.skill_router import validate_request_ids
    validate_request_ids(request)
    candidate = request['candidate_id']
    application = request.get('application_id') or 'app_demo_001'
    raw = request.get('claims')
    if not isinstance(raw, list) or len(raw) > 20:
        raise ValueError('claims must be an array of at most 20 items')
    draft = request.get('resume_draft')
    if isinstance(draft, dict):
        items = experiences_from_resume_draft(draft)
        if not items or any(item['candidate_id'] != candidate for item in items):
            raise ValueError('Resume draft is empty or belongs to another candidate')
        items = attach_local_evidence(items, draft)
    else:
        items = CareerVault.from_json(vault_path).list_experiences(candidate)
    if not items:
        raise ValueError('Candidate has no experiences')
    for item in items:
        validate_contract('experience', item)
    # Never trust client verification, evidence refs, parsed requirements or risk decisions.
    originals = {claim['claim_id']: claim for item in items for claim in item['claims']}
    parsed, _, _ = JDParser().parse(request.get('jd_text'))
    matched = EvidenceMatcher().match(parsed, items)
    claims, results, seen = [], [], set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError('Each claim must be an object')
        claim_id, text = entry.get('claim_id'), entry.get('text')
        if (not isinstance(claim_id, str) or not claim_id.startswith('claim_') or
                not claim_id.removeprefix('claim_').replace('_', '').isalnum() or
                claim_id in seen or not isinstance(text, str) or not 0 < len(text.strip()) <= 420):
            raise ValueError('Invalid, duplicate or oversized claim')
        seen.add(claim_id)
        original = originals.get(claim_id)
        refs = original['evidence_ids'] if original else []
        draft_source = any(key.startswith('ev_draft_') for key in refs)
        relevant = [row['requirement_id'] for row in matched['matches'] if claim_id in row['claim_ids']]
        claim = {'claim_id': claim_id, 'application_id': application, 'text': text.strip(),
                 'evidence_ids': refs, 'requirement_ids': sorted(set(relevant)),
                 'evidence_support_score': float(original.get('confidence', 0)) if original else 0,
                 'selection_reason': 'User selection checked by backend against candidate-owned evidence.',
                 'status': 'DRAFT'}
        if original is None or draft_source or not refs:
            result = {'claim_id': claim_id, 'state': 'BLOCKED', 'grounded': False, 'support_score': 0,
                      'unsupported_fragments': [text.strip()],
                      'explanation': '没有可支持本句的候选人证据原件；人工确认不能解除无证据阻断。'}
        else:
            result = ClaimValidator().verify(claim, items, candidate, matched)
        if result['state'] == 'BLOCKED':
            claim['status'] = 'BLOCKED'
        validate_contract('claim-verification', result)
        # Unsupported editable drafts stay outside the frozen ResumeClaim contract
        # (which requires evidence + requirement refs); they are always non-exportable.
        if refs and relevant:
            validate_contract('resume-claim', claim)
        claims.append(claim)
        results.append(result)
    mapping = simulator_mapping(application, claims)
    engine = RiskEngine()
    for control in engine.field_controls(mapping, results):
        for field in mapping['fields']:
            if field['field_id'] == control['field_id']:
                field['action'] = control['action']
    if any(field['action'] == 'BLOCKED' for field in mapping['fields']):
        mapping['consistency_state'] = 'BLOCKED'
    risk = engine.assess(application, results, mapping, matched)
    blocked = risk['action'] == 'BLOCKED'
    trace_id = 'trace_' + uuid.uuid4().hex[:12]
    audit = {'audit_id': 'audit_' + uuid.uuid4().hex[:12], 'application_id': application, 'version': 1,
             'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
             'event': 'APPLICATION_CLAIMS_REVERIFIED', 'actor': 'applyguard.reverification',
             'trace_id': trace_id, 'decision': 'PENDING'}
    validate_contract('form-mapping', mapping)
    validate_contract('risk-result', risk)
    validate_contract('audit-record', audit)
    from backend.services.skill_router import STEPS
    trace = [{'step': step, 'status': 'COMPLETED'} for step in STEPS[:7]]
    trace += [{'step': 'Human Confirmation', 'status': 'BLOCKED' if blocked else 'PENDING'},
              {'step': 'Audit Record', 'status': 'CREATED'}]
    response = {'resume_claims': claims, 'step_trace': trace, 'evidence_match': matched,
            'evidence_sources': [source for item in items for source in item['evidence_sources']], 'claim_verification': results, 'ats_form_mapping': mapping,
            'field_controls': engine.field_controls(mapping, results), 'risk_result': risk,
            'workflow_status': 'BLOCKED' if blocked else 'AWAITING_HUMAN_CONFIRMATION',
            'human_confirmation': {'required': True, 'reason': '用户修改后已重新核验，请检查新的风险结果。',
                                   'allowed_actions': ['EDIT', 'CANCEL'] if blocked else ['CONFIRM', 'EDIT', 'CANCEL']},
            'trace_id': trace_id, 'audit_record': audit, 'requires_reverification': False}
    if _skip_grounding:
        return response
    from backend.services.grounded_workflow import apply_grounding
    return apply_grounding(vault_path, request, response)
