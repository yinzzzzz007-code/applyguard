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

## B's next work package

1. Replace file-backed fictional data with the simplified Career Evidence Graph and Career Vault.
2. Keep `experience.schema.json` compatible while adding storage and retrieval.
3. Replace fixed evidence matches with a baseline scoring implementation.
4. Add unit tests for matching scores, evidence strength, conflicts, and insufficient evidence.
5. Prepare five fixed JDs and the matching benchmark dataset.
6. Run the formative user study defined in the team plan and provide the traceability matrix.
7. Implement the constrained-selection baseline and record why each claim was selected or removed.

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

- JD parsing and evidence matching are deterministic proposal mocks.
- Data is fictional and stored as JSON.
- The ATS page is simulated rather than connected to a real job portal.
- No application is submitted automatically.
- The AI provider boundary exists only in the architecture and interface plan.
- The current standard-library server is disposable scaffolding. A must record the Resume Matcher compatibility decision before the team adopts a final framework.
- The final project still requires the Skill Router, semantic validator, retry/fallback behavior, Career Evidence Graph storage, and one limited ATS target.
