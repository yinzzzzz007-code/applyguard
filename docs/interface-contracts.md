# Interface contracts

The JSON Schemas in `contracts/` are the proposal source of truth. All service implementations may change internally, but their exchanged objects must remain compatible.

## Contract list

| File | Producer | Main consumer |
| --- | --- | --- |
| `experience.schema.json` | Career Vault | Evidence Matcher |
| `parsed-jd.schema.json` | JD Parser | Evidence Matcher |
| `evidence-match.schema.json` | Evidence Matcher | Resume Selector |
| `resume-claim.schema.json` | Resume Selector | Claim Validator |
| `claim-verification.schema.json` | Claim Validator | Risk Check and UI |
| `risk-result.schema.json` | Risk Check | Human Confirmation and UI |
| `error.schema.json` | Every service | UI, logs, and tests |

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

The response contains `parsed_jd`, `evidence_match`, `resume_claims`, `claim_verification`, `ats_form_mapping`, `risk_result`, `human_confirmation`, `audit_record`, and the nine-step `step_trace`.

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

Backward-compatible fields may be added after A's handoff. Renaming or removing a field requires a versioned contract and coordinated updates across producers, consumers, examples, diagrams, and tests.

