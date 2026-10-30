import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type {
  ClaimVerification,
  EditableResumeForm,
  RemovedClaim,
  ResumeClaim,
} from '../api/types'
import { EmptyState } from '../components/States'
import { SAGPolishPanel } from '../components/SAGPolishPanel'
import { saveTextVersion } from '../resume/groundingHistory'
import { useDemo } from '../context/DemoContext'
import { ZH_CLAIM_STATUS, zhLookup, zhText } from '../i18n'
import { Icon } from '../components/Icon'

type DraftClaim = {
  claim_id: string
  text: string
  evidence_ids: string[]
  experienceTitle: string
  kind: string
}

function shortReason(reason: string): string {
  const value = reason.split(':')[0]?.trim() || reason
  return value === 'LOW_RELEVANCE' ? '相关度较低' : zhText(value)
}

function safeClaimId(raw: string): string {
  const body = raw.replace(/[^a-zA-Z0-9_]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase()
  const id = body.startsWith('claim_') ? body : `claim_${body || 'item'}`
  return id.slice(0, 96)
}

/** Build selectable resume sentences from the user's saved 经历库 form. */
function claimsFromResumeForm(form: EditableResumeForm | null): DraftClaim[] {
  if (!form) return []
  const out: DraftClaim[] = []

  const push = (
    id: string,
    kind: string,
    organization: string,
    title: string,
    role: string,
    description: string,
  ) => {
    const org = organization.trim()
    const label = (title || role).trim()
    const lines = description
      .split(/\r?\n/)
      .map((l) => l.trim().replace(/^[-*•·、]\s*/, ''))
      .filter(Boolean)
    const text = (lines.find((l) => l.length >= 8) || lines[0] || [org, label].filter(Boolean).join(' · ')).trim()
    if (!text) return
    out.push({
      claim_id: safeClaimId(id.replace(/^exp_/, '')),
      text: text.slice(0, 420),
      evidence_ids: [],
      experienceTitle: [label, org].filter(Boolean).join(' · ') || kind,
      kind,
    })
  }

  form.internships.forEach((e) =>
    push(e.id, '实习', e.organization, e.title, e.role, e.description),
  )
  form.projects.forEach((e) =>
    push(e.id, '项目', e.organization, e.title, e.role, e.description),
  )
  ;(form.awards ?? []).forEach((a) => {
    const name = a.name.trim()
    if (!name) return
    const text = (a.description || '').trim() || `${name}${a.issuer ? `（${a.issuer}）` : ''}`
    out.push({
      claim_id: safeClaimId(a.id),
      text: text.slice(0, 420),
      evidence_ids: [],
      experienceTitle: [name, a.issuer].filter(Boolean).join(' · ') || '获奖 / 竞赛',
      kind: '获奖',
    })
  })
  return out
}

export function ResumeReviewPage() {
  const navigate = useNavigate()
  const { workflow, patchWorkflow, resumeForm } = useDemo()
  const [draftText, setDraftText] = useState('')
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [historyError,setHistoryError] = useState('')
  const [sourceQuery,setSourceQuery] = useState('')
  const [sourceKind,setSourceKind] = useState('all')

  const draftClaims = useMemo(() => claimsFromResumeForm(resumeForm), [resumeForm])
  const draftById = useMemo(() => new Map(draftClaims.map((c) => [c.claim_id, c])), [draftClaims])

  if (!workflow) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>简历审查</h2>
        </header>
        <EmptyState
          title="无工作流数据"
          detail="请先运行工作流。"
          actionLabel="去岗位说明"
          onAction={() => navigate('/jd')}
        />
      </section>
    )
  }

  const { resume_claims: claims, resume_selection: selection, evidence_match: match } = workflow
  const reqText = Object.fromEntries(
    workflow.parsed_jd.requirements.map((r) => [r.requirement_id, r.text]),
  )
  const usingDraftVault = workflow.component_modes?.career_vault === 'LOCAL_RESUME_DRAFT'
  const selectedIds = new Set(claims.map((c) => c.claim_id))

  // Prefer 经历库草稿 as the pool; fall back to workflow removed_claims when no draft.
  const available: Array<DraftClaim & { reason: string }> = draftClaims.length
    ? draftClaims
        .filter((c) => !selectedIds.has(c.claim_id))
        .map((c) => {
          const removed = selection.removed_claims?.find((r) => r.claim_id === c.claim_id)
          return {
            ...c,
            reason: removed?.reason || '来自经历库草稿，可手动加入（加入后仍需核验）',
          }
        })
    : (selection.removed_claims ?? []).map((r) => ({
        claim_id: r.claim_id,
        text: r.text || r.claim_id,
        evidence_ids: [] as string[],
        experienceTitle: '工作流未选入',
        kind: '陈述',
        reason: r.reason,
      }))

  const seedLike =
    !usingDraftVault &&
    draftClaims.length > 0 &&
    claims.some((c) => !draftById.has(c.claim_id)) &&
    /lora|pipeline|fullstack|python_api/i.test(claims.map((c) => c.claim_id).join(' '))

  const visibleSources = available.filter(item => (sourceKind === 'all' || item.kind === sourceKind) &&
    (item.text+' '+item.experienceTitle).toLocaleLowerCase().includes(sourceQuery.trim().toLocaleLowerCase()))
  const characters = claims.reduce((sum,claim) => sum+Array.from(claim.text).length,0)

  function requirementIdsFor(claimId: string): string[] {
    return [
      ...new Set(
        match.matches
          .filter((m) => m.claim_ids.includes(claimId))
          .map((m) => m.requirement_id),
      ),
    ]
  }

  function supportFor(claimId: string): number {
    const scores = match.matches
      .filter((m) => m.claim_ids.includes(claimId))
      .map((m) => m.relevance_score)
    return scores.length ? Math.max(...scores) : 0
  }

  function addClaim(input: {
    claim_id: string
    text: string
    evidence_ids: string[]
    requirement_ids?: string[]
    support?: number
  }) {
    if (workflow) {
      try {saveTextVersion(workflow,'增加陈述前')} catch {setHistoryError('历史保存失败，尚未修改草稿。');return}
    }
    patchWorkflow((prev) => {
      if (prev.resume_claims.some((c) => c.claim_id === input.claim_id)) return prev
      const added: ResumeClaim = {
        claim_id: input.claim_id,
        application_id: prev.application_id,
        text: input.text,
        evidence_ids: input.evidence_ids,
        requirement_ids: input.requirement_ids ?? requirementIdsFor(input.claim_id),
        evidence_support_score: input.support ?? supportFor(input.claim_id),
        selection_reason: '手动加入：用户在简历审查页从经历库选入（非自动挑选）。',
        status: 'DRAFT',
      }
      const verification: ClaimVerification = {
        claim_id: input.claim_id,
        state: 'BLOCKED',
        unsupported_fragments: [],
        explanation: '手动内容尚未经过后端核验；请点击重新核验，缺少证据的内容会保持阻断。',
        support_score: added.evidence_support_score,
        grounded: false,
      }
      return {
        ...prev,
        resume_claims: [...prev.resume_claims, added],
        resume_selection: {
          ...prev.resume_selection,
          removed_claims: prev.resume_selection.removed_claims.filter(
            (r) => r.claim_id !== input.claim_id,
          ),
        },
        claim_verification: prev.claim_verification.some((v) => v.claim_id === input.claim_id)
          ? prev.claim_verification
          : [...prev.claim_verification, verification],
      }
    })
  }

  function removeClaim(claim: ResumeClaim) {
    if (workflow) {
      try {saveTextVersion(workflow,'移出陈述前')} catch {setHistoryError('历史保存失败，尚未修改草稿。');return}
    }
    patchWorkflow((prev) => ({
      ...prev,
      resume_claims: prev.resume_claims.filter((c) => c.claim_id !== claim.claim_id),
      resume_selection: {
        ...prev.resume_selection,
        removed_claims: [
          ...prev.resume_selection.removed_claims.filter((r) => r.claim_id !== claim.claim_id),
          {
            claim_id: claim.claim_id,
            reason: '手动移出：用户从简历草稿中拿掉。',
            text: claim.text,
          } as RemovedClaim,
        ],
      },
      claim_verification: prev.claim_verification.filter((v) => v.claim_id !== claim.claim_id),
    }))
  }

  function addCustom() {
    const text = draftText.trim()
    if (!text) return
    addClaim({
      claim_id: `claim_manual_${Date.now().toString(36)}`,
      text,
      evidence_ids: [],
      requirement_ids: [],
      support: 0,
    })
    setDraftText('')
  }

  function clearSeedDraft() {
    if (workflow) {
      try {saveTextVersion(workflow,'清空前自动备份')} catch {setHistoryError('历史保存失败，尚未清空草稿。');return}
    }
    patchWorkflow((prev) => ({
      ...prev,
      resume_claims: [],
      resume_selection: {
        ...prev.resume_selection,
        removed_claims: [],
      },
      claim_verification: [],
    }))
  }

  function cardDetail(opts: {
    claimId: string
    text: string
    reason?: string
    evidenceIds?: string[]
    requirementIds?: string[]
    support?: number
    experienceTitle?: string
  }) {
    return (
      <details className="rr-tip">
        <summary>查看来源与选入理由</summary><div>
        <p className="rr-tip-title">{opts.claimId.replace(/^claim_/, '陈述·')}</p>
        <p>{opts.text}</p>
        {opts.experienceTitle ? <p className="muted">经历：{opts.experienceTitle}</p> : null}
        {opts.reason ? (
          <p>
            <strong>理由：</strong>
            {zhText(opts.reason)}
          </p>
        ) : null}
        <p className="muted">
          证据：{(opts.evidenceIds ?? []).map((id) => id.replace(/^ev_/, '')).join('、') || '无'}
        </p>
        <p className="muted">
          岗位要求：{' '}
          {(opts.requirementIds ?? [])
            .map((id) => reqText[id] ?? id.replace(/^req_0*/, '要求 '))
            .join('；') || '无关联要求'}
        </p>
        {opts.support != null ? (
          <p className="muted">{workflow?.grounding ? '事实支持情况请查看陈述核验' : `支持度 ${(opts.support * 100).toFixed(0)}%`}</p>
        ) : null}
      </div></details>
    )
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>让经历，表达得更准确。</h2>
        <p>
          在左侧整理草稿，在右侧生成建议。每次修改，都需要重新核验。
        </p>
      </header>

      {seedLike ? (
        <div className="callout warn">
          <p>
            当前草稿里仍是演示种子陈述（如 LoRA / 数据管道），不是你在经历库保存的内容。请
            <Link to="/jd"> 回岗位说明重新运行工作流</Link>
            ，或点下方清空后从经历库重新加入。
          </p>
          <div className="btn-row">
            <button type="button" className="btn secondary" onClick={clearSeedDraft}>
              清空种子草稿
            </button>
            <Link className="btn primary" to="/jd">
              去重新运行
            </Link>
          </div>
        </div>
      ) : null}

      {!draftClaims.length ? (
        <div className="callout warn">
          经历库里还没有可引用的实习 / 项目 / 获奖。请先到 <Link to="/vault">经历库</Link> 填写并保存。
        </div>
      ) : (
        <p className="muted">
          可加入来源：本机经历库 {draftClaims.length} 条
          {usingDraftVault ? ' · 本次工作流已按草稿匹配' : ' · 建议重新运行工作流以按草稿自动筛选'}
        </p>
      )}

      <div className="draft-summary-strip">
        <div><strong>{claims.length}</strong><span>条草稿</span></div>
        <div><strong>{characters}</strong><span>个字符</span></div>
        <p>自动筛选参考：{selection.max_claims} 条 / {selection.max_characters} 字<br /><span>手动加入的陈述仍须核验。</span></p>
      </div>

      <div className="review-workspace"><div className="review-draft">
      {historyError && <p className="danger-text" role="alert">{historyError}</p>}
      <h3 className="em-section-title">已加入草稿</h3>
      {!claims.length ? (
        <p className="muted rr-empty">还没有句子。从下方卡片点「加入」，或自己写一条。</p>
      ) : (
        <div className="rr-grid">
          {claims.map((c) => {
            const draftHit = draftById.get(c.claim_id)
            return (
              <article
                key={c.claim_id}
                className={`rr-card rr-card-in${hoveredId === c.claim_id ? ' on' : ''}`}
                onMouseEnter={() => setHoveredId(c.claim_id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <div className="rr-card-top">
                  <span className="em-chip strong compact">{zhLookup(ZH_CLAIM_STATUS, c.status)}</span>
                  <span className="em-req-id">{c.claim_id.replace(/^claim_/, '陈述·')}</span>
                </div>
                <p className="rr-card-text">{c.text}</p>
                {draftHit ? <p className="muted rr-card-org">{draftHit.experienceTitle}</p> : null}
                <div className="rr-card-actions">
                  <button type="button" className="btn secondary" onClick={() => removeClaim(c)}>
                    移出
                  </button>
                </div>
                {cardDetail({
                  claimId: c.claim_id,
                  text: c.text,
                  reason: c.selection_reason,
                  evidenceIds: c.evidence_ids,
                  requirementIds: c.requirement_ids,
                  support: c.evidence_support_score,
                  experienceTitle: draftHit?.experienceTitle,
                })}
              </article>
            )
          })}
        </div>
      )}

      <div className="rr-add">
        <label className="field-label" htmlFor="rr-manual">
          手动添加句子
        </label>
        <textarea
          id="rr-manual"
          className="jd-input"
          rows={3}
          value={draftText}
          onChange={(e) => setDraftText(e.target.value)}
          placeholder="写一条要放进简历草稿的经历描述…"
        />
        <div className="btn-row">
          <button type="button" className="btn primary" disabled={!draftText.trim()} onClick={addCustom}>
            加入草稿
          </button>
        </div>
      </div>

      <div className="source-pool-heading"><h3 className="em-section-title">从经历库选入</h3><span>{visibleSources.length} / {available.length} 条</span></div>
      <label className="work-search source-search"><Icon name="search" /><input aria-label="搜索可加入的经历" value={sourceQuery} onChange={e => setSourceQuery(e.target.value)} placeholder="搜索项目名称、技术或经历内容" />
        {sourceQuery && <button type="button" aria-label="清除经历搜索" onClick={() => setSourceQuery('')}><Icon name="close" /></button>}</label>
      <div className="scope-switch source-kind" aria-label="经历类型">{['all','实习','项目','获奖'].map(kind => <button type="button" key={kind} aria-pressed={sourceKind === kind} onClick={() => setSourceKind(kind)}>{kind === 'all' ? '全部' : kind}</button>)}</div>
      {!available.length ? (
        <p className="muted">没有可加入的经历库句子。</p>
      ) : !visibleSources.length ? (
        <div className="source-empty"><p>没有找到匹配的经历，试试其他关键词或类型。</p><button type="button" className="text-action" onClick={() => {setSourceQuery('');setSourceKind('all')}}>重置筛选</button></div>
      ) : (
        <div className="rr-grid">
          {visibleSources.map((r) => {
            const reqIds = requirementIdsFor(r.claim_id)
            return (
              <article
                key={`${r.claim_id}-${r.reason}`}
                className={`rr-card rr-card-out${hoveredId === r.claim_id ? ' on' : ''}`}
                onMouseEnter={() => setHoveredId(r.claim_id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <div className="rr-card-top">
                  <span className="em-chip medium compact">{shortReason(r.reason)}</span>
                  <span className="chip">{r.kind}</span>
                </div>
                <p className="rr-card-text">{r.text}</p>
                <p className="muted rr-card-org">{r.experienceTitle}</p>
                <div className="rr-card-actions">
                  <button
                    type="button"
                    className="btn primary"
                    onClick={() =>
                      addClaim({
                        claim_id: r.claim_id,
                        text: r.text,
                        evidence_ids: r.evidence_ids,
                      })
                    }
                  >
                    加入草稿
                  </button>
                </div>
                {cardDetail({
                  claimId: r.claim_id,
                  text: r.text,
                  reason: r.reason,
                  evidenceIds: r.evidence_ids,
                  requirementIds: reqIds,
                  support: supportFor(r.claim_id),
                  experienceTitle: r.experienceTitle,
                })}
              </article>
            )
          })}
        </div>
      )}

      </div><aside className="review-rail"><SAGPolishPanel /></aside></div>
      <div className="btn-row end review-footer">
        <span>{claims.length ? '已整理 '+claims.length+' 条草稿，下一步核对每条依据。' : '先从经历库选入，或手动添加一条陈述。'}</span>
        <button type="button" className="btn primary" disabled={!claims.length} onClick={() => navigate('/claims')}>
          下一步：陈述核验
        </button>
      </div>
    </section>
  )
}
