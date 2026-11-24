import type { EditableResumeForm, ResumeParseResult, ResumeImportSuggestion } from '../api/types'
import { prepareImport, resolveImport, type ImportChoices, type ImportRow } from './importReview.ts'
import { newExperienceId, syncAwardText } from './formModel.ts'

const key = 'applyguard.resume-transfer.v1'
export interface ResumeTransfer { id: string; result: ResumeParseResult }
export function queueResumeImport(result: ResumeParseResult) {
  sessionStorage.setItem(key, JSON.stringify({ id: newExperienceId('transfer'), result }))
}
export function readResumeTransfer(): ResumeTransfer | null {
  try {
    const item = JSON.parse(sessionStorage.getItem(key) ?? 'null')
    return item?.id && item.result?.form?.basic && Array.isArray(item.result.form.projects) ? item : null
  } catch { return null }
}
export function finishResumeTransfer(form: EditableResumeForm) {
  const queued = readResumeTransfer()
  if (!queued || queued.id !== form.importContext?.transferId) return
  sessionStorage.setItem('applyguard.resume-edit.v1', JSON.stringify(form))
  sessionStorage.removeItem(key)
}
export function stageResumeImport(base: EditableResumeForm, transfer: ResumeTransfer): EditableResumeForm {
  if (base.importContext?.transferId === transfer.id) return base
  const previous = { ...base, education: base.education.filter(row => row.id !== 'edu_1' || Object.entries(row).some(([key,value]) => key !== 'id' && typeof value === 'string' && value.trim())) }
  const review = prepareImport(base.candidateId, transfer.result.form, previous)
  const choices: ImportChoices = {}
  const suggestions: ResumeImportSuggestion[] = []
  for (const field of review.fields) {
    choices[field.key] = { action: 'keep' }
    suggestions.push({ id: newExperienceId('suggestion'), group: field.group, field: field.field, before: field.before, after: field.after })
  }
  for (const item of review.rows) if (!item.unchanged && item.candidates.length) {
    choices[item.key] = { action: 'keep' }
    suggestions.push({ id: newExperienceId('suggestion'), section: item.section, row: item.row, candidateIds: item.candidates.map(row => row.id) })
  }
  const combined = [...(base.importContext?.suggestions ?? []), ...suggestions]
  const unique = combined.filter((item, index) => {
    const signature = (value: ResumeImportSuggestion) => JSON.stringify({ ...value, id: '', row: value.row ? { ...value.row, id: '' } : undefined })
    return combined.findIndex(other => signature(other) === signature(item)) === index
  })
  return { ...resolveImport(review, choices), dirty: true, importContext: {
    transferId: transfer.id, filename: transfer.result.filename, extractor: transfer.result.extractor,
    text: transfer.result.source_text ?? transfer.result.preview, suggestions: unique,
  } }
}
export function applyImportSuggestion(form: EditableResumeForm, id: string, action: 'keep' | 'use' | 'new', targetId?: string): EditableResumeForm {
  const next = structuredClone(form)
  const suggestion = next.importContext?.suggestions.find(item => item.id === id)
  if (!suggestion || !next.importContext) return form
  if (action !== 'keep') {
    if (suggestion.section && suggestion.row) {
      const rows = next[suggestion.section] as ImportRow[]
      if (action === 'new') rows.push({ ...suggestion.row, id: newExperienceId(suggestion.section) })
      else {
        const index = rows.findIndex(row => row.id === targetId && suggestion.candidateIds?.includes(row.id))
        if (index < 0) return form
        const old = rows[index]
        rows[index] = { ...old, ...Object.fromEntries(Object.entries(suggestion.row).filter(([field, value]) => field !== 'id' && field !== 'sourceExperienceId' && typeof value === 'string' && value.trim())), id: old.id } as ImportRow
      }
      next.extras.awards = syncAwardText(next.awards) || next.extras.awards
    } else if (suggestion.group && suggestion.field && suggestion.after !== undefined) {
      (next[suggestion.group] as unknown as Record<string, string>)[suggestion.field] = suggestion.after
    }
  }
  next.importContext.suggestions = next.importContext.suggestions.filter(item => item.id !== id)
  return { ...next, dirty: true }
}
