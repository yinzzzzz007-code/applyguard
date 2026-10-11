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

export function stepIndex(step: FlowStep): number {
  return STEP_ORDER.indexOf(step)
}

export function stepFromPath(pathname: string): FlowStep {
  const found = STEP_ORDER.find((s) => STEP_META[s].path === pathname)
  return found ?? 'import'
}

export type { DemoScenario }
