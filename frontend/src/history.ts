import type { AggregateRiskLevel, WorkflowResponse } from './api/types'

const STORAGE_KEY = 'applyguard.applicationHistory.v1'
const MAX_RECORDS = 30

export type HistoryOutcome = 'SIMULATED_CONFIRMED' | 'BLOCKED_REVIEWED'

export interface ApplicationHistoryEntry {
  id: string
  recordedAt: string
  applicationId: string
  traceId: string
  title: string
  company: string
  riskLevel: AggregateRiskLevel
  outcome: HistoryOutcome
  source: string
}

export function loadApplicationHistory(storage?: Pick<Storage, 'getItem'>): ApplicationHistoryEntry[] {
  try {
    const target = storage ?? localStorage
    const value: unknown = JSON.parse(target.getItem(STORAGE_KEY) ?? '[]')
    if (!Array.isArray(value)) return []
    return value.filter((entry): entry is ApplicationHistoryEntry =>
      typeof entry === 'object' && entry !== null &&
      typeof entry.id === 'string' && typeof entry.applicationId === 'string' &&
      typeof entry.recordedAt === 'string' && typeof entry.outcome === 'string')
  } catch {
    return []
  }
}

export function saveApplicationHistory(
  workflow: WorkflowResponse,
  outcome: HistoryOutcome,
  storage?: Pick<Storage, 'getItem' | 'setItem'>,
): boolean {
  const entry: ApplicationHistoryEntry = {
    id: crypto.randomUUID(),
    recordedAt: new Date().toISOString(),
    applicationId: workflow.application_id,
    traceId: workflow.trace_id,
    title: workflow.parsed_jd.title,
    company: workflow.parsed_jd.company,
    riskLevel: workflow.risk_result.risk_level,
    outcome,
    source: workflow._prerecorded ? `预录：${workflow._prerecorded.case}` : '本机后端',
  }
  try {
    const target = storage ?? localStorage
    target.setItem(STORAGE_KEY, JSON.stringify([entry, ...loadApplicationHistory(target)].slice(0, MAX_RECORDS)))
    return true
  } catch {
    return false
  }
}

export function removeApplicationHistory(
  id: string,
  storage?: Pick<Storage, 'getItem' | 'setItem'>,
): boolean {
  try {
    const target = storage ?? localStorage
    target.setItem(STORAGE_KEY, JSON.stringify(loadApplicationHistory(target).filter((entry) => entry.id !== id)))
    return true
  } catch {
    return false
  }
}
