import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type {
  CareerVaultSeed,
  ClaimVerification,
  RemovedClaim,
  ResumeClaim,
  VaultExperience,
} from '../api/types'
import { getApiClient } from '../api/client'
import { EmptyState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { ZH_CLAIM_STATUS, zhLookup, zhText } from '../i18n'

function shortReason(reason: string): string {
  return zhText(reason.split(':')[0]?.trim() || reason)
}

function vaultClaimLookup(vault: CareerVaultSeed | null) {
  const map = new Map<
    string,
    { text: string; evidence_ids: string[]; experience: VaultExperience; confidence: number }
  >()
  vault?.experiences.forEach((exp) => {
    exp.claims.forEach((c) => {
      map.set(c.claim_id, {
        text: c.text,
        evidence_ids: c.evidence_ids,
        experience: exp,
        confidence: c.confidence ?? 0,
      })
    })
  })
  return map
}

export function ResumeReviewPage() {
  const navigate = useNavigate()
  const { workflow, patchWorkflow } = useDemo()
  const [vault, setVault] = useState<CareerVaultSeed | null>(null)
  const [draftText, setDraftText] = useState('')
  const [hoveredId, setHoveredId] = useState<string | null>(null)

  useEffect(() => {
    void getApiClient().getCareerVault()
      .then((result) => setVault(result.data ?? null))
      .catch(() => setVault(null))
  }, [])

  const vaultClaims = useMemo(() => vaultClaimLookup(vault), [vault])

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
    patchWorkflow((prev) => {
      if (prev.resume_claims.some((c) => c.claim_id === input.claim_id)) return prev
      const added: ResumeClaim = {
        claim_id: input.claim_id,
        application_id: prev.application_id,
        text: input.text,
        evidence_ids: input.evidence_ids,
        requirement_ids: input.requirement_ids ?? requirementIdsFor(input.claim_id),
        evidence_support_score: input.support ?? supportFor(input.claim_id),
        selection_reason: '手动加入：用户在简历审查页选入（非自动挑选）。',
        status: 'DRAFT',
      }
      const verification: ClaimVerification = {
        claim_id: input.claim_id,
        state: 'BLOCKED',
        unsupported_fragments: [],
        explanation: '手动加入的陈述尚未由后端重新核验；可保留草稿，但不能确认或复制。',
        support_score: added.evidence_support_score,
        grounded: added.evidence_ids.length > 0,
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
          },
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

  function addRemoved(r: RemovedClaim) {
    const vaultHit = vaultClaims.get(r.claim_id)
    addClaim({
      claim_id: r.claim_id,
      text: r.text || vaultHit?.text || r.claim_id,
      evidence_ids: vaultHit?.evidence_ids ?? [],
    })
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
      <div className="rr-tip" role="tooltip">
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
          <p className="muted">支持度 {(opts.support * 100).toFixed(0)}%</p>
        ) : null}
      </div>
    )
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>简历审查</h2>
        <p>
          自动选择未通过时，可把经历库句子或自定义句子手动加入草稿。手动加入不等于已核验通过，下一步仍需处理。
        </p>
      </header>

      <div className="profile-card">
        <p>
          选择方式：确定性、受证据约束 · 最多 {selection.max_claims} 条 · 最多{' '}
          {selection.max_characters} 字 · 当前草稿 {claims.length} 条
        </p>
      </div>

      <h3 className="em-section-title">已加入草稿</h3>
      {!claims.length ? (
        <p className="muted rr-empty">还没有句子。从下方卡片点「加入」，或自己写一条。</p>
      ) : (
        <div className="rr-grid">
          {claims.map((c) => {
            const vaultHit = vaultClaims.get(c.claim_id)
            return (
              <article
                key={c.claim_id}
                className={`rr-card rr-card-in${hoveredId === c.claim_id ? ' on' : ''}`}
                tabIndex={0}
                onMouseEnter={() => setHoveredId(c.claim_id)}
                onMouseLeave={() => setHoveredId(null)}
                onFocus={() => setHoveredId(c.claim_id)}
                onBlur={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget)) setHoveredId(null)
                }}
              >
                <div className="rr-card-top">
                  <span className="em-chip strong compact">{zhLookup(ZH_CLAIM_STATUS, c.status)}</span>
                  <span className="em-req-id">{c.claim_id.replace(/^claim_/, '陈述·')}</span>
                </div>
                <p className="rr-card-text">{c.text}</p>
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
                  experienceTitle: vaultHit
                    ? `${vaultHit.experience.title ?? vaultHit.experience.role} · ${vaultHit.experience.organization}`
                    : undefined,
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

      <h3 className="em-section-title">未选入 / 可加入</h3>
      {(selection.removed_claims?.length ?? 0) === 0 ? (
        <p className="muted">没有被挡下的陈述。</p>
      ) : (
        <div className="rr-grid">
          {selection.removed_claims.map((r) => {
            const vaultHit = vaultClaims.get(r.claim_id)
            const text = r.text || vaultHit?.text || '（无正文）'
            const reqIds = requirementIdsFor(r.claim_id)
            return (
              <article
                key={`${r.claim_id}-${r.reason}`}
                  className={`rr-card rr-card-out${hoveredId === r.claim_id ? ' on' : ''}`}
                  tabIndex={0}
                  onMouseEnter={() => setHoveredId(r.claim_id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onFocus={() => setHoveredId(r.claim_id)}
                  onBlur={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget)) setHoveredId(null)
                  }}
              >
                <div className="rr-card-top">
                  <span className="em-chip medium compact">{shortReason(r.reason)}</span>
                  <span className="em-req-id">{r.claim_id.replace(/^claim_/, '陈述·')}</span>
                </div>
                <p className="rr-card-text">{text}</p>
                <p className="muted rr-card-org">
                  {vaultHit
                    ? `${vaultHit.experience.title ?? vaultHit.experience.role}`
                    : '自定义 / 已移出'}
                </p>
                <div className="rr-card-actions">
                  <button type="button" className="btn primary" onClick={() => addRemoved(r)}>
                    加入草稿
                  </button>
                </div>
                {cardDetail({
                  claimId: r.claim_id,
                  text,
                  reason: r.reason,
                  evidenceIds: vaultHit?.evidence_ids,
                  requirementIds: reqIds,
                  support: supportFor(r.claim_id),
                  experienceTitle: vaultHit
                    ? `${vaultHit.experience.title ?? vaultHit.experience.role} · ${vaultHit.experience.organization}`
                    : undefined,
                })}
              </article>
            )
          })}
        </div>
      )}

      <div className="btn-row end">
        <button type="button" className="btn primary" onClick={() => navigate('/claims')}>
          下一步：陈述核验
        </button>
      </div>
    </section>
  )
}
