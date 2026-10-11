import type { DemoScenario } from './api/types'

export type FlowStep =
  | 'import'
  | 'vault'
  | 'jd'
  | 'match'
  | 'resume'
  | 'claims'
  | 'ats'
  | 'confirm'

export const STEP_META: Record<FlowStep, { label: string; path: string }> = {
  import: { label: '简历识别', path: '/' },
  vault: { label: '经历库', path: '/vault' },
  jd: { label: '岗位说明', path: '/jd' },
  match: { label: '证据匹配', path: '/match' },
  resume: { label: '简历审查', path: '/resume' },
  claims: { label: '陈述核验', path: '/claims' },
  ats: { label: '网申模拟', path: '/ats' },
  confirm: { label: '人工确认', path: '/confirm' },
}

export const STEP_ORDER: FlowStep[] = [
  'import',
  'vault',
  'jd',
  'match',
  'resume',
  'claims',
  'ats',
  'confirm',
]

/** Routes outside the main wizard — must NOT collapse step highlight back to「简历识别」. */
const NON_FLOW_PATHS = new Set(['/evidence', '/history'])

const MAX_STEP_KEY = 'applyguard.flow.maxStep'

export function stepIndex(step: FlowStep): number {
  return STEP_ORDER.indexOf(step)
}

export function stepFromPath(pathname: string): FlowStep | null {
  const clean = pathname.split('?')[0] || '/'
  if (NON_FLOW_PATHS.has(clean)) return null
  const found = STEP_ORDER.find((s) => STEP_META[s].path === clean)
  return found ?? null
}

export function loadMaxStep(): FlowStep {
  try {
    const raw = sessionStorage.getItem(MAX_STEP_KEY) as FlowStep | null
    if (raw && STEP_ORDER.includes(raw)) return raw
  } catch {
    /* ignore */
  }
  return 'vault'
}

export function rememberMaxStep(step: FlowStep): FlowStep {
  const prev = loadMaxStep()
  const next = stepIndex(step) > stepIndex(prev) ? step : prev
  try {
    sessionStorage.setItem(MAX_STEP_KEY, next)
  } catch {
    /* ignore */
  }
  return next
}

export type { DemoScenario }
