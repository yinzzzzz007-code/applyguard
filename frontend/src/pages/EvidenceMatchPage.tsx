import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import type { EvidenceMatchItem, ParsedRequirement } from '../api/types'
import { EmptyState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { ZH_CATEGORY, ZH_MATCHER, ZH_REQ_TYPE, ZH_STRENGTH, zhLookup, zhText } from '../i18n'
import { indexesInScope, quoteKind, type QualificationKind } from '../jdMatchScope'

type MatchTone = 'strong' | 'medium' | 'conflict' | 'uncovered'

type ScopeFilter = 'all' | QualificationKind

type ReqView = {
  requirement: ParsedRequirement
  tone: MatchTone
  label: string
  best?: EvidenceMatchItem
  uncoveredReason?: string
  section: QualificationKind
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

function scoreOutOfTen(match: EvidenceMatchItem): string {
  const fromModel = match.score_breakdown?.ai_score_10
  const value =
    typeof fromModel === 'number' && Number.isFinite(fromModel)
      ? Math.max(0, Math.min(10, fromModel))
      : Math.max(0, Math.min(10, match.relevance_score * 10))
  const text = Number.isInteger(value) ? String(value) : value.toFixed(1)
  return `${text}/10`
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
function buildHighlights(
  jdText: string,
  views: ReqView[],
  kinds: QualificationKind[] | null,
): HlSpan[] {
  const raw: HlSpan[] = []
  for (const v of views) {
    const needle = pickNeedle(jdText, v.requirement)
    if (!needle) continue
    for (const idx of indexesInScope(jdText, needle, kinds)) {
      raw.push({
        start: idx,
        end: idx + needle.length,
        reqId: v.requirement.requirement_id,
        tone: v.tone,
      })
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

function renderHighlightedJd(
  jdText: string,
  spans: HlSpan[],
  onOpen: (reqId: string) => void,
): ReactNode[] {
  if (!jdText) return ['（无岗位原文，仅有解析结果）']
  const nodes: ReactNode[] = []
  let cursor = 0
  spans.forEach((span, i) => {
    if (span.start > cursor) {
      nodes.push(jdText.slice(cursor, span.start))
    }
    nodes.push(
      <mark
        key={`${span.reqId}-${span.start}-${i}`}
        className={`em-hl em-hl-${span.tone}`}
        title="点击查看匹配详情"
        onClick={() => onOpen(span.reqId)}
      >
        {jdText.slice(span.start, span.end)}
      </mark>,
    )
    cursor = span.end
  })
  if (cursor < jdText.length) nodes.push(jdText.slice(cursor))
  return nodes
}

function sectionOf(jdText: string, requirement: ParsedRequirement): QualificationKind | 'out' {
  const quote = requirement.evidence_text || requirement.text || ''
  const kind = quoteKind(jdText, quote)
  if (kind === 'out') return 'out'
  if (kind === 'requirement' || kind === 'bonus') return kind
  return requirement.type === 'PREFERRED' ? 'bonus' : 'requirement'
}

export function EvidenceMatchPage() {
  const navigate = useNavigate()
  const { workflow, jdRawInput } = useDemo()
  const [activeReqId, setActiveReqId] = useState<string | null>(null)
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>('all')

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
    return jd.requirements.flatMap((requirement) => {
      const candidates = byReq.get(requirement.requirement_id) ?? []
      const best = [...candidates].sort((a, b) => b.relevance_score - a.relevance_score)[0]
      const uncoveredReason = uncovered.get(requirement.requirement_id)
      const tone = toneForMatch(best)
      const section = sectionOf((jd.source_text || jdRawInput || '').trim(), requirement)
      if (section === 'out') return []
      return [{
        requirement,
        tone,
        label: toneLabel(tone),
        best,
        uncoveredReason,
        section,
      }]
    })
  }, [workflow, jdRawInput])

  const jdText = useMemo(
    () => (jdRawInput || workflow?.parsed_jd.source_text || '').trim(),
    [jdRawInput, workflow],
  )

  const visible = useMemo(
    () => (scopeFilter === 'all' ? views : views.filter((view) => view.section === scopeFilter)),
    [views, scopeFilter],
  )

  const highlights = useMemo(() => {
    const kinds = scopeFilter === 'all' ? (['requirement', 'bonus'] as QualificationKind[]) : [scopeFilter]
    return buildHighlights(jdText, visible, kinds)
  }, [jdText, visible, scopeFilter])

  const active = visible.find((v) => v.requirement.requirement_id === activeReqId) ?? null
  const counts = useMemo(() => {
    const init = { strong: 0, medium: 0, conflict: 0, uncovered: 0 }
    for (const v of visible) init[v.tone] += 1
    return init
  }, [visible])
  const scopeCounts = useMemo(() => {
    return {
      requirement: views.filter((view) => view.section === 'requirement').length,
      bonus: views.filter((view) => view.section === 'bonus').length,
    }
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
        <p>只对照任职要求与加分项；职位描述不参与匹配。点击彩色片段查看经历与证据明细。</p>
        {(() => {
          const matcherMode = workflow.component_modes?.evidence_matcher
          const label = matcherMode
            ? zhLookup(ZH_MATCHER, matcherMode.split('+')[0], matcherMode)
            : null
          const ai = workflow.evidence_match.ai_match
          if (!label && !ai) return null
          return (
            <p className="muted">
              匹配方式：{label || '规则匹配'}
              {ai?.mode === 'MODEL' && typeof ai.scored_rows === 'number'
                ? ` · 模型评分 ${ai.scored_rows} 条`
                : ''}
              {ai?.mode === 'RULE_FALLBACK' && ai.failure
                ? ` · 模型失败已回退（${zhText(ai.failure)}）`
                : ''}
            </p>
          )
        })()}
      </header>

      <div className="em-scope" role="group" aria-label="匹配范围">
        {(
          [
            ['all', '全部', views.length],
            ['requirement', '任职要求', scopeCounts.requirement],
            ['bonus', '加分项', scopeCounts.bonus],
          ] as const
        ).map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            className={`em-chip em-scope-btn ${scopeFilter === id ? 'on' : ''}`}
            aria-pressed={scopeFilter === id}
            onClick={() => setScopeFilter(id)}
          >
            {label} {count}
          </button>
        ))}
      </div>

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
            {views.length} 条参与匹配
            {workflow.parsed_jd.requirements.length > views.length
              ? ` · 已排除职位描述等 ${workflow.parsed_jd.requirements.length - views.length} 条`
              : ''}
          </p>
          <div className="em-jd-body" role="article">
            {renderHighlightedJd(jdText, highlights, setActiveReqId)}
          </div>
          <p className="muted em-jd-hint">
            {highlights.length
              ? '彩色片段来自任职要求或加分项，可点击查看。职位描述不会着色。'
              : '未能在任职要求或加分项中定位片段，可点下方条目查看详情。'}
          </p>
        </section>

        {!views.length ? (
          <EmptyState
            title={workflow.parsed_jd.requirements.length ? '没有可匹配条目' : '无要求'}
            detail={
              workflow.parsed_jd.requirements.length
                ? '证据匹配只看任职要求与加分项。当前原文里没有识别到这两段中的条目。'
                : 'parsed_jd 未返回 requirements。'
            }
            actionLabel="回退岗位说明"
            onAction={() => navigate('/jd')}
          />
        ) : !visible.length ? (
          <EmptyState
            title="当前筛选下没有条目"
            detail="换到「全部」，或查看另一段。"
            actionLabel="查看全部"
            onAction={() => setScopeFilter('all')}
          />
        ) : (
          <ul className="em-req-list">
            {visible.map((v) => (
              <li key={v.requirement.requirement_id}>
                <button
                  type="button"
                  className={`em-req em-req-${v.tone}`}
                  onClick={() => setActiveReqId(v.requirement.requirement_id)}
                >
                  <span className="em-req-top">
                    <span className="em-chip compact">{v.section === 'bonus' ? '加分项' : '任职要求'}</span>
                    <span className="em-chip compact">{v.label}</span>
                    <span className="em-req-id">
                      {v.requirement.requirement_id.replace(/^req_0*/, '要求 ')}
                    </span>
                    {v.best ? (
                      <span className="em-req-score">
                        {scoreOutOfTen(v.best)} · {zhLookup(ZH_STRENGTH, v.best.evidence_strength)}
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
          onClick={() => setActiveReqId(null)}
        >
          <div
            className="em-modal"
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
              <button type="button" className="btn secondary" onClick={() => setActiveReqId(null)}>
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
                        {scoreOutOfTen(m)} · {zhLookup(ZH_STRENGTH, m.evidence_strength)}
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
