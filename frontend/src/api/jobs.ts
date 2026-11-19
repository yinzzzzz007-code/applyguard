import type { EditableResumeForm, ParsedRequirement } from './types'

export interface JobFactor {
  slug: string
  label: string
  category: string
  evidence: Array<{ text: string; terms: string[] }>
}
export interface JobTarget {
  id: string
  content_hash: string
  version: number
  title: string
  company: string
  url: string
  status: string
  source_kind: string
  source_observed_at: string
  imported_at: string
}
export type ProfileCheck = { label: string; value: string; state: 'MATCH' | 'MISMATCH' | 'UNKNOWN' | 'DECLARED' }
export type ProfileChecks = Record<string, ProfileCheck[]>

export interface Opportunity extends JobTarget {
  location: string
  education: string
  experience: string
  recruitment_type: string
  salary?: { min: number; max: number; currency: string; unit: string }
  internship_schedule?: { days_per_week: number; duration_months: number }
  graduation_window?: { class_year?: number; start_date: string; end_date: string }
  description: string
  stage: 'saved' | 'preparing' | 'archived'
  workflow_jd_text: string
  factors: JobFactor[]
  source_id?: string
  source_url?: string
  first_seen_at?: string
  last_changed_at?: string
  published_at?: string
  is_new?: boolean
  unread?: boolean
  details_available?: boolean
  match_level?: JobMatch['level']
  match_reasons?: JobMatch
}
export interface JobMatch {
  score: number | null
  level: 'high' | 'medium' | 'low' | 'insufficient'
  reasons: string[]
  missing: string[]
  ai_score?: number
  ai_explanation?: string
}
export const MATCH_LABELS: Record<JobMatch['level'], string> = { high: '高匹配', medium: '中匹配', low: '低匹配', insufficient: '信息不足' }
export const OFFICIAL_SOURCES = { baidu: '百度', huawei: '华为', bytedance_seed: '字节跳动 Seed' }
export interface JobSource {
  source_id: string
  name: string
  company: string
  url: string
  enabled: boolean
  interval_hours: number
  last_success_at: string | null
  last_error: string | null
  consecutive_failures: number
  job_count: number
  details_count: number
  next_refresh_at: string
}
type RefreshRun = { id: string; sources: string[]; result: Record<string, { created: number; updated: number; closed: number; skipped: number; error?: string }>; finished_at?: string }
export interface RefreshStatus {
  state: 'waiting' | 'running' | 'success' | 'partial' | 'failed' | 'interrupted'
  current: RefreshRun | null
  last: RefreshRun | null
  next_refresh_at: string | null
}
export interface JobAlert { event_key: string; source_id: string; job_id: string | null; kind: string; reason: string; title: string | null; created_at: string }
export interface JobLibrary {
  items: Opportunity[]
  total: number
  stats: { open: number; unknown: number; reference: number; closed: number; analyzed_jobs: number; factors: Array<{ slug: string; label: string; jobs: number }> }
  notice: string
  ai_matching?: boolean
}
export interface JobAnalysis {
  job_id: string
  content_hash: string
  analyzed_at: string
  has_resume: boolean
  total: number
  supported: number
  excluded?: number
  profile_checks?: ProfileChecks
  requirements: Array<ParsedRequirement & { coverage: 'SUPPORTED' | 'NEEDS_EVIDENCE' | 'NO_MATCH' | 'PROFILE_REPORTED' | 'REVIEW_REQUIRED'; evidence_ids: string[]; experience_ids: string[]; notes: string[] }>
  notice: string
}
export interface RadarPage {
  items: Array<{ id: number; title: string; company: string; location: string; url: string; last_seen_at: string }>
  total: number
  offset: number
  notice: string
}
export interface ImportResult { created: number; updated: number; unchanged: number; items: Opportunity[] }

export async function jobsRequest<T>(path = '', body?: unknown, method: 'GET' | 'POST' | 'PATCH' | 'DELETE' = body === undefined ? 'GET' : 'POST'): Promise<T> {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  let response: Response
  try {
    response = await fetch(`${base}/api/v1/jobs${path}`, {
      method,
      ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    })
  } catch { throw new Error('无法连接本机后端，请确认服务已启动。') }
  const result = await response.json().catch(() => ({ error: { message: '后端未返回有效 JSON，请重启更新后的后端。' } }))
  if (!response.ok || result.error) throw new Error(result.error?.message ?? `请求失败（${response.status}）`)
  if (method !== 'GET' && !path.endsWith('/analyze')) window.dispatchEvent(new Event('applyguard:jobs-changed'))
  return result as T
}

export function analyzeOpportunity(id: string, resume: EditableResumeForm | null) {
  return jobsRequest<JobAnalysis>(`/${id}/analyze`, { resume_draft: resume })
}
