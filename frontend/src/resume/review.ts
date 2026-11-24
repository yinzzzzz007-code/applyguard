import type { EditableResumeForm, GroundingClaimResult, ResumeClaim, WorkflowResponse } from '../api/types'

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
  if (claim && result && result.final_text===claim.text && (result.original_check?.relation==='CONTRADICTED' || result.relation==='CONTRADICTED')) return 5
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
  if (workflow._prerecorded && !workflow.requires_reverification && !row) {
    const recorded = workflow.claim_verification.find(item => item.claim_id === id)
    return recorded?.state === 'BLOCKED' ? '预录结果：已阻断' : '预录结果：请查看核验详情'
  }
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

export type DiffPiece = { text: string; changed: boolean }
export function diffSpans(original:string, proposal:string): { original:DiffPiece[]; proposal:DiffPiece[] } {
  const a=Array.from(original), b=Array.from(proposal)
  const rows=Array.from({length:a.length+1},()=>new Uint16Array(b.length+1))
  for(let i=a.length-1;i>=0;i--) for(let j=b.length-1;j>=0;j--)
    rows[i][j]=a[i]===b[j]?rows[i+1][j+1]+1:Math.max(rows[i+1][j],rows[i][j+1])
  const old:DiffPiece[]=[], next:DiffPiece[]=[]
  function add(out:DiffPiece[], text:string, changed:boolean) {
    const last=out.at(-1)
    if(last?.changed===changed)last.text+=text
    else out.push({text,changed})
  }
  let i=0,j=0
  while(i<a.length||j<b.length) {
    if(i<a.length&&j<b.length&&a[i]===b[j]) {add(old,a[i],false);add(next,b[j],false);i++;j++}
    else if(j<b.length&&(i===a.length||rows[i][j+1]>rows[i+1][j])) {add(next,b[j],true);j++}
    else {add(old,a[i],true);i++}
  }
  return {original:old,proposal:next}
}

export function proposalNeedsReview(result:GroundingClaimResult, error?:string|null):boolean {
  return Boolean(error || result.proposal_check?.relation !== 'SUPPORTED' || !result.proposal_check?.complete ||
    result.proposal_rejected || result.change_audit?.sensitive_change || result.preservation?.lost_supported_details?.length ||
    result.risk_escalation?.error || result.risk_escalation?.agrees_with_primary === false)
}

export function polishResultSummary(result:Partial<WorkflowResponse>):{count:number;error:string|null} {
  return {count:Object.values(result.grounding?.results??{}).filter(row=>Boolean(row.proposed_text) && (typeof row.original_text !== 'string' || row.proposed_text !== row.original_text)).length,
    error:result.grounding?.error??null}
}
export function historyVersionLabel(label:string,proposalCount:number|null):string {
  return label==='建议已生成：等待预览与采用' && proposalCount===0
    ? '本次未生成建议（旧版记录标题有误）' : label
}

export function proposalStatus(result:GroundingClaimResult, error?:string|null):string {
  if(error)return '核查未完成，请重试；原文已保留。'
  if(result.verification_scope==='personal')return '个人资料按表单填写，不作为经历事实核验。'
  const check=result.proposal_check
  if(!check)return '建议尚无独立事实核查结果，请对照材料。'
  if(check.relation==='CONTRADICTED')return '建议与材料存在冲突，请查看核查详情。'
  if(check.relation==='INSUFFICIENT'||!check.complete)return '建议的证据不足或核查不完整，请查看核查详情。'
  if(result.proposal_rejected)return '建议的事实有材料支持，但其他改写检查未确认，请查看原因。'
  return '建议的事实已对照材料核查，仍请人工检查表达和范围。'
}

export function isEducationProfile(claim:ResumeClaim|undefined,form:EditableResumeForm|null):boolean {
  if(!claim||!form)return false
  return form.education.some(row=>{
    const body=row.id.trim().replace(/[^a-zA-Z0-9_]+/g,'_').replace(/^_+|_+$/g,'').toLowerCase()
    const id=(body.startsWith('claim_')?body:`claim_${body||'item'}`).slice(0,96)
    if(id!==claim.claim_id)return false
    const head=[row.school,row.degree,row.major].filter(Boolean).join(' · ')||'教育经历'
    const ym=(value:string)=>{const m=value.match(/^(\d{4})[-/.年](\d{1,2})/);return m?`${m[1]}-${m[2].padStart(2,'0')}`:value}
    const span=[ym(row.start),ym(row.end)].filter(Boolean).join(' — ')
    return [head,head+'（在读）'].some(value=>(value+(span?` · ${span}`:'')).slice(0,420)===claim.text)
  })
}
