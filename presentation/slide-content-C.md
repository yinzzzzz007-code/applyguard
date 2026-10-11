# C slide content — AI, verification, risk, evaluation

## AI location and control

JD text → model-assisted requirement extraction → JSON Schema and source-span checks → B evidence matching/selection → C claim-level verification → C risk decision → human review. The model only proposes JD facts. It does not make the final truth or submit decision.

## Failure handling

Malformed JSON, invalid schema, invented terms, missing source quotes, and timeout trigger one retry. After failure, a deterministic parser identifies explicit technical terms from this JD and labels its output `RULE_FALLBACK`. If it cannot find a reliable requirement, the workflow stops with a traced 422 error and audit event.

## Claim example

Vault: “Built a Python HTTP API and added automated tests for core routes.” Linked to fictional repository and test-report evidence. Result: `VERIFIED` for unchanged wording. Candidate claim: “Owned the entire production API and used CUDA.” Result: `BLOCKED`; fragments include `Owned`, `entire`, `production`, `CUDA`. The interface should show missing support and offer edit/remove/add evidence.

## Risk → control → evidence

| Risk | Control | Demonstration evidence |
| --- | --- | --- |
| Unsupported claim | BLOCK; correction and re-verification | Claim result, unsupported fragments, blocked Risk Result |
| Unverified source or wording ambiguity | Human review | `NEEDS_REVIEW`, source links and explanation |
| Missing work authorization | Ask user, never guess | `MISSING_FIELD` risk |
| Sensitive field | Explicit confirmation | `PRIVACY` risk |
| Model failure | Retry, marked fallback or safe stop | `step_trace` mode and error audit |

## Measured fictional regression baseline

10 fictional JDs, 40 claim variants. Offline JD term precision/recall: 0.973/0.973. Historical pre-audit model-assisted term precision/recall (not rerun after fixes): 0.9474/0.9730, with 7/10 model quotes repaired from actual JD spans. Claim state accuracy: 40/40; unsupported block rate: 28/28. These are authored technical tests, not measured performance on real candidates or independent JDs.


## Acceptance demonstration and cost

`python -m demo.run_c_cases` runs three zero-call cases: normal proposal awaiting human review, unsupported CUDA claim blocked, and simulated model timeout with deterministic fallback. Low-cost test defaults: `gpt-4o-mini`, 2048 maximum output tokens per attempt; both configurable for supported models; at most one retry. Current full regression: 76 tests, including unchanged A/B tests. Field-level L0/L1/L2/L3 controls are exposed for D; aggregate LOW/MEDIUM/HIGH/BLOCK has a separate meaning. ATS mapping is still a fixture and audit records are not persisted. Do not label this a deployed complete ATS product.
