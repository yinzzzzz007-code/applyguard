# C AI and failure evaluation — proposal baseline

Dataset: `eval/c_cases.json`, entirely fictional. It contains ten JDs and forty claim variants from four fictional Vault claims. The variants deliberately include unchanged, reworded, ownership inflation, production/delivery inflation, invented technologies, metrics, and dates. They share source claims and rule vocabulary; results are functional regression evidence, **not** independent generalization estimates or participant findings.

Command: `python -m eval.c_benchmark` with Python 3.11+ and `requirements.txt` installed. The measured offline run on 2026-10-03 produced:

| Measure | Result | Denominator / interpretation |
| --- | ---: | --- |
| JD term precision | 0.9730 | Extracted terms against fictional labels; conservative rule fallback |
| JD term recall | 0.9730 | Labelled terms across 10 JDs |
| Claim state accuracy | 1.0000 | 40 authored expected state labels |
| Grounded Claim Rate | 0.1000 | 4 `VERIFIED` outputs / 40 deliberately mixed claims |
| Unsupported Claim Block Rate | 1.0000 | 28 `BLOCKED` outputs / 28 authored unsupported variants |

The remaining eight claim variants require review. Grounded Claim Rate is low by dataset design: most cases are adversarial. Precision/recall count terms, not hard/preferred classification or span quality; the unit tests separately check exact `evidence_text` substrings and fabricated term rejection.

Historical live snapshot, before the subsequent acceptance-audit fixes (not rerun after them): the same ten fictional JDs were run through the configured ChatAnywhere-compatible API (`APPLYGUARD_AI_MODEL=gpt-4o-mini`) on 2026-10-03. Final measured term precision was **0.9474** and recall **0.9730**. All ten returned model-derived Parsed JDs, with **seven source quotes repaired from exact JD spans** and no fallback or safe stop on that run. Quote repair lowers per-requirement confidence to at most 0.7; the mode is reported as `MODEL_SPAN_REPAIRED`, not hidden as an exact model quote. A prior run before the repair had only 2/10 model outputs accepted, which led to the repair. The model run is small and provider output can vary; it is not a production accuracy estimate.

Failure coverage in `tests/test_member_c.py`: invented skill and source quote, malformed model output, timeout, retry and fallback, prompt injection, unparseable JD safe stop and audit, foreign/missing evidence, unverified/conflicting evidence, role/scope/delivery/skill/metric inflation, sensitive or missing ATS fields, nine distinct trace steps, and no automatic submission. A/B's 29 tests remain the regression gate.

The source evidence is fictional metadata. Claim validation is intentionally conservative: unchanged, candidate-owned and fully verified Vault text can pass; changed wording needs review unless a known critical fragment is unsupported, in which case it is blocked. It does not establish external truth, handle all possible natural-language paraphrases, or replace human review. When B provides real anonymized study findings, add those failure examples as separately labelled cases before updating any reported metrics.

Per-field controls are separate from aggregate risk. `field_controls` distinguishes L0 ordinary, L1 evidence-backed with source display, L2 ambiguous, and L3 sensitive/blocked. Aggregate risk behaves as follows: `LOW` permits a low-risk field suggestion; `MEDIUM` shows source or asks for confirmation; `HIGH` requires explicit confirmation of sensitive fields; `BLOCK` prevents normal filling when evidence or mapping has a hard conflict. These are field/workflow controls, never permission to submit an application.


## Acceptance-audit rerun, 2026-10-03

The current offline result is committed as a reviewable file at `eval/results/c-offline-audit.json` (working-tree artifact until Git approval). No paid provider calls were made during this audit. Offline term precision/recall remains 0.9730/0.9730. Confusion matrix: 4/4 expected VERIFIED accepted, 8/8 expected NEEDS_REVIEW sent to review, 28/28 expected BLOCKED blocked. Accepted-claim precision = 4/4; supported-claim acceptance = 4/4; false block rate among nonblocked labels = 0/12; review rate = 8/40. These denominators expose the adversarial composition; `grounded_claim_rate` alone is an output acceptance share, not factual accuracy.

`tests/test_c_audit.py` adds independently written edge cases for source grounding in Chinese and single-letter terms, negation/injection contexts, inherited preferred headings, skill/experience/education/responsibility categories, nonfinite numbers, unchanged claims with corrupted metrics, denominator/percentage-point mismatches, confidence/ownership, team/planning inflation, blocked sensitive fields, L0–L3 actions, downstream failure audit, and offline/budget transport. These are unit regressions, not a statistically independent evaluation set. JD Parsing Accuracy is reported as term precision/recall plus explicit category/source tests; there is no measured broad semantic accuracy for arbitrary JDs.

The fallback has a bounded vocabulary and can miss a positive clause sharing a negated sentence. Metric-to-text association is conservative when multiple metrics share evidence; ambiguous paraphrases may be blocked or sent for review. Structured metadata does not prove external truth. Final evaluation requires separately labelled unseen JDs, more supported paraphrases, and real anonymized failures supplied by B. Historical model numbers must not be presented as a new live result for the audited implementation.
