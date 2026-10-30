import type {
  AtsMappedField,
  LocalClaimDecision,
  LocalFieldDecision,
  WorkflowResponse,
} from './api/types'

export function copyableClaim(
  workflow: WorkflowResponse,
  decisions: Record<string, LocalClaimDecision>,
  claimId: string,
): boolean {
  const verification = workflow.claim_verification.find((item) => item.claim_id === claimId)
  const decision = decisions[claimId]
  const claim = workflow.resume_claims.find((item) => item.claim_id === claimId)
  if (workflow.requires_reverification || !verification || !claim) return false
  if (workflow.grounding) {
    const report = workflow.grounding
    const result = report.results[claimId]
    if (report.mode !== 'sag_atomic' || report.error || !result || result.state !== 'VERIFIED' ||
        result.final_text !== claim.text || verification.state !== 'VERIFIED') return false
  }
  if (!claim.evidence_ids.length || claim.evidence_ids.some((id) => id.startsWith('ev_draft_'))) return false
  if (decision?.decision === 'reject' || decision?.freshness === 'rejected') return false
  if (decision?.decision === 'edit' || decision?.freshness === 'edited_pending_reverify') return false
  if (verification.state === 'BLOCKED') return false
  if (verification.state === 'NEEDS_REVIEW') return decision?.decision === 'confirm'
  return verification.state === 'VERIFIED'
}

export function copyableField(
  workflow: WorkflowResponse,
  claimDecisions: Record<string, LocalClaimDecision>,
  fieldDecisions: Record<string, LocalFieldDecision>,
  field: AtsMappedField,
): boolean {
  const control = workflow.field_controls.find((item) => item.field_id === field.field_id)
  const action = control?.action ?? field.action
  if (action === 'BLOCKED') return false
  if (
    (action === 'REQUIRES_CONFIRMATION' || control?.level === 'L2' || control?.level === 'L3') &&
    !fieldDecisions[field.field_id]?.confirmed
  ) return false
  const sourceIds = [...new Set([...field.source_claim_ids, ...(control?.source_claim_ids ?? [])])]
  return sourceIds.every((id) => copyableClaim(workflow, claimDecisions, id))
}
