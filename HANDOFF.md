# A-to-B handoff

## Version

`proposal-v0.1-foundation`

## What is frozen

- Module names and order in the nine-step proposal workflow.
- Endpoint paths: `GET /health` and `POST /api/v1/workflow/mock`.
- Contract filenames and top-level field names in `contracts/`.
- Unified error envelope: `error.code`, `error.message`, `error.details`, and `error.trace_id`.
- Fictional identifiers and evidence links in `data/`.

Any breaking change requires a short architecture decision note and updates to contracts, examples, tests, diagrams, and the presentation.

## What works now

- A dependency-free local HTTP service.
- A browser demo page.
- A deterministic mock workflow that returns evidence matches, selected claims, verification results, a risk result, a human-confirmation gate, and an audit record.
- Health, happy-path, invalid-request, and not-found tests.
- Frozen JSON Schemas and fixed seed data.
- Proposal scope, architecture, workflow, sequence, module responsibilities, and presentation skeleton.

## B's next work package

1. Replace file-backed fictional data with the simplified Career Vault.
2. Keep `experience.schema.json` compatible while adding storage and retrieval.
3. Replace fixed evidence matches with a baseline scoring implementation.
4. Add unit tests for matching scores, evidence strength, conflicts, and insufficient evidence.
5. Prepare five fixed JDs and the matching benchmark dataset.
6. Run the formative user study defined in the team plan and provide the traceability matrix.

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

