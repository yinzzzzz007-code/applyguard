import type { Opportunity } from './api/jobs'

export const JOB_STATUS: Record<string, string> = { open: '来源标记在招', unknown: '状态待核对', closed: '已关闭', reference: '参考快照' }
export const JOB_STAGE: Record<string, string> = { saved: '已收藏', preparing: '准备申请', archived: '已归档' }

export function canPrepareJob(job: Pick<Opportunity, 'stage' | 'status'>): boolean {
  return job.stage !== 'archived' && ['open', 'unknown'].includes(job.status)
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
