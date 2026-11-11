import type { EvidenceSourceFile, EvidenceSpan } from '../api/types'

export function orderedEvidenceSpans(spans: EvidenceSpan[]): EvidenceSpan[] {
  return [...spans].sort((a, b) => (a.page ?? 1) - (b.page ?? 1)
    || (a.line_start ?? Number.MAX_SAFE_INTEGER) - (b.line_start ?? Number.MAX_SAFE_INTEGER))
}

export function materialType(file: EvidenceSourceFile): string {
  const path = file.relative_path.toLowerCase()
  if (file.media_type?.startsWith('image/') || /\.(png|jpe?g|webp|gif)$/.test(path)) return '图片'
  if (path.endsWith('.pdf') || file.media_type === 'application/pdf') return 'PDF'
  if (/\.docx?$/.test(path) || file.media_type?.includes('word')) return 'Word'
  if (/\.(md|markdown)$/.test(path)) return 'Markdown'
  return '其他'
}

export function materialStatus(file: EvidenceSourceFile): { key: string; label: string; hint: string } {
  if (file.state === 'FAILED') return { key: 'failed', label: '识别失败', hint: '可以查看原件或重新识别；识别失败不等于关联失败。' }
  if (file.state === 'PARSING' || file.state === 'PENDING') return { key: 'processing', label: '处理中', hint: '正在提取文件内容，请稍候。' }
  if (file.evidence_review_state === 'STALE' || file.state === 'STALE') return { key: 'review', label: '需重新确认内容', hint: '材料有更新，请重新确认识别内容后再关联。' }
  if (file.evidence_review_state === 'REVIEWED') return { key: 'reviewed', label: '识别完成', hint: '内容已确认。关联经历与字段是否获支持是另一步。' }
  if (file.state === 'INDEXED') return { key: 'reviewed', label: '识别完成', hint: '内容已确认。关联经历与字段是否获支持是另一步。' }
  if (file.parse_error || (!file.recognition_saved && !file.ocr_text_preview?.trim())) return { key: 'manual', label: '需人工查看', hint: '暂无可用识别结果。请查看原件，需要时补充提取字段。' }
  return { key: 'review', label: '已提取，待确认', hint: '已提取文字，请对照原件确认内容；确认后才能关联经历。' }
}

export const materialName = (path: string) => path.replace(/\\/g, '/').split('/').pop() || path
export const materialFolder = (path: string) => path.replace(/\\/g, '/').split('/').slice(0, -1).join('/')
