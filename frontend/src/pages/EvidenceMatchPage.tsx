import {matchScoreOutOfTen, STRONG_MATCH_SCORE} from '../resume/draftSelection'
import {completeGuideStep} from '../guide'
import { ExperienceCandidates } from '../components/ExperienceCandidates'
import { ProfileCheckList } from '../components/ProfileCheckList'
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
  if (!best) return 'uncovered'
  if (best.conflicts?.length) return 'conflict'
  if (matchScoreOutOfTen(best) >= STRONG_MATCH_SCORE) return 'strong'
  if (matchScoreOutOfTen(best) > 0) return 'medium'
  return 'uncovered'
}

function toneLabel(tone: MatchTone): string {
  switch (tone) {
    case 'strong':
      return '较强匹配'
    case 'medium':
      return '弱匹配'
    case 'conflict':
      return '有冲突'
    case 'uncovered':
      return '未覆盖'
  }
}

function scoreOutOfTen(match: EvidenceMatchItem): string {
  const score=matchScoreOutOfTen(match)
  return `${score>=STRONG_MATCH_SCORE?'较强匹配':'相关度'} ${score}/10`
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
    for (const idx of indexesInScope(jdText, needle, v.requirement.section ? [v.requirement.section] : kinds)) {
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
        title="点击查看匹配详情" tabIndex={0} role="button"
        onKeyDown={e => { if (e.key === "Enter" || e.key === " ") {e.preventDefault(); onOpen(span.reqId)} }}
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
  if (requirement.section) return requirement.section === 'requirement' && requirement.priority === 'preferred' ? 'bonus' : requirement.section
  if (kind === 'out') return 'out'
  if (kind === 'requirement' || kind === 'bonus' || kind === 'description') return kind
  return requirement.type === 'PREFERRED' ? 'bonus' : 'requirement'
}

export function EvidenceMatchPage() {
  const navigate = useNavigate()
  const { workflow, jdRawInput, workflowSourceNotice } = useDemo()
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
      const best = [...candidates].sort((a, b) => matchScoreOutOfTen(b) - matchScoreOutOfTen(a))[0]
      const uncoveredReason = uncovered.get(requirement.requirement_id)
      const profile = workflow.profile_checks?.[requirement.requirement_id]
      const personalEducation = requirement.category === 'EDUCATION' && Boolean(profile?.length)
      const tone = personalEducation ? 'medium' : toneForMatch(best)
      const label = personalEducation ? '个人资料对照' : tone === 'conflict' ? '有冲突' : best?.lead ? (best.lead.kind === 'framework' ? '框架待确认' : best.lead.kind === 'direct' ? '经历有记录' : '有相关线索') : !requirement.normalized_terms?.length
        ? '需人工核对' : !best && profile?.some(check => check.state === 'DECLARED')
          ? '本人填写，待补证' : toneLabel(tone)
      const section = sectionOf((jd.source_text || jdRawInput || '').trim(), requirement)
      if (section === 'out') return []
      return [{
        requirement,
        tone,
        label,
        best,
        uncoveredReason,
        section,
      }]
    })
  }, [workflow, jdRawInput])

  const jdText = useMemo(
    () => (workflow?._prerecorded ? workflow.parsed_jd.source_text : jdRawInput || workflow?.parsed_jd.source_text || '').trim(),
    [jdRawInput, workflow],
  )

  const visible = useMemo(
    () => (scopeFilter === 'all' ? views : views.filter((view) => view.section === scopeFilter)),
    [views, scopeFilter],
  )

  const highlights = useMemo(() => {
    const kinds = scopeFilter === 'all' ? (['requirement', 'bonus', 'description'] as QualificationKind[]) : [scopeFilter]
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
      description: views.filter(v => v.section === 'description').length,
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
        {workflowSourceNotice && <p className="callout warn">{workflowSourceNotice}</p>}
        <EmptyState
          title="尚未运行工作流"
          detail="请先在岗位说明页分析岗位。"
          actionLabel="去岗位说明"
          onAction={() => navigate('/jd')}
        />
      </section>
    )
  }

  const relatedMatches = active
    ? workflow.evidence_match.matches.filter(
        (m) => m.requirement_id === active.requirement.requirement_id,
      ).sort((a,b)=>matchScoreOutOfTen(b)-matchScoreOutOfTen(a))
    : []

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>证据匹配</h2>
        <p>点击岗位要求，查看对应经历与材料。</p>
        {workflowSourceNotice && <p className="callout warn">{workflowSourceNotice}</p>}
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
            ['description', '岗位职责', scopeCounts.description],
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
        <span className="em-chip strong">较强匹配 {counts.strong}</span>
        <span className="em-chip medium">相关经历 / 个人资料 {counts.medium}</span>
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
              ? ` · 已排除背景信息等 ${workflow.parsed_jd.requirements.length - views.length} 条`
              : ''}
          </p>
          <div className="em-jd-body" role="article">
            {renderHighlightedJd(jdText, highlights, setActiveReqId)}
          </div>
          <p className="muted em-jd-hint">
            {highlights.length
              ? '点击着色词组查看对应经历。'
              : '未能在岗位原文中定位片段，可点下方条目查看详情。'}
          </p>
        </section>

        {!views.length ? (
          <EmptyState
            title={workflow.parsed_jd.requirements.length ? '没有可匹配条目' : '无要求'}
            detail={
              workflow.parsed_jd.requirements.length
                ? '请补充具体的工作职责或任职要求。'
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
                    <span className="em-chip compact">{v.section === 'description' ? '岗位职责' : v.section === 'bonus' ? '加分项' : v.requirement.priority === 'general' ? '通用能力' : '任职要求'}</span>
                    <span className="em-chip compact">{v.label}</span>
                    <span className="em-req-id">
                      {v.requirement.requirement_id.replace(/^req_0*/, '要求 ')}
                    </span>
                    {v.best ? (
                      <span className="em-req-score">
                        {scoreOutOfTen(v.best)} · {zhLookup(ZH_STRENGTH, v.best.evidence_strength)}
                      </span>
                    ) : (
                      <span className="em-req-score">尚未找到相关经历</span>
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
            <ProfileCheckList checks={workflow.profile_checks?.[active.requirement.requirement_id]} />
            {!active.requirement.normalized_terms?.length && <p>此条需要对照岗位原文人工核对。</p>}
            <p className="muted">
              类型 {zhLookup(ZH_REQ_TYPE, active.requirement.type)} · 类别{' '}
              {zhLookup(ZH_CATEGORY, active.requirement.category)}
            </p>

            {active.uncoveredReason && !relatedMatches.some(m => m.lead) ? (
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

            {active.requirement.category === 'EDUCATION' && workflow.profile_checks?.[active.requirement.requirement_id]?.length ? (
              <p className="muted">对照依据为本人填写的教育信息。请按岗位要求另行核对学历证明。</p>
            ) : null}
            {active.requirement.category !== 'EDUCATION' && <ExperienceCandidates key={JSON.stringify([workflow.candidate_id, workflow.parsed_jd.jd_id, active.requirement.requirement_id])} requirement={active.requirement} matches={relatedMatches} />}
            {relatedMatches.some(m => !m.lead) ? (
              <div className="stack">
                {relatedMatches.filter(m => !m.lead).map((m) => (
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
            ) : null}
          </div>
        </div>
      )}

      <div className="btn-row end">
        <button type="button" className="btn primary" data-guide="match-next" onClick={() => {completeGuideStep('match');navigate('/resume')}}>
          下一步：简历审查
        </button>
      </div>
    </section>
  )
}
