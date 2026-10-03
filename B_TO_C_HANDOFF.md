# B-to-C handoff: evidence foundation

## Completed B baseline

- Career Vault: `backend/services/career_vault.py` loads four wholly fictional, structured experiences from `data/career-vault.seed.json`. It keeps experience, claim, metric, evidence, confidence, and verification links; JSON storage is behind `CareerVaultRepository` for future PostgreSQL + pgvector replacement. An optional structured Metric calculation is checked on ingestion by a directly copied ASu Resume Skills arithmetic helper (MIT attribution in `THIRD_PARTY_NOTICES.md`).
- Evidence Matcher: `backend/services/evidence_matcher.py` deterministically scores normalized requirement terms, responsibility text, verification state, source confidence, metrics, conflicts, and missing evidence. Each match exposes `experience_id`, `claim_ids`, `evidence_ids`, rationale, conflicts, missing evidence, score breakdown, and `ready_for_selection`.
- Resume Selector: `backend/services/resume_selector.py` emits contract-valid selected claims only when strong, conflict-free evidence exists. Its Claim-count adapter calls the retained Apache-2.0 Resume Matcher bullet selector; the upstream source, commit, and license are in `THIRD_PARTY_NOTICES.md`. It records unselected claims as low relevance, insufficient evidence, conflict, redundancy, count limit, or length limit.
- Benchmark: `data/benchmarks/fixed-jd-benchmark.json` holds five fictional cases: Python backend, full stack, ML, data engineering, and intentionally unmatched embedded systems.
- Tests: `tests/test_member_b.py` covers Vault retrieval, ranking, traceability, insufficient/conflicting evidence, deduplication, budgets, determinism, all Benchmarks, and Schema conformance.

## Frozen integration surface for C

- Keep all nine module names and `GET /health` / `POST /api/v1/workflow/mock` unchanged.
- `EvidenceMatcher.match(parsed_jd, experiences)` accepts `parsed-jd.schema.json` data and returns `evidence-match.schema.json` data plus only documented optional B fields.
- `ResumeSelector.select(evidence_match, experiences, application_id, max_claims=..., max_characters=...)` returns `SelectionResult.claims`; every claim meets `resume-claim.schema.json` and includes nonempty `evidence_ids` and `requirement_ids`.
- `ready_for_selection == false`, nonempty `conflicts`, or nonempty `missing_evidence` are B's explicit boundary signals for C. C should validate claim-level wording independently and must not turn an uncovered requirement into a supported claim.
- `resume_selection.removed_claims` in the mock response is an audit aid, not a Claim Validator result.

## Current mock boundary

The mock endpoint runs B's Vault, matcher, and selector. It deliberately reads `data/parsed-jd.example.json`; user-supplied `jd_text` is only validated for length. C may replace this fixture with its JD Parser result behind the same parsed-JD contract. C's Claim Validator fixture remains untouched, as do D's form-mapping and human-review fixtures.

## Known limits

- Matching is transparent keyword/topic logic, not embeddings, LLM ranking, multilingual matching, or measured accuracy.
- A skill listed on an experience is insufficient by itself: a linked Claim must actually state the requirement. The backend benchmark intentionally leaves Git uncovered because no Claim states it. Metrics improve ranking when linked but are not mandatory evidence.
- JSON storage is read-only proposal seed data, not production CRUD or a database migration.
- The arithmetic helper checks only supplied numeric relationships (ratio, relative change, percentage-point change). It does not infer missing inputs, authenticate sources, compare free-text `value` to the calculation, or validate generated Claim wording; those remain separate C/production concerns.
- The endpoint uses a one-claim demo budget to retain the original fixed Claim Validator fixture. The selector itself supports configurable budgets.
- `verification_status` is evidence metadata, not final Claim Validator authority.
- The formative-study package contains only recruitment, consent, collection, coding, traceability, and preliminary-results templates. No participant response or result exists yet.

## C checklist

1. Produce valid parsed-JD objects with source text and normalized terms.
2. Preserve B evidence IDs when validating generated or selected claims.
3. Convert unsupported fragments, conflicts, and missing-evidence signals into Claim Validator / Risk Check states and failure tests.
4. Do not change B schemas or module names without a versioned, coordinated contract decision.

## Authorized Plan-Then-Execute option

The team reports author permission to copy `RichardHGL/CHI2025_Plan-then-Execute_LLMAgent`. Its checked-out reference is outside this repository at `E:\软件工程\upstream-references\Plan-Then-Execute`. The reusable `Plan` / `Step` schema and Planner/Executor code depend on LangChain and Flask, so B deliberately does not vendor it into the standard-library Career Vault, Matcher, or Selector. C/D may reuse it for the Plan → Human Review → Execute path after recording the permission and exact upstream commit with their implementation.
