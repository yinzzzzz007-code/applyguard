# ApplyGuard proposal scope

Version: `proposal-v0.1-foundation`  
Scope owner: Member A  
Status: Frozen for the 3 October foundation review

## Target user

The primary user is a senior undergraduate or postgraduate in a concentrated technology-job or internship application period, especially in software engineering, AI, or data roles. The user reviews or applies to at least five positions per week, has at least three substantial project, research, competition, or internship experiences, and repeatedly tailors resumes and completes applicant tracking system forms.

This definition is the recruitment criterion for the formative user study. Broader groups such as all students, all recent graduates, or applicants in unrelated fields are outside the primary sample unless the team records them separately as exploratory participants.

## Problem statement

Job applicants repeatedly translate unstructured experience into job-specific resume claims and application fields. General writing assistants can improve phrasing but may introduce unsupported statements, lose the link to source evidence, or hide uncertainty. Applicants need a workflow that keeps every important claim traceable, blocks unsupported content, and returns control before any high-risk action.

## Specific user need

The user needs to reuse verified experience across applications while seeing why each experience was selected, which evidence supports each claim, and which fields still require manual confirmation.

## Core user stories

1. As an applicant, I want to store a verified experience once so that I can reuse it without rewriting or overstating it.
2. As an applicant, I want the system to match a job description to evidence-backed experience so that I can understand why content is selected.
3. As an applicant, I want unsupported claims and risky ATS fields to stop at a confirmation gate so that I remain responsible for the final application.

## Complete user journey

1. Build and maintain a Career Evidence Vault.
2. Save one target job description.
3. Extract hard requirements, preferred requirements, responsibilities, and their source text.
4. Match each requirement to real evidence.
5. Select, reorder, and tailor resume claims under length and evidence constraints.
6. Verify every claim and expose unsupported fragments.
7. Open the selected ATS page or the proposal-stage ATS simulator.
8. Scan and map ATS fields.
9. Classify each action as safe to fill, requiring confirmation, or blocked.
10. Run a final consistency check across evidence, resume claims, and ATS fields.
11. Let the applicant edit, confirm, cancel, and submit manually.
12. Save the application version, decisions, and audit trace.

ApplyGuard never performs the final submission automatically.

## Internal system pipeline

Career Vault → JD Parser → Evidence Matcher → Resume Selector → Claim Validator → ATS Form Mapper → Risk Check → Human Confirmation → Audit Record

The nine modules are an implementation view of the twelve-step user journey. JD Parser covers steps 2-3. Resume Selector covers step 5. ATS Form Mapper covers steps 7-8. Risk Check and Human Confirmation cover steps 9-11. Audit Record covers step 12. The final consistency check runs between Risk Check and Human Confirmation rather than becoming a separate service.

The proposal demo ends at a prepared draft and confirmation gate. The final project retains the complete user journey, including manual user submission and version storage.

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

- Implement a simplified Career Evidence Graph and Career Vault storage.
- Parse skills, experience, education, and responsibilities into fixed JSON.
- Implement baseline evidence scoring and explanation.
- Select resume content under length and evidence constraints and explain both selection and removal.
- Validate claims and block unsupported content.
- Route specialized skills through schema validation, semantic validation, retry, and deterministic fallback.
- Map fields into a simulated ATS page for the proposal and one limited ATS environment for the final project.
- Record audit events and abnormal cases.
- Evaluate whether to fork or integrate the Resume Matcher foundation before replacing the proposal scaffold.
- Run formative user research before the proposal and task-based usability testing after it.

### P2: optional extensions

- Support for additional ATS platforms beyond the single final-project target.
- Multiple resume variants and multi-objective optimization.
- Broader benchmarks, multilingual support, and additional model providers.
- Learning from user corrections.

## Non-goals

- Submitting an application without explicit user confirmation.
- Inventing or strengthening experience beyond stored evidence.
- Supporting every ATS or job portal in the proposal stage.
- Treating the fixed proposal mock as the final parsing or matching implementation.
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
| Contracts | Nine JSON Schemas and their examples remain mutually consistent |
| Tests | Health, happy path, invalid request, and unknown route pass |
| Research readiness | B can map study findings to requirements without redesigning the workflow |

## Feasibility boundary

The foundation uses deterministic examples and a simulated ATS page. It validates the workflow and contracts; it is not the final technology stack. The target architecture retains the Workflow Orchestrator, Skill Router, specialized skills, Career Evidence Graph, contract and semantic validators, retry/fallback path, ATS scanner, human review, and versioned audit record. Later members can replace module internals behind versioned contracts. The final project will evaluate normal use, unsupported claims, malformed model output, timeouts, and user correction.

## Proposal requirement crosswalk

| Course requirement | ApplyGuard evidence |
| --- | --- |
| Problem, users, and specific need | Sections above and slides 2-3 |
| Related work and gap | Slide 4; evidence traceability and human confirmation are the project gap |
| 2-3 user stories and one workflow | Three stories, the twelve-step user journey, and its nine-module pipeline mapping |
| Technology, data, and AI role | Architecture and interface documents; slide 8 |
| Risks, mitigation, and tests | Risk result, unified errors, tests, and slide 9 |
| Team roles and work plan | Module ownership table and slide 10 |
| Clear architecture or workflow diagram | `docs/diagrams/architecture.*` and `workflow.*` |
| English presentation | `presentation/applyguard-proposal-foundation-v1.1.1-final.pptx` |

## Open clarification

The kickoff PDF states “one proposal slide per team,” while the team plan defines an eleven-part presentation structure. The foundation preserves the team structure and flags this wording for confirmation with the instructor before final submission.
