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
      <button type="button" className="linkish" onClick={() => setOpen((v) => !v)}>
        {open ? '收起本地原件' : '查看本地证据原件'}
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
    const map = new Map<string, { description: string; experience_id: string }>()
    vault?.experiences.forEach((exp) => {
      exp.evidence_sources.forEach((ev) => {
        map.set(ev.evidence_id, {
          description: ev.description,
          experience_id: exp.experience_id,
        })
      })
    })
    workflow?.evidence_sources?.forEach((ev) => map.set(ev.evidence_id, {description: ev.description, experience_id: '本机证据'}))
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

  const claimsById = Object.fromEntries(workflow.resume_claims.map((c) => [c.claim_id, c]))
  const proceedOk = canProceedFromClaims()

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>陈述核验</h2>
        <p>把每一句话，与支持它的原始材料放在一起核对。</p>
        <p className="muted">
          「须逐条处理才能继续」只是辅助提醒：未通过或已阻断表示这句话可能与材料不匹配，不代表已判定虚假，也不代表录用结果。请补证、改写或排除后，再进入申请内容检查。
        </p>
        {workflowSourceNotice && <p className="callout warn">{workflowSourceNotice}</p>}
      </header>
      <div className="claim-summary" aria-label="核验结果汇总">{(['VERIFIED','NEEDS_REVIEW','BLOCKED'] as const).map(state => <div key={state}><strong>{workflow.claim_verification.filter(v => v.state === state &&
        !(v.state === 'VERIFIED' && workflow.grounding?.results[v.claim_id]?.verification_scope === 'personal')).length}</strong><ClaimBadge status={state} /></div>)}
        <div><strong>{workflow.claim_verification.filter(v => v.state === 'VERIFIED' && workflow.grounding?.results[v.claim_id]?.verification_scope === 'personal').length}</strong><ClaimBadge status="VERIFIED" personal /></div>
      </div>
      <div className="btn-row">
        <button type="button" className="btn primary" disabled={rechecking} onClick={() => {
          setRechecking(true)
          void reverifyClaims().then((error) => setRecheckError(error ?? '')).finally(() => setRechecking(false))
        }}>{rechecking ? '正在重新核验…' : '重新核验并更新风险'}</button>
      </div>
      {workflow.requires_reverification && <p className="warn-text">内容已改变，旧核验结果暂不可用于复制或确认。请重新核验。</p>}
      {recheckError && <p className="danger-text">{recheckError}</p>}
      <div className="claim-status-guide" aria-label="核验状态说明">
        <div className="claim-status-guide-item">
          <ClaimBadge status="VERIFIED" />
          <p>当前表述有经历库证据支持，可继续使用；这不等于外部事实已被独立证明。</p>
        </div>
        <div className="claim-status-guide-item">
          <ClaimBadge status="NEEDS_REVIEW" />
          <p>可能不完全匹配材料或措辞待核对。SAG 模式下请补证或编辑后重核验；人工勾选不能把它变成“已核验通过”。</p>
        </div>
        <div className="claim-status-guide-item">
          <ClaimBadge status="BLOCKED" />
          <p>辅助提示：这句话可能与材料不匹配或缺少依据。可「已知悉仍保留」继续，或编辑重核验 / 拒绝排除；不会把它记成材料已支持。</p>
        </div>
      </div>

      <div className="stack">
        {workflow.claim_verification.map((v) => {
          const claim = claimsById[v.claim_id]
          const d = claimDecisions[v.claim_id]
          const displayText =
            d?.decision === 'edit' && d.editedText != null ? d.editedText : claim?.text
          return (
            <article
              key={v.claim_id}
              id={v.claim_id}
              className={
                v.state === 'BLOCKED'
                  ? 'item-block claim blocked'
                  : v.state === 'NEEDS_REVIEW'
                    ? 'item-block claim needs'
                    : 'item-block claim'
              }
            >
              <div className="item-head">
                <ClaimBadge status={v.state} personal={workflow.grounding?.results[v.claim_id]?.verification_scope === 'personal'} />
                <span>
                  {v.claim_id.replace(/^claim_/, '陈述·')}: {displayText ?? '（草稿中缺失）'}
                </span>
              </div>
              <p>
                <strong>说明：</strong>
                {zhText(v.explanation)}
              </p>
              <p className="muted">
                {workflow.grounding ? '逐事实核验结果（不表示正确概率）' : `支持度 ${(v.support_score * 100).toFixed(0)}%`} · 是否锚定原文{' '}
                {v.grounded ? '是' : '否'}
              </p>
              {v.unsupported_fragments?.length ? (
                <div className="callout danger">
                  <h4>未支持片段</h4>
                  <ul>
                    {v.unsupported_fragments.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div className="evidence-box">
                <h4>证据</h4>
                {(claim?.evidence_ids ?? []).length === 0 ? (
                  <p className="danger-text">无证据编号</p>
                ) : (
                  <ul>
                    {claim!.evidence_ids.map((id) => (
                      <li key={id}>
                        <strong>{id}</strong> —{' '}
                        {evidenceIndex.get(id)?.description ?? '（种子中未找到描述）'}
                        {(id.startsWith('evloc_') || id.startsWith('ev_local_')) ? (
                          <LocalEvidencePeek
                            evidenceId={id.startsWith('ev_local_') ? id.replace('ev_local_', 'evloc_') : id}
                            claimText={displayText ?? claim?.text ?? ''}
                          />
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
                {localLinks
                  .filter((l) => l.target_id === v.claim_id)
                  .map((l) => (
                    <div key={l.link_id}>
                      <p className={l.link_state === 'STALE' ? 'danger-text' : 'muted'}>
                        本地关联 {l.evidence_id} · {l.link_state}
                      </p>
                      <LocalEvidencePeek
                        evidenceId={l.evidence_id}
                        claimText={displayText ?? claim?.text ?? ''}
                      />
                    </div>
                  ))}
              </div>
              <AtomicEvidence result={workflow.grounding?.results[v.claim_id]} />

              {v.state === 'VERIFIED' && (
                <p className="muted">
                  当前材料支持这句陈述；仍须核对原文和归属。修改后应重新核验。
                </p>
              )}

              {v.state === 'NEEDS_REVIEW' && (
                <div className="action-pad">
                  <p className="warn-text">{workflow.grounding ? '这句话可能与材料不完全匹配。可补证或编辑后重核验，也可「已知悉仍保留」或拒绝。' : '可能不匹配：请确认保留、编辑（将变为待重新核验）、或拒绝。'}</p>
                  {d?.decision === 'edit' && (
                    <textarea
                      className="jd-input"
                      rows={3}
                      value={d.editedText ?? claim?.text ?? ''}
                      onChange={(e) =>
                        setClaimDecision(v.claim_id, {
                          decision: 'edit',
                          editedText: e.target.value,
                          freshness: 'edited_pending_reverify',
                        })
                      }
                    />
                  )}
                  <div className="btn-row">
                    <button
                      type="button"
                      className={d?.decision === 'confirm' ? 'btn primary' : 'btn secondary'}
                      onClick={() =>
                        setClaimDecision(v.claim_id, {
                          decision: 'confirm',
                          freshness: 'as_returned',
                          editedText: undefined,
                        })
                      }
                    >
                      {workflow.grounding ? '已知悉可能不匹配，仍保留' : '确认保留原文'}
                    </button>
                    <button
                      type="button"
                      className={d?.decision === 'edit' ? 'btn primary' : 'btn secondary'}
                      onClick={() =>
                        setClaimDecision(v.claim_id, {
                          decision: 'edit',
                          editedText: claim?.text,
                          freshness: 'edited_pending_reverify',
                        })
                      }
                    >
                      编辑（待重新核验）
                    </button>
                    <button
                      type="button"
                      className={d?.decision === 'reject' ? 'btn danger' : 'btn secondary'}
                      onClick={() =>
                        setClaimDecision(v.claim_id, {
                          decision: 'reject',
                          freshness: 'rejected',
                        })
                      }
                    >
                      拒绝
                    </button>
                  </div>
                  {d?.freshness === 'edited_pending_reverify' && (
                    <p className="danger-text">
                      内容已修改。请点击「重新核验并更新风险」，在后端检查完成前不可导出。
                    </p>
                  )}
                </div>
              )}

              {workflow.grounding && v.state !== 'NEEDS_REVIEW' && <div className="action-pad">
                <button type="button" className="btn secondary" onClick={() => setClaimDecision(v.claim_id, {
                  decision:'edit', editedText:claim?.text, freshness:'edited_pending_reverify',
                })}>编辑后重新核验</button>
                {d?.decision === 'edit' && <textarea className="jd-input" rows={3}
                  value={d.editedText ?? claim?.text ?? ''} onChange={event => setClaimDecision(v.claim_id, {
                    decision:'edit',editedText:event.target.value,freshness:'edited_pending_reverify',
                  })} />}
              </div>}

              {v.state === 'BLOCKED' && (
                <div className="action-pad">
                  <p className="warn-text">
                    辅助提示：当前材料下这句话可能不匹配或缺少原件。可已知悉后仍保留并继续；这不会变成“材料已支持”，可复制稿也不会收录为已核验陈述。
                  </p>
                  {d?.decision === 'confirm' && (
                    <p className="muted">已记录：你已知悉可能不匹配，仍选择保留本句。</p>
                  )}
                  <div className="btn-row">
                    <button
                      type="button"
                      className={d?.decision === 'confirm' ? 'btn primary' : 'btn secondary'}
                      onClick={() =>
                        setClaimDecision(v.claim_id, {
                          decision: 'confirm',
                          freshness: 'as_returned',
                          editedText: undefined,
                        })
                      }
                    >
                      已知悉可能不匹配，仍保留
                    </button>
                    <button
                      type="button"
                      className={d?.decision === 'reject' ? 'btn danger' : 'btn secondary'}
                      onClick={() =>
                        setClaimDecision(v.claim_id, {
                          decision: 'reject',
                          freshness: 'rejected',
                        })
                      }
                    >
                      拒绝并排除
                    </button>
                  </div>
                </div>
              )}
            </article>
          )
        })}
      </div>

      {!proceedOk && (
        <div className="callout warn">
          仍有陈述待处理。阻断只是辅助提醒（可能不匹配），不是终局裁决：可点「已知悉可能不匹配，仍保留」，或「拒绝并排除」，也可编辑后重核验。
          个人教育资料按填写使用。不要把已编辑、尚未重核验的内容当作材料已支持。工作流状态：
          {workflow.workflow_status === 'BLOCKED' ? '已阻断（辅助）' : '等待人工确认'}
        </div>
      )}

      <div className="btn-row end">
        <button
          type="button"
          className="btn primary"
          disabled={!proceedOk}
          onClick={() => navigate('/ats')}
        >
          下一步：申请内容检查
        </button>
      </div>
    </section>
  )
}
