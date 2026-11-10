import type { GroundingClaimResult, WorkflowResponse } from '../api/types'

export type ReviewChoice = { text: string; action: 'original' | 'edit' | 'accept'; at: string }
export type ReviewSession = { startedAt: number; actions: number; interruptions: number; choices: Record<string, ReviewChoice> }
export function session(workflow: WorkflowResponse): ReviewSession {
  return workflow.review_session ?? {startedAt: Date.now(), actions: 0, interruptions: 0, choices: {}}
}
export function needsAttention(result?: GroundingClaimResult): boolean {
  if (result?.wording_auto_restored && result.final_text === result.original_text) return false
  if (result?.wording_auto_applied && result.proposal_applied && !result.proposal_rejected) return false
  return Boolean(result && (result.proposal_rejected || result.preservation?.lost_supported_details.length ||
    result.change_audit?.sensitive_change || result.risk_escalation?.error || result.risk_escalation?.agrees_with_primary === false))
}
export function reviewPriority(workflow: WorkflowResponse, id: string): number {
  const claim = workflow.resume_claims.find(c => c.claim_id === id)
  const choice = workflow.review_session?.choices[id]
  if (choice && choice.text === claim?.text) return 0
  const result = workflow.grounding?.results[id]
  if (result?.proposed_text && result.proposed_text !== claim?.text) return needsAttention(result) ? 4 : 1
  if (result?.proposal_rejected && !result.wording_auto_restored) return 4
  if (needsAttention(result)) return 3
  if (!result || result.state !== 'VERIFIED' || result.final_text !== claim?.text) return 2
  return 0
}
export function changeClaim(workflow: WorkflowResponse, id: string, text: string, action: ReviewChoice['action']): WorkflowResponse {
  text = text.trim()
  if (!text || text.length > 420) throw new Error('每条陈述需要 1–420 个字符。')
  const claim = workflow.resume_claims.find(c => c.claim_id === id)
  if (!claim) throw new Error('陈述已不存在，请刷新草稿。')
  const changed = claim.text !== text
  const review = session(workflow)
  const next: WorkflowResponse = {...workflow, review_session: {...review, actions: review.actions + 1,
    choices: {...review.choices, [id]: {text, action, at: new Date().toISOString()}}},
    resume_claims: workflow.resume_claims.map(c => c.claim_id === id ? {...c, text, status: changed ? 'DRAFT' : c.status} : c)}
  if (!changed) return next
  return {...next, requires_reverification: true, workflow_status: 'AWAITING_HUMAN_CONFIRMATION',
    claim_verification: next.claim_verification.map(v => v.claim_id === id ? {...v, state: 'NEEDS_REVIEW', grounded: false,
      support_score: 0, unsupported_fragments: [], explanation: '正文已修改；之前的材料核验不适用于当前文字。'} : v),
    field_controls: next.field_controls.map(c => ({...c, action: 'BLOCKED'})),
    human_confirmation: {...next.human_confirmation, allowed_actions: ['EDIT','CANCEL']}}
}
export function mergeReviewResult(workflow: WorkflowResponse, result: Partial<WorkflowResponse>): WorkflowResponse {
  const next = {...workflow, ...result, review_session: {...session(workflow),choices:{}}}
  // Every rewrite requires a person's choice, including model-approved wording changes.
  for (const claim of workflow.resume_claims) {
    const row = next.grounding?.results[claim.claim_id]
    if (row && next.resume_claims.find(c => c.claim_id === claim.claim_id)?.text !== claim.text) {
      // A successful model check is still a suggestion, never permission to rewrite.
      row.proposed_text = row.proposed_text || next.resume_claims.find(c => c.claim_id === claim.claim_id)!.text
      const review = next.review_session
      const edited = changeClaim(next, claim.claim_id, claim.text, 'original')
      Object.assign(next, edited, {review_session:review})
    }
  }
  return next
}
export function currentSupport(workflow: WorkflowResponse, id: string): string {
  const row = workflow.grounding?.results[id]
  const claim = workflow.resume_claims.find(c => c.claim_id === id)
  if (workflow.requires_reverification || row?.final_text !== claim?.text || workflow.grounding?.error) return '当前文字待核验'
  if (row?.verification_scope === 'personal') return '个人资料：按表单填写'
  return row?.relation === 'CONTRADICTED' ? '材料有冲突' : row?.state === 'VERIFIED' ? '材料支持' : '材料不足或待核验'
}
// Highlight only changed spans in a sentence already flagged for factual review, not every stylistic edit.
export function changedSpan(original: string, proposed: string): [string,string,string] {
  let start = 0, end = 0
  while (start < original.length && start < proposed.length && original[start] === proposed[start]) start++
  while (end < original.length-start && end < proposed.length-start && original[original.length-1-end] === proposed[proposed.length-1-end]) end++
  return [proposed.slice(0,start), proposed.slice(start,proposed.length-end), end ? proposed.slice(-end) : '']
}
