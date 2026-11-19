import type { Opportunity } from './api/jobs'

export const JOB_STATUS: Record<string, string> = { open: '来源标记在招', unknown: '状态待核对', closed: '已关闭', reference: '参考快照' }
export const JOB_STAGE: Record<string, string> = { saved: '已收藏', preparing: '准备申请', archived: '已归档' }

export function canPrepareJob(job: Pick<Opportunity, 'stage' | 'status' | 'details_available'>): boolean {
  return job.details_available !== false && job.stage !== 'archived' && ['open', 'unknown'].includes(job.status)
}

export function parseJobImport(text: string): unknown[] {
  if (new TextEncoder().encode(text).length > 1_900_000) throw new Error('文件过大，请分成每批最多 100 个岗位。')
  let parsed: unknown
  try { parsed = JSON.parse(text) }
  catch {
    try { parsed = text.split(/\r?\n/).filter((line) => line.trim()).map((line) => JSON.parse(line)) }
    catch { throw new Error('文件不是有效 JSON 或 JSONL。') }
  }
  const value = parsed as { items?: unknown; jobs?: unknown }
  const rows = Array.isArray(parsed) ? parsed : value?.items ?? value?.jobs
  if (!Array.isArray(rows) || !rows.length || rows.length > 100) throw new Error('需要包含 1 至 100 条完整 JD 的数组，或带 items/jobs 的对象。')
  return rows
}

export function importMessage(result: { created: number; updated: number; unchanged: number }): string {
  return `导入完成：新增 ${result.created}，更新 ${result.updated}，未变化 ${result.unchanged}。`
}

export type JobScope = 'active' | 'preparing' | 'archived' | 'all'
export type JobSort = 'match' | 'newest' | 'company'
export function filterJobs<T extends Pick<Opportunity,'title'|'company'|'location'|'description'|'status'|'stage'|'imported_at'|'match_score'|'match_level'|'match_reasons'>>(
  items:T[], query:string, scope:JobScope, status:string, sort:JobSort,
):T[] {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  return items.filter(job => {
    const inScope = scope === 'all' || (scope === 'archived' ? job.stage === 'archived' : scope === 'preparing' ? job.stage === 'preparing' : job.stage !== 'archived')
    const text = [job.title,job.company,job.location,job.description].join(' ').toLocaleLowerCase()
    return inScope && (status === 'all' || job.status === status) && terms.every(term => text.includes(term))
  }).sort((a,b) => {
    if (sort === 'company') {
      return a.company.localeCompare(b.company,'zh-CN') || a.title.localeCompare(b.title,'zh-CN')
    }
    if (sort === 'match') {
      const scoreA = a.match_score ?? a.match_reasons?.score ?? -1
      const scoreB = b.match_score ?? b.match_reasons?.score ?? -1
      if (scoreA !== scoreB) return scoreB - scoreA
      const levelA = a.match_level ?? a.match_reasons?.level ?? 'insufficient'
      const levelB = b.match_level ?? b.match_reasons?.level ?? 'insufficient'
      const rank = { high: 3, medium: 2, low: 1, insufficient: 0 }
      if (rank[levelA] !== rank[levelB]) return rank[levelB] - rank[levelA]
    }
    return (Date.parse(b.imported_at) || 0) - (Date.parse(a.imported_at) || 0)
  })
}
