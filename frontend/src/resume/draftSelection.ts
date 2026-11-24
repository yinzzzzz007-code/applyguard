import type {EditableResumeForm,EvidenceMatchItem,ResumeClaim,WorkflowResponse} from '../api/types'

export type DraftClaim={claim_id:string;text:string;evidence_ids:string[];experienceTitle:string;kind:string}
const textKey=(text:string)=>text.replace(/\s+/g,'').toLocaleLowerCase()
function safeClaimId(raw: string): string {
  const body = raw.replace(/[^a-zA-Z0-9_]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase()
  const id = body.startsWith('claim_') ? body : `claim_${body || 'item'}`
  return id.slice(0, 96)
}

/** Build selectable resume sentences from the user's saved 经历库 form. */
export function claimsFromResumeForm(form: EditableResumeForm | null): DraftClaim[] {
  if (!form) return []
  const out: DraftClaim[] = []

  const push = (
    id: string,
    kind: string,
    organization: string,
    title: string,
    role: string,
    description: string,
  ) => {
    const org = organization.trim()
    const label = (title || role).trim()
    const lines = description
      .split(/\r?\n/)
      .map((l) => l.trim().replace(/^[-*•·、]\s*/, ''))
      .filter(Boolean)
    const text = (description.trim().length <= 420 && description.trim() ? description.trim() : lines.find((l) => l.length >= 8) || lines[0] || [org, label].filter(Boolean).join(' · ')).trim()
    if (!text) return
    out.push({
      claim_id: safeClaimId(id.replace(/^exp_/, '')),
      text: text.slice(0, 420),
      evidence_ids: [],
      experienceTitle: [label, org].filter(Boolean).join(' · ') || kind,
      kind,
    })
  }

  form.internships.forEach((e) =>
    push(e.id, '实习', e.organization, e.title, e.role, e.description),
  )
  form.projects.forEach((e) =>
    push(e.id, '项目', e.organization, e.title, e.role, e.description),
  )
  ;(form.awards ?? []).forEach((a) => {
    const name = a.name.trim()
    if (!name) return
    const text = (a.description || '').trim() || `${name}${a.issuer ? `（${a.issuer}）` : ''}`
    out.push({
      claim_id: safeClaimId(a.id),
      text: text.slice(0, 420),
      evidence_ids: [],
      experienceTitle: [name, a.issuer].filter(Boolean).join(' · ') || '获奖 / 竞赛',
      kind: '获奖',
    })
  })
  return out
}


export const AUTO_DRAFT_MIN_SCORE = 3.5
export const STRONG_MATCH_SCORE = 6

export function matchScoreOutOfTen(row: EvidenceMatchItem): number {
  const raw = row.lead ? row.lead.score * 10 : row.score_breakdown?.ai_score_10
  const score = Number.isFinite(raw) ? raw! : row.relevance_score * 10
  return Number.isFinite(score) ? Number(Math.max(0, Math.min(10, score)).toFixed(1)) : 0
}

export function relevanceFor(workflow:WorkflowResponse,id:string):number {
  return Math.max(0,...workflow.evidence_match.matches.filter(row=>row.claim_ids.includes(id)).map(matchScoreOutOfTen)) / 10
}
function orderByRelevance(workflow:WorkflowResponse,claims:ResumeClaim[]):ResumeClaim[] {
  return [...claims].sort((a,b)=>relevanceFor(workflow,b.claim_id)-relevanceFor(workflow,a.claim_id))
}
export function remainingDraftClaims(workflow:WorkflowResponse,form:EditableResumeForm|null):DraftClaim[] {
  const ids=new Set(workflow.resume_claims.map(row=>row.claim_id))
  const texts=new Set(workflow.resume_claims.map(row=>textKey(row.text)))
  const seen=new Set<string>()
  return claimsFromResumeForm(form).sort((a,b)=>relevanceFor(workflow,b.claim_id)-relevanceFor(workflow,a.claim_id)).filter(row=>{
    const key=textKey(row.text)
    if(ids.has(row.claim_id)||texts.has(key)||seen.has(key))return false
    seen.add(key);return true
  })
}
function invalidateDraft(workflow:WorkflowResponse):WorkflowResponse {
  return {...workflow,requires_reverification:true,workflow_status:'AWAITING_HUMAN_CONFIRMATION',
    resume_selection:{...workflow.resume_selection,draft_initialized:true},
    field_controls:workflow.field_controls.map(row=>({...row,action:'BLOCKED'})),
    human_confirmation:{...workflow.human_confirmation,allowed_actions:['EDIT','CANCEL']}}
}
export function addDraftClaim(workflow:WorkflowResponse,input:Pick<DraftClaim,'claim_id'|'text'|'evidence_ids'>,reason='用户从经历库补选，证据状态仍待核验。'):WorkflowResponse {
  if(workflow.resume_claims.some(row=>row.claim_id===input.claim_id||textKey(row.text)===textKey(input.text)))return workflow
  if(!input.text.trim()||input.text.length>420)throw Error('每条经历描述需为 1–420 个字符。')
  if(workflow.resume_claims.length>=20)throw Error('每份草稿最多 20 条，请先移出不需要的经历。')
  const requirements=[...new Set(workflow.evidence_match.matches.filter(row=>row.claim_ids.includes(input.claim_id)).map(row=>row.requirement_id))]
  const claim:ResumeClaim={claim_id:input.claim_id,text:input.text,evidence_ids:input.evidence_ids,application_id:workflow.application_id,requirement_ids:requirements,evidence_support_score:0,
    selection_reason:reason,status:'DRAFT'}
  const next=invalidateDraft(workflow)
  return {...next,resume_claims:orderByRelevance(workflow,[...next.resume_claims,claim]),
    resume_selection:{...next.resume_selection,removed_claims:next.resume_selection.removed_claims.filter(row=>row.claim_id!==claim.claim_id)},
    claim_verification:[...next.claim_verification.filter(row=>row.claim_id!==claim.claim_id),
      {claim_id:claim.claim_id,state:'NEEDS_REVIEW',grounded:false,support_score:0,unsupported_fragments:[],explanation:'已加入编辑草稿；相关度不代表材料支持，请独立核验。'}]}
}
export function removeDraftClaim(workflow:WorkflowResponse,id:string):WorkflowResponse {
  const claim=workflow.resume_claims.find(row=>row.claim_id===id)
  if(!claim)return workflow
  const next=invalidateDraft(workflow)
  const results={...next.grounding?.results};delete results[id]
  const choices={...next.review_session?.choices};delete choices[id]
  return {...next,resume_claims:next.resume_claims.filter(row=>row.claim_id!==id),
    claim_verification:next.claim_verification.filter(row=>row.claim_id!==id),
    grounding:next.grounding?{...next.grounding,results}:undefined,
    review_session:next.review_session?{...next.review_session,choices,actions:next.review_session.actions+1}:undefined,
    resume_selection:{...next.resume_selection,removed_claims:[...next.resume_selection.removed_claims.filter(row=>row.claim_id!==id),
      {claim_id:id,text:claim.text,reason:'MANUAL_REMOVED: 用户从正文移除，可从经历库重新补选。'}]}}
}
export function initializeDraftSelection(workflow:WorkflowResponse,form:EditableResumeForm|null):WorkflowResponse {
  if(!form || form.candidateId!==workflow.candidate_id || workflow._prerecorded ||
    workflow.component_modes?.career_vault!=='LOCAL_RESUME_DRAFT' ||
    workflow.resume_selection.auto_match_threshold===AUTO_DRAFT_MIN_SCORE)return workflow

  const removed=workflow.resume_selection.removed_claims.filter(row=>/MANUAL_REMOVED|手动移出|用户从正文移除/.test(row.reason))
  const removedIds=new Set(removed.map(row=>row.claim_id))
  const removedTexts=new Set(removed.map(row=>textKey(row.text || '')).filter(Boolean))
  const candidates=remainingDraftClaims(workflow,form).filter(row=>!removedIds.has(row.claim_id) &&
    !removedTexts.has(textKey(row.text)) && relevanceFor(workflow,row.claim_id)*10>=AUTO_DRAFT_MIN_SCORE)
  let next=workflow
  const capacity=Math.max(0,20-workflow.resume_claims.length)
  for(const row of candidates.slice(0,capacity)){
    next=addDraftClaim(next,row,'岗位匹配度达到 3.5/10，自动加入草稿，材料待核验。')
  }
  const overflow=candidates.length>capacity?' 正文已达 20 条，其余经历可从下方补选。':''
  const ordered=orderByRelevance(workflow,next.resume_claims)
  return {...next,resume_claims:ordered,resume_selection:{...next.resume_selection,draft_initialized:true,auto_match_threshold:AUTO_DRAFT_MIN_SCORE,
    draft_notice:'匹配度达到 3.5/10 的经历自动带入正文，6 分及以上优先。你可以编辑、移除或补选。'+overflow}}
}
