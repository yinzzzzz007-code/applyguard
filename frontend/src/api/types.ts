/**
 * UI-facing types aligned with ApplyGuard contracts (C proposal-v0.3-ai-core).
 * Pages should import from here only — not from obsolete SUPPORTED/NEEDS_CONFIRMATION enums.
 */

export type DemoScenario =
  | 'live'
  | 'prerecorded_block'
  | 'prerecorded_fallback'
  | 'error'

/** claim_verification.state */
export type ClaimState = 'VERIFIED' | 'NEEDS_REVIEW' | 'BLOCKED'

/** Local UI only: edited content is no longer treated as verified */
export type LocalClaimFreshness = 'as_returned' | 'edited_pending_reverify' | 'rejected'

/** field_controls.level */
export type FieldControlLevel = 'L0' | 'L1' | 'L2' | 'L3'

/** risk_result.risk_level */
export type AggregateRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'BLOCK'

export type FieldAction = 'SAFE_TO_FILL' | 'REQUIRES_CONFIRMATION' | 'BLOCKED'

export type WorkflowStatus = 'AWAITING_HUMAN_CONFIRMATION' | 'BLOCKED' | string

export interface ApiError {
  code: string
  message: string
  details?: unknown[]
  trace_id?: string
  retryable: boolean
}

export interface ApiResult<T> {
  data?: T
  error?: ApiError
  empty?: boolean
}

export interface VaultEvidence {
  evidence_id: string
  type?: string
  source_type?: string
  description: string
  source_reference?: string | null
  uri?: string | null
  confidence?: number
  verification_status?: string
}

export interface VaultExperience {
  experience_id: string
  title?: string
  organization: string
  role: string
  start_date: string
  end_date: string
  summary: string
  responsibilities?: string[]
  skills: string[]
  claims: Array<{
    claim_id: string
    text: string
    evidence_ids: string[]
    confidence?: number
    verification_state?: string
  }>
  evidence_sources: VaultEvidence[]
  verification_state?: string
}

export interface CareerVaultSeed {
  candidate_id: string
  profile: {
    display_name: string
    education: string
    consent: string
  }
  experiences: VaultExperience[]
  awards?: VaultAward[]
}

export interface VaultAward {
  award_id: string
  name: string
  issuer: string
  date: string
  description: string
}

/** Editable campus-resume form held in the frontend (no vault save API yet). */
export interface ResumeBasicInfo {
  name: string
  gender: string
  birthday: string
  ethnicity: string
  politics: string
  phone: string
  email: string
  idType: string
  idNo: string
  city: string
  hukou: string
}

export interface ResumeIntention {
  projectType: string
  expectRole: string
  expectCity: string
  availability: string
}

export interface ResumeEducation {
  id: string
  school: string
  degree: string
  major: string
  fullTime: string
  start: string
  end: string
  rank: string
}

export interface ResumeExperienceEntry {
  id: string
  organization: string
  title: string
  role: string
  start: string
  end: string
  description: string
  sourceExperienceId?: string
}

export interface ResumeAward {
  id: string
  name: string
  issuer: string
  date: string
  description: string
}

export interface ResumeExtras {
  skills: string
  awards: string
  summary: string
}

export interface ExtractedResumeForm {
  basic: ResumeBasicInfo
  intention: ResumeIntention
  education: Array<Omit<ResumeEducation, 'id'>>
  internships: Array<Omit<ResumeExperienceEntry, 'id' | 'sourceExperienceId'>>
  projects: Array<Omit<ResumeExperienceEntry, 'id' | 'sourceExperienceId'>>
  awards: Array<Omit<ResumeAward, 'id'>>
  extras: ResumeExtras
}

export interface ResumeParseResult {
  filename: string
  extractor: string
  notice: string
  char_count: number
  preview: string
  form: ExtractedResumeForm
}

export interface EditableResumeForm {
  candidateId: string
  basic: ResumeBasicInfo
  intention: ResumeIntention
  education: ResumeEducation[]
  internships: ResumeExperienceEntry[]
  projects: ResumeExperienceEntry[]
  awards: ResumeAward[]
  extras: ResumeExtras
  savedAt?: string
  dirty: boolean
}

