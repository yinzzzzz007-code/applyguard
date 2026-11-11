import type {
  AtsMappedField,
  ClaimVerification,
  EditableResumeForm,
  RiskItem,
  WorkflowResponse,
} from './api/types'
import { zhText } from './i18n'

export type SummaryClaimRow = {
  claimId: string
  title: string
  state: ClaimVerification['state'] | 'UNKNOWN'
  reason: string
  pinpoint: string | null
  linkToClaim: boolean
}

export type UncoveredRequirementRow = {
  id: string
  text: string
  category: string
  note: string
}

export type CheckNotice =
  | { kind: 'offline'; key: string; count: number; message: string }
  | {
      kind: 'uncovered'
      key: string
      count: number
      message: string
      requirements: UncoveredRequirementRow[]
    }
  | { kind: 'action'; key: string; severity: string; message: string; mitigation: string }
  | { kind: 'detail'; key: string; severity: string; message: string; mitigation: string }

const UNCOVERED_RE = /JD requirement (req_\d+) has no ready evidence/i
const OFFLINE_HINT = '当前为全离线模式'

export function findSummaryField(workflow: WorkflowResponse): AtsMappedField | undefined {
  return workflow.ats_form_mapping.fields.find(
    (field) =>
      field.field_id === 'candidate_summary' ||
      field.field_id === 'field_candidate_summary' ||
      /candidate\s*summary|候选人摘要/i.test(field.label),
  )
}

function experienceTitle(
  claimId: string,
  claimText: string,
  form: EditableResumeForm | null,
  workflow: WorkflowResponse,
): string {
  const match = workflow.evidence_match.matches.find((row) => row.claim_ids.includes(claimId))
  if (match && form) {
    const entry = [...form.internships, ...form.projects].find(
      (item) => item.sourceExperienceId === match.experience_id || item.id === match.experience_id,
    )
    if (entry) {
      const label = [entry.organization, entry.title || entry.role].filter(Boolean).join(' · ')
      if (label) return label
    }
  }
  const indexed = claimId.match(/^claim_(proj|intern)_(\d+)/)
  if (indexed && form) {
    const list = indexed[1] === 'proj' ? form.projects : form.internships
    const entry = list[Number(indexed[2])]
    if (entry) {
      const label = [entry.organization, entry.title || entry.role].filter(Boolean).join(' · ')
      if (label) return label
    }
  }
  const short = claimText.trim().replace(/\s+/g, ' ')
  return short.length > 36 ? `${short.slice(0, 36)}…` : short || claimId.replace(/^claim_/, '陈述·')
}

export function buildSummaryClaimRows(
  workflow: WorkflowResponse,
  form: EditableResumeForm | null,
): { rows: SummaryClaimRow[]; summaryOnlyReason: string | null } {
  const field = findSummaryField(workflow)
  if (!field) return { rows: [], summaryOnlyReason: '当前演示表单没有候选人摘要字段。' }

  const verifications = Object.fromEntries(workflow.claim_verification.map((row) => [row.claim_id, row]))
  const claims = Object.fromEntries(workflow.resume_claims.map((row) => [row.claim_id, row]))
  const sourceIds = field.source_claim_ids

  if (!sourceIds.length) {
    const control = workflow.field_controls.find((row) => row.field_id === field.field_id)
    const reason =
      control?.action === 'BLOCKED' || field.action === 'BLOCKED'
        ? '摘要字段被阻断，但结果未标明具体陈述，只能在摘要层级处理。'
        : '摘要字段未关联具体陈述，无法定位到某一段经历。'
    return { rows: [], summaryOnlyReason: reason }
  }

  const rows = sourceIds.map((claimId) => {
    const claim = claims[claimId]
    const verification = verifications[claimId]
    const text = claim?.text ?? ''
    const fragments = verification?.unsupported_fragments?.filter(Boolean) ?? []
    const pinpoint = fragments.length
      ? `需补充依据：${fragments.slice(0, 3).join('、')}`
      : verification && verification.state !== 'VERIFIED'
        ? `这句话需要处理：${text.trim().replace(/\s+/g, ' ').slice(0, 48)}${text.length > 48 ? '…' : ''}`
        : null
    return {
      claimId,
      title: experienceTitle(claimId, text, form, workflow),
      state: verification?.state ?? 'UNKNOWN',
      reason: verification ? zhText(verification.explanation) : '工作流未返回该陈述的核验结果。',
      pinpoint,
      linkToClaim: Boolean(claim && verification),
    } satisfies SummaryClaimRow
  })

  return { rows, summaryOnlyReason: null }
}

