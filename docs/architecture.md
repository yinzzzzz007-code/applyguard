# Architecture and workflow

## Architecture diagram

![ApplyGuard architecture](diagrams/architecture.svg)

## Workflow diagram

![ApplyGuard workflow](diagrams/workflow.svg)

## Core sequence diagram

![ApplyGuard core sequence](diagrams/sequence.svg)

## Module responsibilities

| Module | Responsibility | Input | Output | Owner after A handoff |
| --- | --- | --- | --- | --- |
| Career Vault | Store fictional or user-approved experience, claims, skills, metrics, and evidence sources | Experience edits | Experience JSON | B |
| JD Parser | Extract hard and preferred requirements while retaining source evidence text | JD text | Parsed JD JSON | C |
| Evidence Matcher | Score relevant experiences and explain evidence strength or conflicts | Parsed JD + Experience | Evidence Match JSON | B |
| Resume Selector | Choose and order evidence-backed claims under length constraints | Evidence Match | Resume Claim JSON | B |
| Claim Validator | Check whether every statement is supported and block unsupported fragments | Resume Claim + evidence | Claim Verification JSON | C |
| ATS Form Mapper | Map approved content into simulated application fields and expose missing fields | Verified claims | Field map | D |
| Risk Check | Convert unsupported claims, conflicts, missing fields, and privacy issues into visible risks | Verification + field map | Risk Result JSON | C |
| Human Confirmation | Let the user confirm, edit, or cancel before any submission | Risk Result + draft | User decision | D |
| Audit Record | Record the trace, decisions, and outcome for inspection | Workflow events | Audit record | A |

## Control boundaries

- Deterministic code handles field validation, scores, state transitions, and the confirmation gate.
- AI components may parse or draft content, but they cannot bypass contract validation or user confirmation.
- The proposal demonstration uses fictional data and ends before external submission.
- Every module logs a trace ID so a failure can be connected to its input and output.