export interface ParsedRequirement {
  requirement_id: string
  type: string
  category: string
  text: string
  normalized_terms?: string[]
  evidence_text: string
  confidence?: number
}

export interface ParsedJd {
  jd_id: string
  title: string
  company: string
  source_text: string
  requirements: ParsedRequirement[]
}

export interface EvidenceMatchItem {
  requirement_id: string
  experience_id: string
  claim_ids: string[]
  relevance_score: number
  evidence_strength: string
  confidence: number
  rationale: string
  conflicts: string[]
  evidence_ids?: string[]
  missing_evidence?: string[]
  ready_for_selection?: boolean
}

export interface EvidenceMatchResult {
  match_id: string
  jd_id: string
  candidate_id: string
  matches: EvidenceMatchItem[]
  uncovered_requirements?: Array<{
    requirement_id: string
    missing_evidence: string[]
    reason: string
  }>
}

export interface ResumeClaim {
  claim_id: string
  application_id: string
  text: string
  evidence_ids: string[]
  requirement_ids: string[]
  evidence_support_score: number
  selection_reason: string
  removed_alternatives?: Array<{ claim_id: string; reason: string }>
  status: 'DRAFT' | 'SELECTED' | 'BLOCKED'
}

export interface RemovedClaim {
  claim_id: string
  reason: string
  text?: string
}

export interface ResumeSelection {
  mode: string
  removed_claims: RemovedClaim[]
  max_claims: number
  max_characters: number
}

export interface ClaimVerification {
  claim_id: string
  state: ClaimState
  grounded: boolean
  support_score: number
  unsupported_fragments: string[]
  explanation: string
}

export interface AtsMappedField {
  field_id: string
  label: string
  value: string
  source_claim_ids: string[]
  action: FieldAction
}

export interface AtsFormMapping {
  application_id: string
  target: string
  fields: AtsMappedField[]
  unmapped_fields: string[]
  consistency_state: string
}

export interface FieldControl {
  field_id: string
  level: FieldControlLevel
  action: FieldAction
  show_sources: boolean
  source_claim_ids: string[]
}

export interface RiskItem {
  risk_id: string
  type: string
  severity: string
  message: string
  related_claim_ids: string[]
  mitigation: string
  recommended_action: string
}

export interface RiskResult {
  application_id: string
  risk_level: AggregateRiskLevel
  action: FieldAction
  risks: RiskItem[]
  requires_human_confirmation: boolean
}

export interface HumanConfirmation {
  required: boolean
  reason: string
  allowed_actions: string[]
}

export interface StepTraceItem {
  step: string
  status: string
  mode?: string
  fallback_reason?: string
  error?: string
}

export interface ComponentModes {
  jd_parser?: string
  ats_form_mapper?: string
  [key: string]: string | undefined
}

export interface AuditRecord {
  audit_id: string
  application_id: string
  version?: number
  created_at?: string
  event?: string
  actor?: string
  trace_id?: string
  decision?: string
}

/** Full POST /api/v1/workflow/mock success body (offline / dynamic / fixture). */
export interface WorkflowResponse {
  requires_reverification?: boolean
  evidence_sources?: VaultEvidence[]
  trace_id: string
  application_id: string
  candidate_id: string
  execution_mode?: string
  mock_notice?: string
  workflow_status: WorkflowStatus
  parsed_jd: ParsedJd
  evidence_match: EvidenceMatchResult
  resume_claims: ResumeClaim[]
  resume_selection: ResumeSelection
  claim_verification: ClaimVerification[]
  ats_form_mapping: AtsFormMapping
  field_controls: FieldControl[]
  risk_result: RiskResult
  human_confirmation: HumanConfirmation
  audit_record: AuditRecord
  step_trace: StepTraceItem[]
  component_modes?: ComponentModes
  /** Present only on pre-recorded demo packs */
  _prerecorded?: {
    case: string
    notice: string
  }
}

export interface LocalClaimDecision {
  claim_id: string
  decision: 'confirm' | 'reject' | 'edit' | null
  editedText?: string
  freshness: LocalClaimFreshness
}

