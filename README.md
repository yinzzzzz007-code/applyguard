# ApplyGuard proposal foundation

ApplyGuard helps early-career job seekers tailor an application from evidence they can inspect. The proposal foundation implements one runnable, deterministic path from a job description to evidence matches, verified resume claims, a risk result, human confirmation, and an audit record.

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

## Frozen proposal workflow

1. Career Vault
2. JD Parser
3. Evidence Matcher
4. Resume Selector
5. Claim Validator
6. ATS Form Mapper
7. Risk Check
8. Human Confirmation
9. Audit Record

## Repository structure

- `backend/`: runnable HTTP service and deterministic mock workflow
- `frontend/`: lightweight demonstration page
- `contracts/`: frozen JSON Schema contracts
- `data/`: fictional seed data and fixed example outputs
- `tests/`: standard-library API and workflow tests
- `docs/`: proposal scope, architecture, interface, and module ownership
- `demo/`: a fixed request and a PowerShell demo command
- `presentation/`: editable proposal presentation source and final PPTX

The handoff contract and known limitations are documented in [HANDOFF.md](HANDOFF.md).

