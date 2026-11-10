import type { EditableResumeForm, WorkflowResponse } from '../api/types'

const KEY = 'applyguard.review-session.v1'
export interface ReviewSessionSnapshot {
  version: 1
  savedAt: string
  jd: string
  form: EditableResumeForm | null
  workflow: WorkflowResponse
  drafts: Record<string, string>
}

/** Restore writing progress, never historical permission to fill or export. */
export function invalidateRestoredWorkflow(workflow: WorkflowResponse, reason = '已恢复草稿；请按当前材料重新核验。'): WorkflowResponse {
  return {...workflow, requires_reverification: true, workflow_status: 'AWAITING_HUMAN_CONFIRMATION',
    claim_verification: workflow.claim_verification.map(row => ({...row, state: row.state === 'BLOCKED' ? 'BLOCKED' : 'NEEDS_REVIEW', grounded: false,
      support_score: 0, explanation: reason})),
    field_controls: workflow.field_controls.map(row => ({...row, action: 'BLOCKED'})),
    grounding: workflow.grounding ? {...workflow.grounding, error: reason} : undefined,
    human_confirmation: {...workflow.human_confirmation, allowed_actions: ['EDIT', 'CANCEL']}}
}

export function loadReviewSession(storage: Pick<Storage, 'getItem'>): ReviewSessionSnapshot | null {
  try {
    const value = JSON.parse(storage.getItem(KEY) ?? 'null') as ReviewSessionSnapshot | null
    const w = value?.workflow
    if (value?.version !== 1 || typeof value.jd !== 'string' || typeof value.savedAt !== 'string' || !w ||
      typeof w.application_id !== 'string' || typeof w.candidate_id !== 'string' || !w.parsed_jd || !w.resume_selection ||
      !Array.isArray(w.resume_claims) || w.resume_claims.length > 20 ||
      !w.resume_claims.every(c => typeof c.claim_id === 'string' && typeof c.text === 'string' && c.text.length <= 420) ||
      !Array.isArray(w.claim_verification) || !Array.isArray(w.field_controls) || !w.human_confirmation || !w.risk_result ||
      !w.ats_form_mapping || !Array.isArray(w.step_trace)) return null
    if (value.form && (value.form.candidateId !== w.candidate_id || !value.form.basic ||
      !Array.isArray(value.form.education) || !Array.isArray(value.form.projects) || !Array.isArray(value.form.internships))) return null
    const ids = new Set(w.resume_claims.map(c => c.claim_id))
    const drafts = Object.fromEntries(Object.entries(value.drafts ?? {}).filter(([id,text]) =>
      ids.has(id) && typeof text === 'string' && text.length <= 420))
    return {...value, drafts, workflow: invalidateRestoredWorkflow(w)}
  } catch { return null }
}

export function saveReviewSession(snapshot: Omit<ReviewSessionSnapshot, 'version'|'savedAt'> | null,
  storage: Pick<Storage, 'setItem'|'removeItem'>): void {
  if (!snapshot) {storage.removeItem(KEY); return}
  storage.setItem(KEY, JSON.stringify({...snapshot, version: 1, savedAt: new Date().toISOString()}))
}