export interface LocalFieldDecision {
  field_id: string
  confirmed: boolean
  acknowledgedBlocked: boolean
}

/** Local evidence workspace (file snapshots + human review). */
export type EvidenceFileState =
  | 'PENDING'
  | 'PARSING'
  | 'NEEDS_REVIEW'
  | 'INDEXED'
  | 'FAILED'

export type EvidenceReviewState = 'UNREVIEWED' | 'REVIEWED' | 'CONFLICT' | 'STALE'

export type EvidenceLinkState = 'ACTIVE' | 'STALE' | 'CONFLICT'

export interface EvidenceWorkspace {
  workspace_id: string
  name: string
  created_at: string
}

export interface EvidenceSpan {
  span_id: string
  file_id: string
  page?: number | null
  bbox?: number[] | null
  line_start?: number | null
  line_end?: number | null
  raw_text: string
  extractor: string
  extractor_version?: string
}

export interface EvidenceSourceFile {
  file_id: string
  workspace_id: string
  relative_path: string
  media_type: string
  size: number
  sha256: string
  imported_at: string
  version: number
  state: EvidenceFileState | string
  parse_error?: string | null
  is_conversion?: boolean
  conversion_note?: string | null
  span_count?: number
  spans?: EvidenceSpan[]
  evidence_id?: string
  evidence_review_state?: string | null
  normalized_fields?: AwardEvidenceFields
  ocr_fields?: AwardEvidenceFields
  ocr_text_preview?: string
  recognition_saved?: boolean
  suggested_fields?: AwardEvidenceFields
  deduplicated?: boolean
  skipped_reparse?: boolean
  reparsed?: boolean
  stale_previous?: boolean
  notice?: string
  sidecar?: boolean
}

export interface AwardEvidenceFields {
  recipient?: string
  award_name?: string
  grade?: string
  issuer?: string
  date?: string
}

export interface EvidenceRecord {
  evidence_id: string
  workspace_id: string
  kind: string
  normalized_fields: AwardEvidenceFields
  ocr_fields?: AwardEvidenceFields
  review_state: EvidenceReviewState | string
  reviewed_at?: string | null
  primary_file_id?: string | null
  file?: EvidenceSourceFile | null
  spans?: EvidenceSpan[]
  links?: EvidenceLink[]
}

export interface EvidenceLink {
  link_id: string
  target_type: string
  target_id: string
  evidence_id: string
  file_sha256: string
  linked_at: string
  link_state: EvidenceLinkState | string
  review_state?: string
  normalized_fields?: AwardEvidenceFields
  relative_path?: string
  version?: number
  file_state?: string
  current_sha?: string
  primary_file_id?: string
}

export interface EvidenceSearchMatch {
  span: EvidenceSpan
  file_id: string
  relative_path: string
  sha256: string
  version: number
  media_type: string
  workspace_id: string
  evidence_id?: string | null
  review_state?: string | null
  normalized_fields?: AwardEvidenceFields
  relevance_note?: string
}

export interface ClaimEvidenceCheck {
  evidence_id: string
  status: 'VERIFIED' | 'CONFLICT' | 'STALE' | 'NEEDS_REVIEW' | string
  supported: boolean
  reasons: string[]
  evidence?: EvidenceRecord
  notice?: string
}

/** Resume ↔ local evidence auto-match row */
export type ResumeMatchStatus =
  | 'LINKED'
  | 'MATCHED'
  | 'NEEDS_CONFIRM'
  | 'CONFLICT'
  | 'MISSING'
  | 'REJECTED'
  | 'UNCHECKED'

export interface ResumeMatchItem {
  target_type: 'award' | 'claim' | 'project' | 'internship' | 'experience' | string
  target_id: string
  kind?: string
  label: string
  status: ResumeMatchStatus | string
  score: number
  evidence_id?: string | null
  relative_path?: string | null
  review_state?: string | null
  notes: string[]
  action: string
  gap_hint?: string
  candidate_fields?: AwardEvidenceFields
}

export interface ResumeMatchReport {
  workspace_id: string
  summary: Record<string, number>
  results: ResumeMatchItem[]
  notice?: string
}
