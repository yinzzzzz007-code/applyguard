/** Demo UI copy: show Chinese to users; keep protocol enums as keys only. */

export const ZH_CLAIM: Record<string, string> = {
  VERIFIED: '已核验',
  NEEDS_REVIEW: '待复核',
  BLOCKED: '已阻断',
}

export const ZH_LEVEL: Record<string, string> = {
  L0: '一级·可填',
  L1: '二级·须看来源',
  L2: '三级·须确认',
  L3: '四级·敏感或阻断',
}

export const ZH_RISK: Record<string, string> = {
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
  BLOCK: '阻断',
}

export const ZH_ACTION: Record<string, string> = {
  CONFIRM: '确认',
  EDIT: '编辑',
  CANCEL: '取消',
  BLOCKED: '已阻断',
  REQUIRES_CONFIRMATION: '须确认',
  SAFE_TO_FILL: '可建议填写',
}

export const ZH_STEP: Record<string, string> = {
  'Career Vault': '经历库',
  'JD Parser': '岗位解析',
  'Evidence Matcher': '证据匹配',
  'Resume Selector': '简历挑选',
  'Claim Validator': '陈述核验',
  'ATS Form Mapper': '网申字段映射',
  'Risk Check': '风险检查',
  'Human Confirmation': '人工确认',
  'Audit Record': '审计记录',
}

export const ZH_STATUS: Record<string, string> = {
  COMPLETED: '已完成',
  BLOCKED: '已阻断',
  PENDING: '待处理',
  CREATED: '已创建',
  FAILED: '失败',
  SKIPPED: '已跳过',
}

export const ZH_WORKFLOW: Record<string, string> = {
  AWAITING_HUMAN_CONFIRMATION: '等待人工确认',
  BLOCKED: '已阻断',
}

export const ZH_EXEC: Record<string, string> = {
  DETERMINISTIC_FALLBACK: '规则回退',
  DETERMINISTIC_FIXTURE: '固定演示',
  DYNAMIC_MODEL: '模型路径',
}

export const ZH_PARSER: Record<string, string> = {
  MODEL: '模型解析',
  MODEL_SPAN_REPAIRED: '模型解析（已校正原文）',
  RULE_FALLBACK: '规则回退',
}

export const ZH_MAPPER: Record<string, string> = {
  FIXTURE: '固定映射',
}

export const ZH_STRENGTH: Record<string, string> = {
  STRONG: '强',
  MEDIUM: '中',
  WEAK: '弱',
}

export const ZH_REQ_TYPE: Record<string, string> = {
  HARD: '硬性',
  PREFERRED: '加分',
}

export const ZH_CATEGORY: Record<string, string> = {
  SKILL: '技能',
  EXPERIENCE: '经历',
  EDUCATION: '学历',
  RESPONSIBILITY: '职责',
  OTHER: '其他',
}

export const ZH_DECISION: Record<string, string> = {
  confirm: '已确认',
  reject: '已拒绝',
  edit: '已编辑',
}

export const ZH_FRESHNESS: Record<string, string> = {
  as_returned: '与返回一致',
  edited_pending_reverify: '已改待重核',
  rejected: '已拒绝',
}

export const ZH_CLAIM_STATUS: Record<string, string> = {
  DRAFT: '草稿',
  SELECTED: '已选入',
  BLOCKED: '已阻断',
}

const PHRASE: Array<[RegExp | string, string]> = [
  ['parse_mode=offline', '离线规则'],
  ['parse_mode=dynamic', '模型解析'],
  ['parse_mode: offline', '离线规则'],
  ['Blocked content must be corrected before review.', '阻断内容须先修正，才能进入复核。'],
  ['APPLICATION_DRAFT_BLOCKED', '申请草稿已阻断'],
  ['APPLICATION_DRAFT_PREPARED', '申请草稿已备好'],
  ['INSUFFICIENT_EVIDENCE', '证据不足'],
  ['no match was ready for selection', '没有达到可写入门槛的匹配'],
  ['MANUAL_ADD', '手动加入'],
  ['MANUAL_REMOVE', '手动移出'],
  ['ready_for_selection', '可写入'],
  ['unsupported_block', '不支持阻断'],
  ['timeout_fallback', '超时回退'],
  ['Skill overlap', '技能重合'],
  ['Responsibility overlap', '职责重合'],
  ['Linked evidence', '关联证据'],
  ['Conflict penalty applied', '已计入冲突扣分'],
  ['Missing-evidence penalty applied', '已计入缺证扣分'],
  [': none', ': 无'],
  [/JD requirement req_0*(\d+)/g, '岗位要求 $1'],
  [/ATS field /g, '网申字段'],
  [/B matching did not establish a ready, conflict-free selection\./g, '匹配未形成可写入、无冲突的选择。'],
  [/has no ready evidence\./g, '没有达到可写入门槛的证据。'],
  [/is missing; its value must not be guessed\./g, '缺失，不得猜测其取值。'],
  [/needs the user's own answer\./g, '须由用户本人作答。'],
  [/is blocked or references an unverified claim ID\./g, '被阻断，或引用了未核验的陈述。'],
  [/ATS mapping is inconsistent\./g, '网申映射不一致。'],
  ['Review the evidence and correct the claim before filling.', '填写前请核对证据并修正陈述。'],
  ['Show the coverage gap; do not generate a claim for it without new evidence.', '展示覆盖缺口；没有新证据不要编造陈述。'],
  ['Ask the user to supply and confirm the value.', '请用户本人提供并确认该值。'],
  ['Do not infer sensitive values.', '不要推断敏感取值。'],
  ['Correct the field and verify every linked claim before continuing.', '继续前请修正该字段并核验所有关联陈述。'],
  ['Resolve mapping conflict.', '请先解决映射冲突。'],
  ['No experience has sufficiently verified, conflict-free evidence for selection.', '没有任何经历具备足够、已核验且无冲突的证据可供选入。'],
  ['work_authorization', '工作许可'],
  ['Candidate summary', '候选人摘要'],
  ['ATS_SIMULATOR', '网申模拟器'],
  ['applyguard-foundation', '申请护栏服务'],
  ['ok', '正常'],
]

export function zhLookup(map: Record<string, string>, value: string | null | undefined, fallback?: string): string {
  if (!value) return fallback ?? '—'
  return map[value] ?? fallback ?? value
}

export function zhText(input: string | null | undefined): string {
  if (!input) return ''
  let out = input
  for (const [from, to] of PHRASE) {
    out = typeof from === 'string' ? out.split(from).join(to) : out.replace(from, to)
  }
  return out
}
