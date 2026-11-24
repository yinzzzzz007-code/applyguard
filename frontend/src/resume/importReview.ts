import type { EditableResumeForm, ExtractedResumeForm } from '../api/types'
import { applyExtractedResume, emptyResumeForm, normalizeResumeForm, resumeSections, syncAwardText } from './formModel.ts'

export type RowSection = typeof resumeSections[number]
export type ImportRow = EditableResumeForm[RowSection][number]
type ProfileGroup = 'basic' | 'intention' | 'extras'
export type ImportChoice = { action: 'keep' | 'import' | 'both'; targetId?: string }
export type ImportChoices = Record<string, ImportChoice>
export interface RowReview { key: string; section: RowSection; row: ImportRow; candidates: ImportRow[]; unchanged: boolean }
export interface FieldReview { key: string; group: ProfileGroup; field: string; before: string; after: string }
export interface ImportReview { previous: EditableResumeForm; incoming: EditableResumeForm; rows: RowReview[]; fields: FieldReview[] }
const groups: ProfileGroup[] = ['basic', 'intention', 'extras']
const norm = (value: unknown) => String(value ?? '').normalize('NFKC').toLowerCase().replace(/\s+/g, '')
const values = (row: object) => row as Record<string, string>
const content = (row: object) => JSON.stringify(Object.entries(row).filter(([key]) => !['id', 'sourceExperienceId'].includes(key)).sort(([a], [b]) => a.localeCompare(b)))
function merged(old: ImportRow, row: ImportRow): ImportRow {
  return { ...old, ...Object.fromEntries(Object.entries(row).filter(([key, value]) => key !== 'id' && key !== 'sourceExperienceId' && typeof value === 'string' && value.trim())), id: old.id } as ImportRow
}
function related(section: RowSection, a: ImportRow, b: ImportRow) {
  const x = values(a), y = values(b)
  const compatible = (key: string) => !norm(x[key]) || !norm(y[key]) || norm(x[key]) === norm(y[key])
  if (section === 'education') return !!norm(x.school) && norm(x.school) === norm(y.school) && compatible('degree') && compatible('major')
  if (section === 'awards') return !!norm(x.name) && norm(x.name) === norm(y.name) && compatible('issuer')
  const titleA = norm(x.title || x.role), titleB = norm(y.title || y.role)
  return !!titleA && titleA === titleB && compatible('organization')
}
export function prepareImport(candidateId: string, extracted: ExtractedResumeForm, previous?: EditableResumeForm | null): ImportReview {
  const blank = { ...emptyResumeForm(candidateId), education: [], basic: { ...emptyResumeForm(candidateId).basic, idType: '' } }
  const incoming = applyExtractedResume(blank, extracted)
  const base = previous ? normalizeResumeForm(previous) : blank
  const rows: RowReview[] = []
  for (const section of resumeSections) {
    const seen = new Set<string>()
    for (const row of incoming[section]) {
      const signature = content(row)
      if (seen.has(signature)) continue
      seen.add(signature)
      const candidates = base[section].filter(old => related(section, row, old))
      const exact = candidates.find(old => content(merged(old, row)) === content(old))
      rows.push({ key: `${section}:${row.id}`, section, row, candidates: exact ? [exact] : candidates, unchanged: !!exact })
    }
  }
  const fields: FieldReview[] = []
  for (const group of groups) for (const [field, after] of Object.entries(incoming[group])) {
    if (group === 'extras' && field === 'awards') continue
    const before = values(base[group])[field] ?? ''
    if (after.trim() && before.trim() && after !== before) fields.push({ key: `${group}:${field}`, group, field, before, after })
  }
  return { previous: base, incoming, rows, fields }
}
export function pendingImport(review: ImportReview, choices: ImportChoices) {
  return review.fields.filter(field => !choices[field.key]).length + review.rows.filter(item => !item.unchanged && item.candidates.length > 0 &&
    (!choices[item.key] || (choices[item.key].action === 'import' && item.candidates.length > 1 && !item.candidates.some(row => row.id === choices[item.key].targetId)))).length
}
export function resolveImport(review: ImportReview, choices: ImportChoices): EditableResumeForm {
  if (pendingImport(review, choices)) throw new Error('请先确认有差异的资料。')
  const next = structuredClone(review.previous)
  for (const group of groups) for (const [field, value] of Object.entries(review.incoming[group])) {
    if ((group === 'extras' && field === 'awards') || !value.trim()) continue
    const key = `${group}:${field}`
    if (!values(next[group])[field]?.trim() || !review.fields.some(item => item.key === key) || choices[key]?.action === 'import') values(next[group])[field] = value
  }
  for (const item of review.rows) {
    if (item.unchanged) continue
    const choice = choices[item.key]
    if (choice?.action === 'keep') continue
    const rows = next[item.section] as ImportRow[]
    if (!item.candidates.length || choice?.action === 'both') rows.push(item.row)
    else {
      const target = choice?.targetId ?? item.candidates[0].id
      const index = rows.findIndex(row => row.id === target)
      if (index >= 0) rows[index] = merged(rows[index], item.row)
    }
  }
  next.extras.awards = syncAwardText(next.awards) || next.extras.awards
  return { ...next, dirty: false }
}
