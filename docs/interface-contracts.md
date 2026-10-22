# Interface contracts

The JSON Schemas in `contracts/` are the proposal source of truth. All service implementations may change internally, but their exchanged objects must remain compatible or use an explicit contract version. The contracts preserve the selected topic's evidence graph, explainable selection, validation, risk, form mapping, and audit boundaries even when the proposal uses deterministic fixtures.

## Contract list

| File | Producer | Main consumer |
| --- | --- | --- |
| `experience.schema.json` | Career Vault | Evidence Matcher |
| `parsed-jd.schema.json` | JD Parser | Evidence Matcher |
| `evidence-match.schema.json` | Evidence Matcher | Resume Selector |
| `resume-claim.schema.json` | Resume Selector | Claim Validator |
| `claim-verification.schema.json` | Claim Validator | Risk Check and UI |
| `risk-result.schema.json` | Risk Check | Human Confirmation and UI |
| `form-mapping.schema.json` | ATS Form Mapper Skill | Risk Skill and UI |
| `audit-record.schema.json` | Workflow Orchestrator | Audit view and evaluation |
| `error.schema.json` | Every service | UI, logs, and tests |

## Shared skill boundary

AI-assisted modules follow `Router → Specialized Skill → Validator`. Each skill result must pass JSON Schema validation and semantic validation. A failed result may retry once under the configured policy and must then use a deterministic fallback or stop safely. The workflow records which path produced the result.

Required trace fields across skill outputs are:

- `trace_id` or a parent workflow trace;
- source evidence text or evidence IDs;
- confidence or support score where uncertainty matters;
- explanation for selection, removal, review, or blocking;
- validation state and fallback state.

## API endpoints

### `GET /health`

Success response:

```json
{
  "status": "ok",
  "service": "applyguard-foundation",
  "version": "0.1.0",
  "time": "2026-10-01T00:00:00Z"
}
```

### `POST /api/v1/workflow/mock`

Required request fields:

- `candidate_id`: non-empty string.
- `jd_text`: at least 20 characters.

The response contains `parsed_jd`, `evidence_match`, `resume_claims`, `claim_verification`, `ats_form_mapping`, `risk_result`, `human_confirmation`, `audit_record`, and the nine-step `step_trace`. In the proposal scaffold these objects may come from fixtures; the endpoint must label itself as a mock and must not imply that the input JD was analyzed dynamically.

## Unified errors

All failures use:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "candidate_id must be a non-empty string",
    "details": [],
    "trace_id": "trace_example"
  }
}
```

Initial error codes:

| Code | HTTP status | Meaning |
| --- | --- | --- |
| `INVALID_JSON` | 400 | Request body cannot be decoded as JSON |
| `VALIDATION_ERROR` | 422 | Required content is missing or invalid |
| `NOT_FOUND` | 404 | Route or resource does not exist |
| `INTERNAL_ERROR` | 500 | Unexpected server failure; implementation reserved for the next iteration |

## Change rule

Backward-compatible fields may be added after A's handoff. Renaming or removing a field requires a versioned contract and coordinated updates across producers, consumers, examples, diagrams, and tests. The fields added to preserve the selected topic's core mechanisms are part of the A-to-B baseline and must not be silently dropped.

## B compatibility extensions

B added optional fields only; every pre-B valid object remains valid.

- `experience.schema.json` now permits optional `title` and `responsibilities`. Evidence sources may additionally carry `source_type`, `source_reference`, `confidence`, and `verification_status`. Existing `role`, `summary`, `type`, `description`, `uri`, and verification fields remain unchanged.
- Its existing Metric objects additionally permit an optional `calculation` object with explicit numerator/denominator/percentage or baseline/result/change fields. The B Vault adapter rejects partial or inconsistent arithmetic at ingestion; the retained upstream calculation permits 0.5 absolute rounding tolerance. Old Metric objects without `calculation` remain valid; this check does not establish that free-text `value` or a resume Claim is true.
- `evidence-match.schema.json` now permits optional match-level `evidence_ids`, `missing_evidence`, `ready_for_selection`, and a bounded `score_breakdown`; it also permits top-level `uncovered_requirements`. Its original required fields and names are unchanged.
- The mock endpoint adds the backward-compatible `resume_selection` object for B's removed-claim audit. Each item in `resume_claims` continues to satisfy `resume-claim.schema.json`.

These extensions expose B's deterministic baseline. They do not implement C's JD Parser or Claim Validator, nor D's form mapping or Human Confirmation UI.

## C compatible workflow extension

`POST /api/v1/workflow/mock` accepts optional `parse_mode: "dynamic" | "offline" | "fixture"`. Dynamic mode uses the supplied JD, C verification, and C risk result. With an API key in the environment, dynamic mode is the default; no-key/no-mode retains the original fixture behavior. The response adds `component_modes` to identify model/fallback parsing and ATS fixture mapping. No frozen contract fields or enums were changed. A parse safe-stop uses the existing 422 error envelope; `error.details[0]` contains a step trace and failed-parse audit record. Audit `decision` remains the frozen `PENDING`; the event and workflow/risk states convey blocked status.


C audit additions: `offline` disables model creation even when an API key exists. `field_controls` provides per-field `level` (L0–L3), `action`, `show_sources`, and `source_claim_ids` outside the frozen core contracts. Aggregate risk and per-field controls are different axes. Evidence can be joined through `claim_id` → `resume_claims.evidence_ids` → Vault evidence sources without modifying the frozen verification schema. Source confidence is a conservative support bound, not calibrated truth probability. Every module failure has a skipped remainder and audit event; HTTP 500 is reserved for execution failure, 422 for validation failure. Requests are limited to 262144 bytes, JD text to 20000 characters, parsed requirements to 40; oversized results are rejected rather than silently truncated.

### 2026-10-22 compatible repair extensions

`POST /api/v1/workflow/reverify` takes candidate/application IDs, raw JD, optional explicit local resume draft, and an array of Claim ID/text pairs. It reloads evidence rather than trusting client statuses, recalculates verification, simulated mapping and risk, and returns replacement workflow fields. `requires_reverification` and `evidence_sources` are optional response metadata. Unsupported editable drafts are always blocked and are not frozen contract-valid selected Resume Claims. Existing JSON Schemas remain unchanged. See [repair handoff](fixes-2026-10-22.md) for limits and source-ID mapping.

`POST /api/v1/resume/parse` accepts `parse_mode` (offline default, dynamic opt-in); presence of an API key alone never opts the document into model processing. Final UI export rechecks current backend evidence and fails closed on revocation or connectivity failure.