function requirementText(workflow: WorkflowResponse, requirementId: string): string {
  const requirement = workflow.parsed_jd.requirements.find((row) => row.requirement_id === requirementId)
  return requirement?.text?.trim() || requirementId.replace(/^req_0*/, '岗位要求 ')
}

const PROFILE_STATE: Record<string, string> = {
  MATCH: '已填写且相符',
  MISMATCH: '已填写但不相符',
  UNKNOWN: '未填写',
  DECLARED: '本人已填写',
}

function uncoveredNote(
  workflow: WorkflowResponse,
  requirementId: string,
  matchReason?: string,
): { category: string; note: string } {
  const requirement = workflow.parsed_jd.requirements.find((row) => row.requirement_id === requirementId)
  const category = requirement?.category ?? 'OTHER'
  const checks = workflow.profile_checks?.[requirementId] ?? []
  if (checks.length) {
    const parts = checks.map(
      (check) => `${check.label}：${check.value?.trim() || '未填写'}（${PROFILE_STATE[check.state] ?? check.state}）`,
    )
    if (category === 'EDUCATION' || checks.some((check) => /学历|专业|学校|教育/.test(check.label))) {
      return {
        category,
        note: `对照本人填写：${parts.join('；')}。属个人信息，不要求另附材料。`,
      }
    }
    return {
      category,
      note: `对照本人填写：${parts.join('；')}。以现有资料核对即可。`,
    }
  }
  if (category === 'EDUCATION') {
    return { category, note: '属教育 / 个人信息类要求，对照本人填写即可，不要求另附材料。' }
  }
  if (matchReason && /unnormalized|cannot evaluate/i.test(matchReason)) {
    return { category, note: '现有填写与经历中未见可自动对照的明确表述。' }
  }
  return { category, note: '现有填写与经历中未见对应覆盖。' }
}

function buildUncoveredRow(
  workflow: WorkflowResponse,
  requirementId: string,
  matchReason?: string,
): UncoveredRequirementRow {
  const { category, note } = uncoveredNote(workflow, requirementId, matchReason)
  return {
    id: requirementId,
    text: requirementText(workflow, requirementId),
    category,
    note,
  }
}

