# ApplyGuard proposal scope

Version: `proposal-v0.1-foundation`  
Scope owner: Member A  
Status: Frozen for the 3 October foundation review

## Target user

The primary user is a university student or recent graduate applying for internships and entry-level software roles. The user has real project, course, volunteer, or internship experience but finds it difficult to select relevant evidence, write concise claims, and transfer the same information into an applicant tracking system without exaggeration or inconsistency.

## Problem statement

Job applicants repeatedly translate unstructured experience into job-specific resume claims and application fields. General writing assistants can improve phrasing but may introduce unsupported statements, lose the link to source evidence, or hide uncertainty. Applicants need a workflow that keeps every important claim traceable, blocks unsupported content, and returns control before any high-risk action.

## Specific user need

The user needs to reuse verified experience across applications while seeing why each experience was selected, which evidence supports each claim, and which fields still require manual confirmation.

## Core user stories

1. As an applicant, I want to store a verified experience once so that I can reuse it without rewriting or overstating it.
2. As an applicant, I want the system to match a job description to evidence-backed experience so that I can understand why content is selected.
3. As an applicant, I want unsupported claims and risky ATS fields to stop at a confirmation gate so that I remain responsible for the final application.

## Complete main workflow

Career Vault → JD Parser → Evidence Matcher → Resume Selector → Claim Validator → ATS Form Mapper → Risk Check → Human Confirmation → Audit Record

The proposal demo ends at a prepared draft. ApplyGuard does not submit an application.

## Priority scope

### P0: proposal foundation

- Freeze module names, JSON fields, error format, and handoff rules.
- Run `GET /health` and one deterministic mock workflow.
- Provide fictional Career Vault data and fixed workflow output.
- Show evidence IDs for every selected resume claim.
- Show one risk and require human confirmation.
- Provide architecture, workflow, sequence, and module ownership documentation.
- Provide tests, setup instructions, and an editable English presentation skeleton.

### P1: proposal demonstration and final-project baseline

- Implement simplified Career Vault storage and CRUD.
- Parse skills, experience, education, and responsibilities into fixed JSON.
- Implement baseline evidence scoring and explanation.
- Select resume content under length and evidence constraints.
- Validate claims and block unsupported content.
- Map fields into a simulated ATS page.
- Record audit events and abnormal cases.
- Run formative user research before the proposal and task-based usability testing after it.

### P2: optional extensions

- Browser extension for a selected job portal.
- Multiple resume variants and multi-objective optimization.
- Broader benchmarks, multilingual support, and additional model providers.
- Learning from user corrections.

## Non-goals

- Submitting an application without explicit user confirmation.
- Inventing or strengthening experience beyond stored evidence.
- Supporting every ATS or job portal in the proposal stage.
- Building a production identity-verification system.
- Using real teammate resumes, names, phone numbers, or other unnecessary personal data in the demo.
- Claiming measured accuracy before the benchmark and user study are complete.

## Proposal success criteria

These are planned acceptance targets, not completed-study results.

| Area | Proposal acceptance target |
| --- | --- |
| Runnable foundation | Health check and mock workflow return valid JSON locally |
| Traceability | Every selected claim contains at least one evidence ID |
| User control | The workflow stops at human confirmation before submission |
| Error handling | Invalid input returns the unified error envelope |
| Architecture | Diagrams and module ownership use the same frozen module names |
| Contracts | Seven JSON Schemas and their examples remain mutually consistent |
| Tests | Health, happy path, invalid request, and unknown route pass |
| Research readiness | B can map study findings to requirements without redesigning the workflow |

## Feasibility boundary

The foundation uses deterministic examples and a simulated ATS page. Later members can replace the parser, matcher, validator, and storage independently because each module exchanges frozen JSON objects. The final project will evaluate normal use, unsupported claims, malformed model output, timeouts, and user correction.

## Proposal requirement crosswalk

| Course requirement | ApplyGuard evidence |
| --- | --- |
| Problem, users, and specific need | Sections above and slides 2-3 |
| Related work and gap | Slide 4; evidence traceability and human confirmation are the project gap |
| 2-3 user stories and one workflow | Three stories and the nine-step workflow |
| Technology, data, and AI role | Architecture and interface documents; slide 8 |
| Risks, mitigation, and tests | Risk result, unified errors, tests, and slide 9 |
| Team roles and work plan | Module ownership table and slide 10 |
| Clear architecture or workflow diagram | `docs/diagrams/architecture.*` and `workflow.*` |
| English presentation | `presentation/applyguard-proposal-foundation-final.pptx` |

## Open clarification

The kickoff PDF states “one proposal slide per team,” while the team plan defines an eleven-part presentation structure. The foundation preserves the team structure and flags this wording for confirmation with the instructor before final submission.
