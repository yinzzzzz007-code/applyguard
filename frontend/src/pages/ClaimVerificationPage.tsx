import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getApiClient } from '../api/client'
import type { CareerVaultSeed, ClaimEvidenceCheck, EvidenceLink, EvidenceRecord } from '../api/types'
import { ClaimBadge, EmptyState } from '../components/States'
import { AtomicEvidence } from '../components/AtomicEvidence'
import { useDemo } from '../context/DemoContext'
import { zhText } from '../i18n'

function LocalEvidencePeek({
  evidenceId,
  claimText,
}: {
  evidenceId: string
  claimText: string
}) {
  const api = getApiClient()
  const [record, setRecord] = useState<EvidenceRecord | null>(null)
  const [check, setCheck] = useState<ClaimEvidenceCheck | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    void api.getEvidence(evidenceId).then((res) => {
      if (res.data) setRecord(res.data)
    })
    void api.checkClaimEvidence(claimText, evidenceId).then((res) => {
      if (res.data) setCheck(res.data)
    })
  }, [api, evidenceId, claimText, open])

  const previewUrl = record?.primary_file_id
    ? api.evidencePreviewUrl(record.primary_file_id)
    : null
  const hit = record?.spans?.find((s) => /二等奖|一等奖|三等奖/.test(s.raw_text))

  return (
    <div className="local-evidence-peek">
      <button type="button" className="linkish" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {open ? '收起原件预览' : '查看原件'}
      </button>
      {' · '}
      <Link to={`/evidence?evidence_id=${evidenceId}`}>在工作区打开</Link>
      {open ? (
        <div className="callout">
          {!record ? (
            <p className="muted">加载中或该编号不是本地证据…</p>
          ) : (
            <>
              <p>
                版本状态：{record.review_state}
                {record.file ? ` · ${record.file.relative_path} v${record.file.version}` : ''}
                {record.reviewed_at ? ` · 核对于 ${record.reviewed_at}` : ''}
              </p>
              {check ? (
                <p className={check.status === 'VERIFIED' ? 'muted' : 'danger-text'}>
                  相对陈述：{check.status}
                  {check.reasons.length ? ` — ${check.reasons.join('；')}` : ''}
                </p>
              ) : null}
              {previewUrl && record.file?.media_type?.startsWith('image/') ? (
                <div className="evidence-preview-image-wrap">
                  <img src={previewUrl} alt="" className="evidence-preview-image" />
                  {hit?.bbox && hit.bbox.length === 4 ? (
                    <div
                      className="evidence-bbox"
                      style={{
                        left: `${hit.bbox[0] * 100}%`,
                        top: `${hit.bbox[1] * 100}%`,
                        width: `${(hit.bbox[2] - hit.bbox[0]) * 100}%`,
                        height: `${(hit.bbox[3] - hit.bbox[1]) * 100}%`,
                      }}
                    />
                  ) : null}
                </div>
              ) : previewUrl ? (
                <p>
                  <a href={previewUrl} target="_blank" rel="noreferrer">
                    打开预览
                  </a>
                  {hit ? ` · 定位片段：${hit.raw_text}` : ''}
                </p>
              ) : (
                <p className="danger-text">原件不可用或已失效</p>
              )}
            </>
          )}
        </div>
      ) : null}
    </div>
  )
}

