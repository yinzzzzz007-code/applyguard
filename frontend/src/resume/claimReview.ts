import type {AtsMappedField, GroundingClaimResult, LocalClaimDecision, WorkflowResponse} from '../api/types'

type Decisions = Record<string, LocalClaimDecision>
type Atom = GroundingClaimResult['atoms'][number]

export function retainRemaining(claims: WorkflowResponse['resume_claims'], previous: Decisions): Decisions {
  const remaining = claims.filter(c => !previous[c.claim_id]?.decision && previous[c.claim_id]?.freshness !== 'rejected')
  if (!remaining.length) return previous
  const next = {...previous}
  for (const {claim_id} of remaining) next[claim_id] = {claim_id, decision: 'confirm', freshness: 'as_returned'}
  return next
}

export function isQuantitative(text: string) {
  return /\d[\d,.]*\s*(?:%|％|个百分点|毫秒|秒|倍|分之|人次|万元|ms\b|fps\b|\/\s*\d)|(?:第|排名|准确率|吞吐量|延迟)\s*\d/i.test(text)
}

function cited(atom: Pick<Atom,'citations'>) {
  return atom.citations.some(c => c.quote?.trim() && c.end > c.start)
}

export function evidenceCoverage(result: GroundingClaimResult | undefined, hasLink: boolean, hasCandidate: boolean, current: boolean, lookup: 'loading'|'ready'|'error') {
  const atoms = current ? result?.atoms ?? [] : []
  const supported = atoms.filter(a => a.relation === 'SUPPORTED' && cited(a))
  const unresolved = atoms.filter(a => !supported.includes(a)).sort((a,b) =>
    Number(b.relation === 'CONTRADICTED' && cited(b)) - Number(a.relation === 'CONTRADICTED' && cited(a))
    || Number(isQuantitative(b.claim_excerpt || b.text)) - Number(isQuantitative(a.claim_excerpt || a.text)))
  const full = result?.full_claim_check
  const conflict = unresolved.some(a => a.relation === 'CONTRADICTED' && cited(a)) ||
    (current && full?.relation === 'CONTRADICTED' && cited(full))
  const retrieved = current && !!result?.retrieved_sources.length
  const related = hasLink || retrieved || supported.length > 0 || conflict
  let label: string
  if (conflict) label = '材料有冲突'
  else if (current && result?.state === 'VERIFIED' && result.complete && !unresolved.length && supported.length) label = '材料已支持'
  else if (supported.length) label = '材料支持部分事实'
  else if (related) label = retrieved ? '已检索材料，细节待确认' : '已关联材料，待核验'
  else if (hasCandidate) label = '已找到候选材料，待核对关联'
  else if (lookup !== 'ready') label = lookup === 'loading' ? '正在查找相关材料' : '材料库查询未完成'
  else label = '暂无已关联材料'
  return {label, supported, unresolved: related ? unresolved : [], related}
}

export function retainedFieldValue(workflow: WorkflowResponse, field: AtsMappedField, decisions: Decisions) {
  const sources = new Set([...field.source_claim_ids, ...(workflow.field_controls.find(c => c.field_id === field.field_id)?.source_claim_ids ?? [])])
  const changed = [...sources].some(id => decisions[id]?.decision === 'reject' || workflow.review_session?.choices[id]?.action === 'edit')
  if (!changed) return field.value
  if (!/candidate_summary|候选人摘要|candidate summary/i.test(field.field_id+' '+field.label)) return ''
  return workflow.resume_claims.filter(c => sources.has(c.claim_id) && decisions[c.claim_id]?.decision !== 'reject')
    .map(c => c.text).join('\n')
}

export function keepExclusions(previous: Decisions): Decisions {
  const onlyExcluded = Object.entries(previous).filter(([,d]) => d.decision === 'reject')
  return onlyExcluded.length === Object.keys(previous).length ? previous : Object.fromEntries(onlyExcluded)
}
