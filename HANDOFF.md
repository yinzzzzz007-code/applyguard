# A-to-B handoff

## Version

`proposal-v0.1-foundation`

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

- A dependency-free local HTTP service.
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

## Known limitations

- JD parsing remains a fixed fixture; evidence matching is a computed deterministic proposal baseline, not a semantic model.
- Data is fictional and stored as JSON.
- The ATS page is simulated rather than connected to a real job portal.
- No application is submitted automatically.
- The AI provider boundary exists only in the architecture and interface plan.
- The current standard-library server is disposable scaffolding. A must record the Resume Matcher compatibility decision before the team adopts a final framework.
- The final project still requires the Skill Router, semantic validator, retry/fallback behavior, Career Evidence Graph storage, and one limited ATS target.
