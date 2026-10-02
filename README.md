# ApplyGuard proposal foundation

ApplyGuard helps senior undergraduates and postgraduates in concentrated software, AI, or data job searches tailor applications from evidence they can inspect. The proposal foundation implements one runnable, deterministic contract path from a fixed job-description fixture to evidence matches, evidence-backed selected claims, a fixed claim-verification fixture, a risk result, human confirmation, and a versioned audit record.

The repository is a proposal scaffold. It preserves the target architecture and contracts but does not implement dynamic JD parsing, a production database, a real ATS scanner, or a model provider.

## Run

Requirements: Python 3.11 or later. The foundation uses only the Python standard library.

```powershell
python -m backend.app
```

Open `http://127.0.0.1:8000/` for the lightweight demo page.

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Mock workflow:

```powershell
$body = Get-Content -Raw demo/workflow-request.json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/workflow/mock -ContentType 'application/json' -Body $body
```

## Test

```powershell
python -m unittest discover -s tests -v
```

## B deterministic proposal baseline

The B-owned modules are runnable, deterministic, and fixture-backed:

- `data/career-vault.seed.json` stores four wholly fictional experiences with claims, metrics, evidence sources, confidence, and verification states.
- `backend/services/career_vault.py` provides a JSON repository boundary that can later be replaced by PostgreSQL + pgvector.
- `backend/services/evidence_matcher.py` ranks term and responsibility overlap, verification, confidence, metrics, conflicts, and missing evidence with an explanation and evidence IDs.
- `backend/services/resume_selector.py` selects only strong, conflict-free, evidence-backed claims under deterministic count, length, and redundancy constraints. Its count-limit step adapts the retained Apache-2.0 Resume Matcher bullet selector; see `THIRD_PARTY_NOTICES.md`.
- `data/benchmarks/fixed-jd-benchmark.json` contains five fictional fixed JD cases. It is a test set, not an evaluation result.

`POST /api/v1/workflow/mock` now computes its Career Vault, Evidence Matcher, and Resume Selector steps. It still uses `data/parsed-jd.example.json` because JD Parser belongs to C; it does **not** parse the submitted `jd_text`. Claim validation, ATS mapping, and risk output remain their frozen fixtures.

For B-specific verification, run the standard test command above. See [B_TO_C_HANDOFF.md](B_TO_C_HANDOFF.md) for integration details and `docs/user-study/` for formative-study materials.

## Frozen internal pipeline

1. Career Vault
2. JD Parser
3. Evidence Matcher
4. Resume Selector
5. Claim Validator
6. ATS Form Mapper
7. Risk Check
8. Human Confirmation
9. Audit Record

This nine-module pipeline implements the twelve-step user journey defined in `docs/proposal-scope.md`. The final project retains manual user submission, final consistency checking, and application-version storage. The system never submits automatically.

## Repository structure

- `backend/`: runnable HTTP service, B services, and deterministic mock workflow
- `frontend/`: lightweight demonstration page
- `contracts/`: versioned JSON Schema contracts for the evidence, skill, mapping, risk, and audit boundaries
- `data/`: fictional seed data, fixed outputs, and the five-case Benchmark
- `tests/`: standard-library API and workflow tests
- `docs/`: proposal scope, architecture, interface, and module ownership
- `demo/`: a fixed request and a PowerShell demo command
- `presentation/`: editable proposal presentation source and final PPTX

The complete target architecture and the scaffold-to-final migration boundary are documented in `docs/architecture.md`. The A handoff contract and known limitations are documented in [HANDOFF.md](HANDOFF.md); B's handoff to C is in [B_TO_C_HANDOFF.md](B_TO_C_HANDOFF.md).
