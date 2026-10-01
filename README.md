# ApplyGuard proposal foundation

ApplyGuard helps senior undergraduates and postgraduates in concentrated software, AI, or data job searches tailor applications from evidence they can inspect. The proposal foundation implements one runnable, deterministic contract path from a fixed job-description fixture to evidence matches, verified resume claims, a risk result, human confirmation, and a versioned audit record.

The repository is a proposal scaffold. It preserves the target architecture and contracts but does not yet implement dynamic JD parsing, a production Career Evidence Graph, a real ATS scanner, or a model provider.

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

- `backend/`: runnable HTTP service and deterministic mock workflow
- `frontend/`: lightweight demonstration page
- `contracts/`: versioned JSON Schema contracts for the evidence, skill, mapping, risk, and audit boundaries
- `data/`: fictional seed data and fixed example outputs
- `tests/`: standard-library API and workflow tests
- `docs/`: proposal scope, architecture, interface, and module ownership
- `demo/`: a fixed request and a PowerShell demo command
- `presentation/`: editable proposal presentation source and final PPTX

The complete target architecture and the scaffold-to-final migration boundary are documented in `docs/architecture.md`. The handoff contract and known limitations are documented in [HANDOFF.md](HANDOFF.md).
