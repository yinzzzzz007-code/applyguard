import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import type { EvidenceMatchItem, ParsedRequirement } from '../api/types'
import { EmptyState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { ZH_CATEGORY, ZH_REQ_TYPE, ZH_STRENGTH, zhLookup, zhText } from '../i18n'

type MatchTone = 'strong' | 'medium' | 'conflict' | 'uncovered'

type ReqView = {
  requirement: ParsedRequirement
  tone: MatchTone
  label: string
  best?: EvidenceMatchItem
  uncoveredReason?: string
}

type HlSpan = {
  start: number
  end: number
  reqId: string
  tone: MatchTone
}

function toneForMatch(best: EvidenceMatchItem | undefined): MatchTone {
  // Color by actual match strength. Backend may still list MEDIUM rows under
  // uncovered_requirements when they are not ready_for_selection — that is not "无匹配".
  if (!best) return 'uncovered'
  if (best.conflicts?.length) return 'conflict'
  if (best.evidence_strength === 'STRONG' || best.ready_for_selection) return 'strong'
  if (best.evidence_strength === 'MEDIUM' || best.relevance_score >= 0.35) return 'medium'
  if (best.evidence_strength === 'WEAK' || best.relevance_score > 0) return 'medium'
  return 'uncovered'
}

function toneLabel(tone: MatchTone): string {
  switch (tone) {
    case 'strong':
      return '强匹配'
    case 'medium':
      return '弱匹配'
    case 'conflict':
      return '有冲突'
    case 'uncovered':
      return '未覆盖'
  }
}

function pickNeedle(jdText: string, req: ParsedRequirement): string | null {
  const candidates = [req.evidence_text, req.text].filter(
    (s): s is string => typeof s === 'string' && s.trim().length >= 4,
  )
  for (const c of candidates) {
    if (jdText.includes(c)) return c
  }
  return null
}

/** Longest-first, non-overlapping spans inside JD source. */
function buildHighlights(jdText: string, views: ReqView[]): HlSpan[] {
  const raw: HlSpan[] = []
  for (const v of views) {
    const needle = pickNeedle(jdText, v.requirement)
    if (!needle) continue
    let from = 0
    while (from < jdText.length) {
      const idx = jdText.indexOf(needle, from)
      if (idx < 0) break
      raw.push({
        start: idx,
        end: idx + needle.length,
        reqId: v.requirement.requirement_id,
        tone: v.tone,
      })
      from = idx + needle.length
    }
  }
  raw.sort((a, b) => b.end - b.start - (a.end - a.start) || a.start - b.start)
  const chosen: HlSpan[] = []
  for (const span of raw) {
    if (chosen.some((c) => !(span.end <= c.start || span.start >= c.end))) continue
    chosen.push(span)
  }
  return chosen.sort((a, b) => a.start - b.start)
}

function HighlightedJd({ jdText, spans, onOpen }: {
  jdText: string
  spans: HlSpan[]
  onOpen: (reqId: string) => void
}): ReactNode[] {
  if (!jdText) return ['（无岗位原文，仅有解析结果）']
  const nodes: ReactNode[] = []
  let cursor = 0
  spans.forEach((span, i) => {
    if (span.start > cursor) {
      nodes.push(jdText.slice(cursor, span.start))
    }
    nodes.push(
      <button
        type="button"
        key={`${span.reqId}-${span.start}-${i}`}
        className={`em-hl em-hl-${span.tone}`}
        aria-label={`查看要求匹配详情：${jdText.slice(span.start, span.end)}`}
        onClick={() => onOpen(span.reqId)}
      >
        {jdText.slice(span.start, span.end)}
      </button>,
    )
    cursor = span.end
  })
  if (cursor < jdText.length) nodes.push(jdText.slice(cursor))
  return nodes
}

export function EvidenceMatchPage() {
  const navigate = useNavigate()
  const { workflow } = useDemo()
  const [activeReqId, setActiveReqId] = useState<string | null>(null)
  const modalRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLElement | null>(null)
  const openRequirement = useCallback((id: string) => {
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setActiveReqId(id)
  }, [])
  const closeRequirement = useCallback(() => {
    setActiveReqId(null)
    triggerRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!activeReqId) return
    const modal = modalRef.current
    modal?.querySelector<HTMLElement>('button')?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRequirement()
      }
      if (event.key !== 'Tab' || !modal) return
      const focusable = [...modal.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled])')]
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [activeReqId, closeRequirement])

  const views = useMemo(() => {
    if (!workflow) return [] as ReqView[]
    const { evidence_match: match, parsed_jd: jd } = workflow
    const uncovered = new Map(
      (match.uncovered_requirements ?? []).map((u) => [u.requirement_id, u.reason]),
    )
    const byReq = new Map<string, EvidenceMatchItem[]>()
    for (const item of match.matches) {
      const list = byReq.get(item.requirement_id) ?? []
      list.push(item)
      byReq.set(item.requirement_id, list)
    }
    return jd.requirements.map((requirement) => {
      const candidates = byReq.get(requirement.requirement_id) ?? []
      const best = [...candidates].sort((a, b) => b.relevance_score - a.relevance_score)[0]
      const uncoveredReason = uncovered.get(requirement.requirement_id)
      const tone = toneForMatch(best)
      return {
        requirement,
        tone,
        label: toneLabel(tone),
        best,
        uncoveredReason,

      }
    })
  }, [workflow])

  const jdText = (workflow?.parsed_jd.source_text || '').trim()

  const highlights = useMemo(() => buildHighlights(jdText, views), [jdText, views])

  const active = views.find((v) => v.requirement.requirement_id === activeReqId) ?? null
  const counts = useMemo(() => {
    const init = { strong: 0, medium: 0, conflict: 0, uncovered: 0 }
    for (const v of views) init[v.tone] += 1
    return init
  }, [views])

  if (!workflow) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>证据匹配</h2>
        </header>
        <EmptyState
          title="尚未运行工作流"
          detail="请先在岗位说明页运行在线流程，或加载预录结果。"
          actionLabel="去岗位说明"
          onAction={() => navigate('/jd')}
        />
      </section>
    )
  }

  const relatedMatches = active
    ? workflow.evidence_match.matches.filter(
        (m) => m.requirement_id === active.requirement.requirement_id,
      )
    : []

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>证据匹配</h2>
        <p>岗位原文按匹配结果着色；点击彩色片段查看经历与证据明细。</p>
      </header>

      <div className="em-legend" aria-label="匹配图例">
        <span className="em-chip strong">强匹配 {counts.strong}</span>
        <span className="em-chip medium">弱匹配 {counts.medium}</span>
        <span className="em-chip conflict">有冲突 {counts.conflict}</span>
        <span className="em-chip uncovered">未覆盖 {counts.uncovered}</span>
      </div>

      <div className="em-stack">
        <section className="em-jd">
          <h3 className="em-section-title">输入的岗位说明</h3>
          <p className="muted em-jd-meta">
            {workflow.parsed_jd.title === 'UNKNOWN' ? '未知岗位' : workflow.parsed_jd.title} @{' '}
            {workflow.parsed_jd.company === 'UNKNOWN' ? '未知公司' : workflow.parsed_jd.company} ·{' '}
            {workflow.parsed_jd.requirements.length} 条要求
          </p>
          <div className="em-jd-body" role="article">
            <HighlightedJd jdText={jdText} spans={highlights} onOpen={openRequirement} />
          </div>
          <p className="muted em-jd-hint">
            {highlights.length
              ? '彩色片段可点击；未高亮的段落暂无对应解析要求。'
              : '未能在原文中定位要求片段，可点下方条目查看详情。'}
          </p>
        </section>

        {!views.length ? (
          <EmptyState
            title="无要求"
            detail="parsed_jd 未返回 requirements。"
              actionLabel="回退岗位说明"
            onAction={() => navigate('/jd')}
          />
        ) : (
          <ul className="em-req-list">
            {views.map((v) => (
              <li key={v.requirement.requirement_id}>
                <button
                  type="button"
                  className={`em-req em-req-${v.tone}`}
                  onClick={() => openRequirement(v.requirement.requirement_id)}
                >
                  <span className="em-req-top">
                    <span className="em-chip compact">{v.label}</span>
                    <span className="em-req-id">
                      {v.requirement.requirement_id.replace(/^req_0*/, '要求 ')}
                    </span>
                    {v.best ? (
                      <span className="em-req-score">
                        {(v.best.relevance_score * 100).toFixed(0)}% ·{' '}
                        {zhLookup(ZH_STRENGTH, v.best.evidence_strength)}
                      </span>
                    ) : (
                      <span className="em-req-score">无可用经历</span>
                    )}
                  </span>
                  <span className="em-req-text">{v.requirement.text}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {active && (
        <div
          className="em-modal-backdrop"
          role="presentation"
          onClick={closeRequirement}
        >
          <div
            className="em-modal"
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="em-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="em-modal-head">
              <div>
                <p className={`em-chip ${active.tone}`}>{active.label}</p>
                <h3 id="em-modal-title">
                  {active.requirement.requirement_id.replace(/^req_0*/, '要求 ')}
                </h3>
              </div>
              <button type="button" className="btn secondary" onClick={closeRequirement}>
                关闭
              </button>
            </header>
            <p className="em-modal-req">{active.requirement.text}</p>
            <p className="muted">
              类型 {zhLookup(ZH_REQ_TYPE, active.requirement.type)} · 类别{' '}
              {zhLookup(ZH_CATEGORY, active.requirement.category)}
            </p>

            {active.uncoveredReason ? (
              <div className={`callout ${active.tone === 'uncovered' ? 'warn' : 'ok'}`}>
                <strong>
                  {active.tone === 'uncovered' ? '未覆盖原因' : '选入说明'}
                </strong>
                <p>
                  {active.tone === 'uncovered'
                    ? zhText(active.uncoveredReason)
                    : `已有${active.label}，但尚未达到可写入简历的门槛。${zhText(active.uncoveredReason)}`}
                </p>
              </div>
            ) : null}

            {relatedMatches.length ? (
              <div className="stack">
                {relatedMatches.map((m) => (
                  <article
                    key={`${m.requirement_id}-${m.experience_id}`}
                    className="item-block em-detail-card"
                  >
                    <div className="item-head">
                      <h4>{m.experience_id.replace(/^exp_/, '经历·').replaceAll('_', ' ')}</h4>
                      <span className="score">
                        {(m.relevance_score * 100).toFixed(0)}% ·{' '}
                        {zhLookup(ZH_STRENGTH, m.evidence_strength)}
                      </span>
                    </div>
                    <p>
                      <strong>匹配原因：</strong>
                      {zhText(m.rationale)}
                    </p>
                    <p className="muted">
                      陈述：{m.claim_ids.map((id) => id.replace(/^claim_/, '')).join('、') || '无'}
                    </p>
                    <p className="muted">
                      证据：{(m.evidence_ids ?? []).map((id) => id.replace(/^ev_/, '')).join('、') || '无'}
                    </p>
                    {m.conflicts?.length ? (
                      <p className="danger-text">冲突：{m.conflicts.map((c) => zhText(c)).join('；')}</p>
                    ) : null}
                    {m.missing_evidence?.length ? (
                      <p className="warn-text">
                        缺证：{m.missing_evidence.map((c) => zhText(c)).join('；')}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">没有关联到经历库条目。</p>
            )}
          </div>
        </div>
      )}

      <div className="btn-row end">
        <button type="button" className="btn primary" onClick={() => navigate('/resume')}>
          下一步：简历审查
        </button>
      </div>
    </section>
  )
}
