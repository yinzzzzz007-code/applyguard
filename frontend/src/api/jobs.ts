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
export interface Opportunity extends JobTarget {
  location: string
  education: string
  experience: string
  recruitment_type: string
  description: string
  stage: 'saved' | 'preparing' | 'archived'
  workflow_jd_text: string
  factors: JobFactor[]
}
export interface JobLibrary {
  items: Opportunity[]
  total: number
  stats: { open: number; unknown: number; reference: number; closed: number; analyzed_jobs: number; factors: Array<{ slug: string; label: string; jobs: number }> }
  notice: string
}
export interface JobAnalysis {
  job_id: string
  content_hash: string
  analyzed_at: string
  has_resume: boolean
  total: number
  supported: number
  requirements: Array<ParsedRequirement & { coverage: 'SUPPORTED' | 'NEEDS_EVIDENCE' | 'NO_MATCH'; evidence_ids: string[]; experience_ids: string[]; notes: string[] }>
  notice: string
}
export interface RadarPage {
  items: Array<{ id: number; title: string; company: string; location: string; url: string; last_seen_at: string }>
  total: number
  offset: number
  notice: string
}
export interface ImportResult { created: number; updated: number; unchanged: number; items: Opportunity[] }

export async function jobsRequest<T>(path = '', body?: unknown): Promise<T> {
  const base = (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
  let response: Response
  try {
    response = await fetch(`${base}/api/v1/jobs${path}`, body === undefined ? undefined : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
  } catch { throw new Error('无法连接本机后端，请确认服务已启动。') }
  const result = await response.json().catch(() => ({ error: { message: '后端未返回有效 JSON，请重启更新后的后端。' } }))
  if (!response.ok || result.error) throw new Error(result.error?.message ?? `请求失败（${response.status}）`)
  if (body !== undefined && !path.endsWith('/analyze')) window.dispatchEvent(new Event('applyguard:jobs-changed'))
  return result as T
}

export function analyzeOpportunity(id: string, resume: EditableResumeForm | null) {
  return jobsRequest<JobAnalysis>(`/${id}/analyze`, { resume_draft: resume })
}
