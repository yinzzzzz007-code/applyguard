// Gitvextor的原型：历史版本恢复与核验状态失效（姜凌天，2026-10-30）。
import type { WorkflowResponse } from '../api/types'

export interface TextVersion {
  id: string
  createdAt: string
  label: string
  claims: Array<{claim_id: string; text: string}>
  candidateId?: string
  restoredFrom?: string
  stateSnapshot?: {
    workflowStatus: string
    requiresReverification: boolean
    claimStates: Array<{claim_id: string; state: string}>
    removedClaims: Array<{claim_id: string; reason: string; text?: string}>
    proposals: Array<{claim_id: string; text: string; rejected: boolean}>
  }
}
const key = (candidate: string) => `applyguard.grounding.text-history.${candidate}`

export function loadTextVersions(candidate: string, storage: Pick<Storage,'getItem'> = localStorage): TextVersion[] {
  try {
    const rows: unknown = JSON.parse(storage.getItem(key(candidate)) ?? '[]')
    if (!Array.isArray(rows)) return []
    return rows.filter((row): row is TextVersion => row && typeof row.id === 'string' &&
      typeof row.createdAt === 'string' && typeof row.label === 'string' && Array.isArray(row.claims) &&
      row.claims.length <= 20 && row.claims.every((c: {claim_id?: unknown;text?: unknown}) =>
        typeof c.claim_id === 'string' && typeof c.text === 'string' && c.text.length <= 420)).slice(0,20)
  } catch { return [] }
}

export function saveTextVersion(workflow: WorkflowResponse, label: string,
  storage: Pick<Storage,'getItem'|'setItem'> = localStorage, restoredFrom?: string): void {
  const rows = loadTextVersions(workflow.candidate_id,storage)
  const claims = workflow.resume_claims.map(({claim_id,text}) => ({claim_id,text}))
  const stateSnapshot = {
    workflowStatus: workflow.workflow_status,
    requiresReverification: Boolean(workflow.requires_reverification),
    claimStates: workflow.claim_verification.map(({claim_id,state}) => ({claim_id,state})),
    removedClaims: workflow.resume_selection.removed_claims.map(({claim_id,reason,text}) => ({claim_id,reason,text})),
    proposals: Object.entries(workflow.grounding?.results ?? {}).filter(([,r]) => r.proposed_text)
      .map(([claim_id,r]) => ({claim_id,text:r.proposed_text!,rejected:Boolean(r.proposal_rejected)})),
  }
  if (!restoredFrom && JSON.stringify(rows[0]?.claims) === JSON.stringify(claims) &&
    JSON.stringify(rows[0]?.stateSnapshot) === JSON.stringify(stateSnapshot)) return
  storage.setItem(key(workflow.candidate_id),JSON.stringify([{id:crypto.randomUUID(),
    createdAt:new Date().toISOString(),label,claims,stateSnapshot,candidateId:workflow.candidate_id,restoredFrom},...rows].slice(0,20)))
}

export function restoreTextVersion(workflow: WorkflowResponse, version: TextVersion): WorkflowResponse {
  if (version.candidateId && version.candidateId !== workflow.candidate_id) throw new Error('不能恢复其他候选人的版本')
  const claims = version.claims.map(c => ({claim_id:c.claim_id,text:c.text,application_id:workflow.application_id,
    evidence_ids:[],requirement_ids:[],evidence_support_score:0,selection_reason:'历史版本恢复，须重新核验',status:'DRAFT' as const}))
  return {...workflow,resume_claims:claims,requires_reverification:true,workflow_status:'AWAITING_HUMAN_CONFIRMATION',
    resume_selection:{...workflow.resume_selection,removed_claims:Array.isArray(version.stateSnapshot?.removedClaims)
      ? version.stateSnapshot.removedClaims : []},
    claim_verification:claims.map(c => ({claim_id:c.claim_id,state:'NEEDS_REVIEW' as const,grounded:false,
      support_score:0,unsupported_fragments:[],explanation:'历史状态仅供查看；恢复后必须对当前原件重新核验。'})),
    grounding:workflow.grounding ? {...workflow.grounding,results:{},error:'历史版本已恢复，当前核验结果失效。'} : undefined,
    field_controls:workflow.field_controls.map(c => ({...c,action:'BLOCKED' as const})),
    human_confirmation:{...workflow.human_confirmation,required:true,allowed_actions:['EDIT','CANCEL'],
      reason:'版本恢复后须重新核验；历史通过状态不能直接沿用。'},
  }
}