export function buildCheckNotices(workflow: WorkflowResponse): {
  actionable: CheckNotice[]
  details: CheckNotice[]
} {
  const actionable: CheckNotice[] = []
  const details: CheckNotice[] = []
  const uncovered: UncoveredRequirementRow[] = []
  const uncoveredReasons = new Map(
    (workflow.evidence_match.uncovered_requirements ?? []).map((row) => [row.requirement_id, row.reason]),
  )
  let offlineCount = 0
  let offlineMessage = ''

  const summaryField = findSummaryField(workflow)
  const summaryClaimIds = new Set(summaryField?.source_claim_ids ?? [])
  const shownClaimIssues = new Set(
    workflow.claim_verification
      .filter((row) => row.state !== 'VERIFIED' && summaryClaimIds.has(row.claim_id))
      .map((row) => row.claim_id),
  )

  for (const risk of workflow.risk_result.risks) {
    const message = zhText(risk.message)
    const mitigation = zhText(risk.mitigation)
    const uncoveredMatch = risk.message.match(UNCOVERED_RE)
    if (uncoveredMatch) {
      const id = uncoveredMatch[1]
      if (!uncovered.some((row) => row.id === id)) {
        uncovered.push(buildUncoveredRow(workflow, id, uncoveredReasons.get(id) ?? risk.message))
      }
      continue
    }
    if (message.includes(OFFLINE_HINT) || risk.message.includes(OFFLINE_HINT)) {
      offlineCount += 1
      offlineMessage = message
      continue
    }
    if (
      /work_authorization|工作许可/.test(risk.message) ||
      /work_authorization|工作许可/.test(message)
    ) {
      details.push({
        kind: 'detail',
        key: risk.risk_id,
        severity: risk.severity,
        message,
        mitigation,
      })
      continue
    }
    if (
      summaryField &&
      (/候选人摘要|Candidate summary/i.test(risk.message) ||
        risk.related_claim_ids.some((id) => shownClaimIssues.has(id)))
    ) {
      details.push({
        kind: 'detail',
        key: risk.risk_id,
        severity: risk.severity,
        message,
        mitigation,
      })
      continue
    }
    if (risk.type === 'UNSUPPORTED_CLAIM' && risk.related_claim_ids.some((id) => shownClaimIssues.has(id))) {
      details.push({
        kind: 'detail',
        key: risk.risk_id,
        severity: risk.severity,
        message,
        mitigation,
      })
      continue
    }

    const notice: CheckNotice = {
      kind: risk.recommended_action === 'BLOCK' || risk.severity === 'ERROR' ? 'action' : 'detail',
      key: risk.risk_id,
      severity: risk.severity,
      message,
      mitigation,
    }
    if (notice.kind === 'action') actionable.push(notice)
    else details.push(notice)
  }

  if (offlineCount) {
    actionable.unshift({
      kind: 'offline',
      key: 'offline-merged',
      count: offlineCount,
      message: offlineMessage || '当前为全离线模式。已按现有资料继续，模型核验未执行。',
    })
  }

  for (const [requirementId, reason] of uncoveredReasons) {
    if (!uncovered.some((item) => item.id === requirementId)) {
      uncovered.push(buildUncoveredRow(workflow, requirementId, reason))
    }
  }
  if (uncovered.length) {
    actionable.push({
      kind: 'uncovered',
      key: 'uncovered-merged',
      count: uncovered.length,
      message: `${uncovered.length} 项岗位要求在现有资料中未见对应覆盖`,
      requirements: uncovered,
    })
  }

  // Prefer actionable first; keep remaining detail notices for the foldout.
  const prioritized = [
    ...actionable.filter((item) => item.kind === 'action' && item.severity === 'ERROR'),
    ...actionable.filter((item) => !(item.kind === 'action' && item.severity === 'ERROR')),
  ]

  return { actionable: prioritized, details }
}

export function claimsNeedEvidenceCheck(workflow: WorkflowResponse): boolean {
  return workflow.claim_verification.some((row) => row.state === 'BLOCKED' || row.state === 'NEEDS_REVIEW')
}

export function isWorkflowBlocked(workflow: WorkflowResponse): boolean {
  return workflow.workflow_status === 'BLOCKED' || workflow.risk_result.action === 'BLOCKED'
}

export function collectTechDetails(workflow: WorkflowResponse): string[] {
  const lines: string[] = []
  const mapper = workflow.component_modes?.ats_form_mapper
  if (mapper) lines.push(`网申映射：${mapper === 'FIXTURE' ? '固定映射（演示表单）' : mapper}`)
  const parser = workflow.component_modes?.jd_parser
  if (parser) lines.push(`岗位解析：${parser}`)
  if (workflow.component_modes?.requested_parse_mode) {
    lines.push(`请求模式：${workflow.component_modes.requested_parse_mode}`)
  }
  for (const step of workflow.step_trace) {
    if (step.error) lines.push(`${step.step}：${zhText(step.error)}`)
    if (step.fallback_reason) lines.push(`${step.step} 回退：${zhText(step.fallback_reason)}`)
  }
  if (workflow.risk_result.risks.length) {
    lines.push(`完整检查记录 ${workflow.risk_result.risks.length} 条（见下方列表）`)
  }
  return lines
}

export function riskLabel(risk: RiskItem): string {
  return `${zhText(risk.message)} → ${zhText(risk.recommended_action)}（${zhText(risk.mitigation)}）`
}