export function ClaimVerificationPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const {
    workflow,
    workflowSourceNotice,
    claimDecisions,
    setClaimDecision,
    canProceedFromClaims,
    reverifyClaims,
  } = useDemo()
  const [rechecking, setRechecking] = useState(false)
  const [recheckError, setRecheckError] = useState('')
  const [vault, setVault] = useState<CareerVaultSeed | null>(null)
  const [localLinks, setLocalLinks] = useState<EvidenceLink[]>([])

  useEffect(() => {
    void fetch(`${import.meta.env.BASE_URL}data/career-vault.seed.json`)
      .then((r) => r.json())
      .then((d: CareerVaultSeed) => setVault(d))
      .catch(() => setVault(null))
  }, [])

  useEffect(() => {
    void getApiClient()
      .listEvidenceLinks({ target_type: 'claim' })
      .then((res) => setLocalLinks(res.data ?? []))
  }, [])

  useEffect(() => {
    const id = location.hash.replace(/^#/, '')
    if (!id || !workflow) return
    const timer = window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
    return () => window.clearTimeout(timer)
  }, [location.hash, workflow])

  const evidenceIndex = useMemo(() => {
    const map = new Map<string, string>()
    vault?.experiences.forEach((exp) => {
      exp.evidence_sources.forEach((ev) => {
        map.set(ev.evidence_id, ev.description)
      })
    })
    workflow?.evidence_sources?.forEach((ev) => map.set(ev.evidence_id, ev.description))
    return map
  }, [vault, workflow])

  if (!workflow) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>陈述核验</h2>
        </header>
        {workflowSourceNotice && <p className="callout warn">{workflowSourceNotice}</p>}
        <EmptyState
          title="无核验数据"
          detail="请先在岗位说明页完成分析。结果会预存到本机后端；源头变更后会作废并要求重新分析。"
          actionLabel="去岗位说明"
          onAction={() => navigate('/jd')}
        />
      </section>
    )
  }

  const claimsById = Object.fromEntries(workflow.resume_claims.map((claim) => [claim.claim_id, claim]))
  const proceedOk = canProceedFromClaims()

  return (
    <section className="panel claim-verification-page">
      <header className="panel-head">
        <h2>陈述核验</h2>
        <p>核对每条陈述的材料依据，再决定如何处理。</p>
        {workflowSourceNotice && <p className="callout warn">{workflowSourceNotice}</p>}
      </header>

      <div className="claim-overview">
        <div className="claim-summary" aria-label="核验结果汇总">
          {(['VERIFIED', 'NEEDS_REVIEW', 'BLOCKED'] as const).map(state => (
            <div key={state}>
              <strong>{workflow.claim_verification.filter(row => row.state === state &&
                !(state === 'VERIFIED' && workflow.grounding?.results[row.claim_id]?.verification_scope === 'personal')).length}</strong>
              <ClaimBadge status={state} />
            </div>
          ))}
          <div>
            <strong>{workflow.claim_verification.filter(row => row.state === 'VERIFIED' &&
              workflow.grounding?.results[row.claim_id]?.verification_scope === 'personal').length}</strong>
            <ClaimBadge status="VERIFIED" personal />
          </div>
        </div>
        <button type="button" className="btn primary" disabled={rechecking} onClick={() => {
          setRechecking(true)
          setRecheckError('')
          void reverifyClaims().then((error) => setRecheckError(error ?? '')).finally(() => setRechecking(false))
        }}>{rechecking ? '正在重新核验…' : '重新核验'}</button>
      </div>

      {workflow.requires_reverification && <p className="callout warn" role="status">请重新核验当前草稿，更新材料支持状态。</p>}
      {recheckError && <p className="danger-text" role="alert">{recheckError}</p>}
      <div className="stack claim-cards">
        {workflow.claim_verification.map((verification, index) => {
          const id = verification.claim_id
          const claim = claimsById[id]
          const decision = claimDecisions[id]
          const result = workflow.grounding?.results[id]
          const personal = result?.verification_scope === 'personal'
          const editing = decision?.decision === 'edit'
          const needsDecision = verification.state !== 'VERIFIED'
          const canEdit = verification.state === 'NEEDS_REVIEW' || Boolean(workflow.grounding)
          const needsRecheck = workflow.requires_reverification || decision?.freshness === 'edited_pending_reverify'
          const text = editing ? decision.editedText ?? claim?.text ?? '' : claim?.text
          const materials = new Map<string, { id: string; state?: EvidenceLink['link_state'] }>()
          const evidenceKey = (rawId: string) => rawId.replace(/^ev_local_/, 'evloc_')
          for (const evidenceId of claim?.evidence_ids ?? []) {
            materials.set(evidenceKey(evidenceId), { id: evidenceId })
          }
          for (const link of localLinks.filter(link => link.target_id === id)) {
            const key = evidenceKey(link.evidence_id)
            materials.set(key, { id: materials.get(key)?.id ?? link.evidence_id, state: link.link_state })
          }
          const atomTexts = new Set(result?.atoms.map(atom => atom.text))
          const extraFragments = (verification.unsupported_fragments ?? []).filter(fragment => !atomTexts.has(fragment))
          const stateClass = verification.state === 'BLOCKED' ? 'blocked' : verification.state === 'NEEDS_REVIEW' ? 'needs' : ''
          const title = `第 ${index + 1} 条陈述`

          return (
            <article key={id} id={id} className={`item-block claim ${stateClass}`} aria-labelledby={`title-${id}`}>
              <header className="claim-card-heading">
                <h3 id={`title-${id}`}>{title}</h3>
                <ClaimBadge status={verification.state} personal={personal} />
                {decision?.decision === 'confirm' && <span className="claim-choice">已选择保留</span>}
                {decision?.decision === 'reject' && <span className="claim-choice">已排除</span>}
                {editing && <span className="claim-choice">编辑中 · 待重新核验</span>}
              </header>

              {editing ? (
                <textarea className="jd-input" rows={3} aria-label={`编辑${title}`} value={text}
                  onChange={(event) => setClaimDecision(id, {
                    decision: 'edit', editedText: event.target.value, freshness: 'edited_pending_reverify',
                  })} />
              ) : <p className="claim-statement">{text ?? '草稿中缺少该条陈述。'}</p>}

              {materials.size === 0 && !personal && <p className="claim-meta">暂无关联材料</p>}

              <div className="claim-card-controls">
                <details className="claim-details">
                  <summary>
                    {needsRecheck ? '材料与上次核验' : '材料与核验明细'}
                    <span>{` · ${materials.size} 份材料`}</span>
                  </summary>
                  {verification.explanation && <p className="claim-detail-note">{zhText(verification.explanation)}</p>}
                  {extraFragments.length > 0 && (
                    <div className="claim-details-group">
                      <h4>待核对片段</h4>
                      <ul>{extraFragments.map((fragment, index) => <li key={index}>{fragment}</li>)}</ul>
                    </div>
                  )}
                  <AtomicEvidence result={result} />
                  {materials.size > 0 && (
                    <div className="claim-details-group">
                      <h4>关联材料</h4>
                      <ul className="claim-material-list">
                        {[...materials].map(([key, material], index) => {
                          const title = result?.retrieved_sources.find(source => evidenceKey(source.evidence_id) === key)?.title
                          const description = evidenceIndex.get(material.id)
                          return (
                            <li key={key}>
                              <strong>{title || `材料 ${index + 1}`}</strong>
                              {material.state === 'STALE' && <span className="danger-text"> · 关联已过期</span>}
                              {material.state === 'REJECTED' && <span className="muted"> · 已撤销关联</span>}
                              {key.startsWith('evloc_') && <LocalEvidencePeek evidenceId={key} claimText={text ?? ''} />}
                              {description && (
                                <details className="claim-source">
                                  <summary>展开材料正文</summary>
                                  <div className="claim-source-text" tabIndex={0} role="region" aria-label="材料正文">{description}</div>
                                </details>
                              )}
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  )}
                </details>

                {(needsDecision || canEdit) && <div className="btn-row claim-action-bar">
                  {needsDecision && (
                    <button type="button" className="btn secondary" aria-pressed={decision?.decision === 'confirm'}
                      onClick={() => setClaimDecision(id, { decision: 'confirm', editedText: undefined, freshness: 'as_returned' })}>
                      {workflow.grounding || verification.state === 'BLOCKED' ? '知悉并保留' : '保留原文'}
                    </button>
                  )}
                  {canEdit && !editing && (
                    <button type="button" className="btn secondary"
                      onClick={() => setClaimDecision(id, { decision: 'edit', editedText: claim?.text, freshness: 'edited_pending_reverify' })}>
                      编辑陈述
                    </button>
                  )}
                  {needsDecision && (
                    <button type="button" className="btn secondary" aria-pressed={decision?.decision === 'reject'}
                      onClick={() => setClaimDecision(id, { decision: 'reject', freshness: 'rejected' })}>
                      排除
                    </button>
                  )}
                </div>}
              </div>
            </article>
          )
        })}
      </div>

      <div className="claim-page-footer">
        {!proceedOk && !workflow.requires_reverification && <p className="muted">请完成陈述核验与待处理项。</p>}
        <button type="button" className="btn primary" disabled={!proceedOk} onClick={() => navigate('/ats')}>
          下一步：申请内容检查
        </button>
      </div>
    </section>
  )
}
