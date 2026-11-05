import type { ResumeExperienceEntry } from '../api/types'

export const REEL_DURATION = 24
export const REEL_OPEN = 3
export const REEL_CLOSE = 21

export interface ReelProject {
  id: string
  title: string
  role: string
  period: string
  excerpt: string
  body: string
  original: string
}

/** Presentation only. Quotes retain the source wording and never become verified claims. */
export function reelProjects(entries: ResumeExperienceEntry[]): ReelProject[] {
  return entries.filter(entry => entry.title?.trim() && entry.description?.trim()).map((entry, index) => {
    const original = entry.description.trim()
    const title = entry.title.trim()
    const research = original.search(/(?:研究|贡献)[：:]/)
    // PDF parsers often repeat title/publication/role, then hard-wrap each paragraph.
    // Remove that repeated header only when the source explicitly marks its research/body.
    const body = research > 0 && original.slice(0, research).includes(title)
      ? original.slice(research).replace(/\r?\n(?!\s*(?:研究|贡献)[：:])/g, '')
      : original
    const chars = Array.from(body)
    return {
      id: `${entry.id || 'project'}:${index}`,
      title,
      role: entry.role?.trim() || '',
      period: [entry.start?.trim(), entry.end?.trim()].filter(Boolean).join(' — '),
      excerpt: chars.slice(0, 86).join('') + (chars.length > 86 ? '…' : ''),
      body,
      original,
    }
  })
}

export function reelFrame(seconds: number, count: number) {
  const time = ((Number.isFinite(seconds) ? seconds : 0) % REEL_DURATION + REEL_DURATION) % REEL_DURATION
  const total = Math.max(1, Math.min(4, Math.trunc(count) || 1))
  const phase = time < REEL_OPEN ? 'open' : time >= REEL_CLOSE ? 'close' : 'project'
  const starts = Array.from({length: total}, (_, index) => projectStart(index, total))
  const index = Math.max(0, starts.findLastIndex(start => time >= start))
  const span = (starts[index + 1] ?? REEL_CLOSE) - starts[index]
  const start = phase === 'open' ? 0 : phase === 'close' ? REEL_CLOSE : starts[index]
  return { time, phase, index, local: time - start, span, progress: time / REEL_DURATION }
}

export function projectStart(index: number, count: number) {
  return (count === 4 ? [3, 7.5, 12, 16.5] : count === 3 ? [3, 11, 16] : count === 2 ? [3, 13] : [3])[index] ?? REEL_OPEN
}

export function motionAllowed(reduced: boolean, paused: boolean, visible: boolean, pageVisible: boolean) {
  return !reduced && !paused && visible && pageVisible
}
