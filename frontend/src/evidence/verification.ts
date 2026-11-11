/** Experience-typed verification helpers. Material kind ≠ experience type. */

export type ExperienceTargetType = 'project' | 'internship' | 'award'

export type FieldCheckStatus = 'SUPPORTED' | 'NOT_MENTIONED' | 'CONFLICT' | 'PENDING'

export interface FieldCheck {
  key: string
  label: string
  experience_value: string
  status: FieldCheckStatus | string
  status_label?: string
  quote?: string
  quote_available?: boolean
  quote_note?: string
  source?: string
}

export const FIELD_STATUS_LABELS: Record<string, string> = {
  SUPPORTED: '支持',
  NOT_MENTIONED: '未提及',
  CONFLICT: '冲突',
  PENDING: '待确认',
}

export const MATERIAL_KIND_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'AWARD_CERTIFICATE', label: '获奖证书' },
  { value: 'INTERNSHIP_CERTIFICATE', label: '实习证明' },
  { value: 'PROJECT_REPORT', label: '项目报告' },
  { value: 'CODE_REPO', label: '代码仓库说明' },
  { value: 'WORK_PRODUCT', label: '工作成果' },
  { value: 'CERTIFICATE', label: '通用证书' },
  { value: 'DOCUMENT', label: '其他材料' },
]

export const MATERIAL_EDITOR_FIELDS: Record<string, Array<[string, string]>> = {
  AWARD_CERTIFICATE: [
    ['recipient', '获奖人 / 持有人'],
    ['award_name', '证书 / 奖项名称'],
    ['grade', '级别'],
    ['issuer', '颁发单位'],
    ['date', '日期'],
  ],
  CERTIFICATE: [
    ['recipient', '获奖人 / 持有人'],
    ['award_name', '证书 / 奖项名称'],
    ['grade', '级别'],
    ['issuer', '颁发单位'],
    ['date', '日期'],
  ],
  INTERNSHIP_CERTIFICATE: [
    ['company', '公司'],
    ['department', '部门'],
    ['title', '岗位'],
    ['period', '实习时间'],
    ['issuer', '证明出具方'],
  ],
  PROJECT_REPORT: [
    ['name', '项目 / 成果名称'],
    ['organization', '所属组织'],
    ['role', '个人角色'],
    ['period', '时间'],
    ['tech_stack', '技术栈'],
    ['outcomes', '成果与指标'],
  ],
  CODE_REPO: [
    ['name', '项目 / 成果名称'],
    ['organization', '所属组织'],
    ['role', '个人角色'],
    ['period', '时间'],
    ['tech_stack', '技术栈'],
    ['outcomes', '成果与指标'],
  ],
  WORK_PRODUCT: [
    ['name', '项目 / 成果名称'],
    ['organization', '所属组织'],
    ['role', '个人角色'],
    ['period', '时间'],
    ['tech_stack', '技术栈'],
    ['outcomes', '成果与指标'],
  ],
  DOCUMENT: [
    ['material_label', '材料标题'],
    ['organization', '相关组织'],
    ['period', '相关时间'],
  ],
}

export const EXPERIENCE_FIELD_SCHEMAS: Record<ExperienceTargetType, Array<[string, string]>> = {
  project: [
    ['name', '名称'],
    ['period', '时间'],
    ['organization', '所属组织'],
    ['role', '个人角色'],
    ['responsibilities', '负责工作'],
    ['tech_stack', '技术栈'],
    ['outcomes', '成果与指标'],
  ],
  internship: [
    ['company', '公司'],
    ['department', '部门'],
    ['title', '岗位'],
    ['period', '时间'],
    ['duties', '职责'],
    ['outcomes', '工作产出与指标'],
  ],
  award: [
    ['award_name', '奖项名称'],
    ['issuer', '颁发单位'],
    ['grade', '级别'],
    ['date', '获奖时间'],
    ['recipient', '获奖人或团队'],
  ],
}

export function materialKindLabel(kind?: string | null): string {
  return MATERIAL_KIND_OPTIONS.find((item) => item.value === kind)?.label || kind || '其他材料'
}

export function editorFieldsForKind(kind?: string | null): Array<[string, string]> {
  return MATERIAL_EDITOR_FIELDS[kind || 'DOCUMENT'] || MATERIAL_EDITOR_FIELDS.DOCUMENT
}

export function statusLabel(status?: string | null): string {
  return FIELD_STATUS_LABELS[status || ''] || status || '待确认'
}

export function recognitionLabel(reviewState?: string | null, hasEvidence?: boolean): string {
  if (!hasEvidence) return '未识别'
  if (reviewState === 'REVIEWED') return '识别完成'
  if (reviewState === 'STALE') return '需重新识别'
  return '已提取，待确认内容'
}

export function associationLabel(status?: string | null): string {
  if (status === 'LINKED') return '关联完成'
  if (status === 'MATCHED' || status === 'NEEDS_CONFIRM') return '仅推荐，未确认'
  if (status === 'CONFLICT') return '关联冲突'
  return '未关联'
}

export function supportSummary(checks: FieldCheck[] | undefined): string {
  if (!checks?.length) return '无核对项'
  const counts = { SUPPORTED: 0, NOT_MENTIONED: 0, CONFLICT: 0, PENDING: 0 }
  for (const row of checks) {
    const key = (row.status in counts ? row.status : 'PENDING') as keyof typeof counts
    counts[key] += 1
  }
  const parts: string[] = []
  if (counts.SUPPORTED) parts.push(`支持 ${counts.SUPPORTED}`)
  if (counts.NOT_MENTIONED) parts.push(`未提及 ${counts.NOT_MENTIONED}`)
  if (counts.CONFLICT) parts.push(`冲突 ${counts.CONFLICT}`)
  if (counts.PENDING) parts.push(`待确认 ${counts.PENDING}`)
  return parts.join(' · ') || '无核对项'
}
