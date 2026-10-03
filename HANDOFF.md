# Project handoff — C implementation ready for review

## Version

C delivery branch based on B `64cae15`; release label: `proposal-v0.3-ai-core`. A foundation history: `proposal-v0.1-foundation`

## What is frozen

- The selected ApplyGuard topic remains the design source of truth.
- The twelve-step user journey and its mapping to the nine-module internal pipeline.
- Target architecture boundaries: Workflow Orchestrator, Skill Router, specialized skills, validators, Career Evidence Graph, ATS scanner/mapper, human review, and versioned audit.
- Endpoint paths: `GET /health` and `POST /api/v1/workflow/mock`.
- Contract filenames and top-level field names in `contracts/`, including form mapping and audit record.
- Unified error envelope: `error.code`, `error.message`, `error.details`, and `error.trace_id`.
- Fictional identifiers and evidence links in `data/`.

Any breaking change requires a short architecture decision note and updates to contracts, examples, tests, diagrams, and the presentation.

## What works now

- A standard-library HTTP service; C contract validation additionally requires `jsonschema`.
- A browser demo page.
- A deterministic mock workflow that returns evidence matches, selected claims, verification results, a risk result, a human-confirmation gate, and an audit record.
- Health, happy-path, invalid-request, and not-found tests.
- Frozen JSON Schemas and fixed seed data.
- Proposal scope, complete user journey, target architecture, internal workflow, sequence, module responsibilities, and presentation skeleton.

## B implementation status

B completed the deterministic Career Vault, Evidence Matcher, constrained Resume Selector, five-case fictional Benchmark, and unit tests without breaking the frozen endpoint, step trace, confirmation gate, or audit record. `B_TO_C_HANDOFF.md` records the service interfaces, compatibility extensions, and C integration checklist.

The formative user-study package is ready in `docs/user-study/`, but no participants, results, statistics, quotes, or conclusions have been fabricated. Collection and the resulting traceability matrix remain a real-world team activity.

## Run and verify before handoff

```powershell
python -m unittest discover -s tests -v
python -m backend.app
```

Then verify:

- `GET http://127.0.0.1:8000/health` returns `status: ok`.
- `POST http://127.0.0.1:8000/api/v1/workflow/mock` with `demo/workflow-request.json` returns `AWAITING_HUMAN_CONFIRMATION`.
- Every resume claim has at least one `evidence_id`.
- The risk result identifies unsupported claims and requests confirmation when needed.

## C implementation status

JD Parser, model transport, prompt, schema/source checks, bounded retry, fallback/safe stop, Claim Validator, Risk Engine and nine-step Router are implemented. Three offline demos and the 10-JD/40-claim benchmark are runnable. See `docs/C-requirements-audit.md` for the itemized audit, test evidence, and known limits; `C_TO_D_HANDOFF.md` specifies D integration.

Install `requirements.txt` before running the commands above. Use `parse_mode: "offline"` to exercise C without spending API credits; the no-key/no-mode request retains the old A/B fixture for compatibility. The current low-cost demo defaults to `gpt-4o-mini` and 2048 maximum output tokens; both can be changed through `APPLYGUARD_AI_MODEL` and `APPLYGUARD_AI_MAX_TOKENS` after checking provider compatibility and cost.

## Known limitations and ownership

- B Vault and evidence are fictional read-only JSON, not external truth verification.
- D ATS mapping remains a simulator fixture; final review UI, actual fill, and task-based usability study belong to D.
- A/B application version and audit persistence remain future integration; C returns an in-memory audit record.
- Rule fallback is conservative and dictionary-limited; semantic checks do not cover every natural-language paraphrase or mixed negation. Ambiguous rewording requires review.
- Real formative-study failure cases await B's collection, then A requirement confirmation and C regression additions.
- The server remains proposal scaffolding. No application is automatically submitted.
- C is published separately from main/B; A can review and merge it for final integration.
