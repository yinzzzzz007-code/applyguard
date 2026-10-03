# ApplyGuard proposal foundation

ApplyGuard helps senior undergraduates and postgraduates in concentrated software, AI, or data job searches tailor applications from evidence they can inspect. Its C-stage workflow can parse a supplied JD, match and select evidence, verify each selected claim, assess risk, and stop for human review with an audit record.

The repository remains a proposal scaffold: the Vault is fictional JSON data and ATS mapping is a fixed simulator fixture.

## Run

Requirements: Python 3.11 or later and `jsonschema`:

```sh
python -m pip install -r requirements.txt
```

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

To parse the submitted JD offline, add `"parse_mode": "offline"` to the request JSON. This runs the rule fallback and C verification. With `APPLYGUARD_AI_API_KEY` in the process environment, the endpoint uses the model path by default; `parse_mode: "fixture"` retains the original A/B fixed demo. The dynamic response reports `component_modes.jd_parser` as `MODEL`, `MODEL_SPAN_REPAIRED`, or `RULE_FALLBACK`, and `component_modes.ats_form_mapper` as `FIXTURE`. A model failure retries once, then falls back or returns a safe-stop validation error. The key is never needed for offline tests.

On macOS/Linux, a dynamic request can be sent with:

```sh
curl -sS http://127.0.0.1:8000/api/v1/workflow/mock -H 'Content-Type: application/json' \
  -d '{"candidate_id":"cand_demo_001","jd_text":"Software Engineering Intern requires Python HTTP APIs, automated tests, and Git.","parse_mode":"offline"}'
```

The low-cost demo defaults to `gpt-4o-mini` and 2048 maximum output tokens per attempt. These are temporary defaults: set `APPLYGUARD_AI_MODEL` to a provider-supported stronger model and `APPLYGUARD_AI_MAX_TOKENS` to a suitable value (1–16384) when quality needs justify the additional cost. Authentication/configuration failures do not retry; transient or invalid output failures retry at most once. Set `APPLYGUARD_AI_BASE_URL` for the compatible provider. Confirm the chosen provider supports chat completions, JSON object response format, and `max_tokens`; rerun quality evaluation after changing models. `parse_mode: "offline"` guarantees zero API calls even if a key exists; `dynamic` enables model calls when a key exists. Keep the key in a shell environment or ignored `.env`, not in tracked files. This service reads process environment variables; it does not load `.env` automatically.

## Test

```powershell
python -m unittest discover -s tests -v
python -m eval.c_benchmark
python -m demo.run_c_cases
```

`python -m eval.c_benchmark --model` opts into paid model calls for ten fictional JDs. See `docs/ai-evaluation-C.md` for the measured offline results and limits.

## B deterministic proposal baseline

The B-owned modules are runnable, deterministic, and fixture-backed:

- `data/career-vault.seed.json` stores four wholly fictional experiences with claims, metrics, evidence sources, confidence, and verification states.
- `backend/services/career_vault.py` provides a JSON repository boundary that can later be replaced by PostgreSQL + pgvector.
- `backend/services/evidence_matcher.py` ranks term and responsibility overlap, verification, confidence, metrics, conflicts, and missing evidence with an explanation and evidence IDs.
- `backend/services/resume_selector.py` selects only strong, conflict-free, evidence-backed claims under deterministic count, length, and redundancy constraints. Its count-limit step adapts the retained Apache-2.0 Resume Matcher bullet selector; see `THIRD_PARTY_NOTICES.md`.
- `data/benchmarks/fixed-jd-benchmark.json` contains five fictional fixed JD cases. It is a test set, not an evaluation result.

The default no-key, no-`parse_mode` request preserves the original A/B fixture response for existing consumers. Dynamic requests compute C's Parser, Claim Validator, and Risk Check while keeping B's services unchanged. ATS mapping remains D's fixed fixture.

For B-specific verification, run the standard test command above. See [B_TO_C_HANDOFF.md](B_TO_C_HANDOFF.md) for integration details and the [Proposal formative-study kit](docs/user-study/README.md) for the released questionnaire, interview guide, privacy/photo consent, and evidence templates. No participant results are included.

Career Vault also checks optional structured Metric arithmetic when a fictional experience supplies a complete `calculation` object; existing Metrics without one remain valid. This is an ingestion check, not final Claim validation. See [third-party notices](THIRD_PARTY_NOTICES.md) for the retained ASu Resume Skills implementation and MIT license.

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

- `backend/`: runnable HTTP service, B/C services, and routed mock workflow
- `frontend/`: lightweight demonstration page
- `contracts/`: versioned JSON Schema contracts for the evidence, skill, mapping, risk, and audit boundaries
- `data/`: fictional seed data, fixed outputs, and the five-case Benchmark
- `tests/`: standard-library API and workflow tests
- `docs/`: proposal scope, architecture, interface, and module ownership
- `demo/`: a fixed request and a PowerShell demo command
- `presentation/`: editable proposal presentation source and final PPTX

The complete target architecture and the scaffold-to-final migration boundary are documented in `docs/architecture.md`. The A handoff contract and known limitations are documented in [HANDOFF.md](HANDOFF.md); B's handoff to C is in [B_TO_C_HANDOFF.md](B_TO_C_HANDOFF.md).

## C acceptance audit

See [the requirement-by-requirement audit](docs/C-requirements-audit.md), [C to D handoff](C_TO_D_HANDOFF.md), and [offline measured results](eval/results/c-offline-audit.json). The three-case demo always runs offline, including when an API key exists.
