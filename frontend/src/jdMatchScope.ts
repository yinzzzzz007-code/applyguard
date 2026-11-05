/** Same section boundaries as backend/services/jd_match_scope.py. */

export type QualificationKind = 'requirement' | 'bonus'

export interface SectionSpan {
  kind: QualificationKind | 'description' | 'other'
  start: number
  end: number
}

const HEADER =
  /^\s*(?:[【\[（(]\s*)?(?:(?:[一二三四五六七八九十]+|\d{1,2})\s*[、.．]\s*)?(加分项或注意事项|加分项|优先条件|nice[\s-]to[\s-]have|preferred(?:\s+(?:qualifications|requirements|skills))?|bonus|任职资格|任职要求|岗位要求|基本要求|required(?:\s+(?:qualifications|skills))?|requirements|qualifications|职位描述|岗位描述|工作职责|岗位职责|工作内容|job\s+description|responsibilities|职责|面向对象|招聘对象)\s*(?:[】\])）)])?\s*[:：]?(?=\s|$)/i

const BONUS = new Set(['加分项或注意事项', '加分项', '优先条件', 'nice to have', 'nice-to-have', 'bonus'])
const DESCRIPTION = new Set([
  '职位描述',
  '岗位描述',
  '工作职责',
  '岗位职责',
  '工作内容',
  '职责',
  'job description',
  'responsibilities',
])
const OTHER = new Set(['面向对象', '招聘对象'])

export function sectionSpans(source: string): SectionSpan[] | null {
  if (!source) return null
  const headers = collectHeaders(source)
  const kinds = new Set(headers.map((header) => header.kind))
  if (!kinds.has('requirement') && !kinds.has('bonus')) {
    return kinds.has('description') ? [] : null
  }
  return headers.flatMap((header, index) => {
    if (header.kind !== 'requirement' && header.kind !== 'bonus') return []
    const end = index + 1 < headers.length ? headers[index + 1].start : source.length
    return [{ kind: header.kind, start: header.start, end }]
  })
}

export function quoteKind(
  source: string,
  quote: string,
): QualificationKind | 'out' | 'unsectioned' {
  const spans = sectionSpans(source)
  if (spans === null) return 'unsectioned'
  if (!quote || !spans.length) return 'out'
  let from = 0
  while (from <= source.length) {
    const index = source.indexOf(quote, from)
    if (index < 0) return 'out'
    const end = index + quote.length
    const hit = spans.find((span) => span.start <= index && end <= span.end)
    if (hit?.kind === 'requirement' || hit?.kind === 'bonus') return hit.kind
    from = index + 1
  }
  return 'out'
}

export function indexesInScope(
  source: string,
  quote: string,
  kinds: QualificationKind[] | null,
): number[] {
  if (!quote) return []
  const spans = kinds ? sectionSpans(source) : null
  const found: number[] = []
  let from = 0
  while (from <= source.length) {
    const index = source.indexOf(quote, from)
    if (index < 0) break
    const end = index + quote.length
    const allowed =
      spans === null ||
      spans.some(
        (span) =>
          !!kinds?.includes(span.kind as QualificationKind) &&
          span.start <= index &&
          end <= span.end,
      )
    if (allowed) found.push(index)
    from = index + Math.max(quote.length, 1)
  }
  return found
}

function collectHeaders(source: string): Array<{ start: number; kind: SectionSpan['kind'] }> {
  const headers: Array<{ start: number; kind: SectionSpan['kind'] }> = []
  let offset = 0
  const lines = source.split(/\r\n|\n|\r/)
  lines.forEach((line, index) => {
    const kind = headerKind(line)
    if (kind) headers.push({ start: offset, kind })
    offset += line.length
    if (index < lines.length - 1) {
      const breakAt = offset
      const pair = source.slice(breakAt, breakAt + 2)
      offset += pair === '\r\n' ? 2 : 1
    }
  })
  return headers
}

function headerKind(line: string): SectionSpan['kind'] | null {
  const matched = HEADER.exec(line)
  if (!matched) return null
  const label = matched[1].replace(/\s+/g, ' ').toLowerCase()
  if (OTHER.has(label)) return 'other'
  if (DESCRIPTION.has(label)) return 'description'
  if (BONUS.has(label) || label.startsWith('preferred')) return 'bonus'
  return 'requirement'
}
