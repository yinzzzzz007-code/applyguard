import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiClient } from '../api/client'
import type { CareerVaultSeed, ClaimEvidenceCheck, EvidenceLink, EvidenceRecord } from '../api/types'
import { ClaimBadge, EmptyState } from '../components/States'
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
  const {
    workflow,
    claimDecisions,
    setClaimDecision,
    canProceedFromClaims,
  } = useDemo()
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
    return map
  }, [vault])

  if (!workflow) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>陈述核验</h2>
        </header>
        <EmptyState
          title="无核验数据"
          detail="请先运行工作流。"
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
        <p>逐条查看简历陈述的证据与处理方式。</p>
      </header>

      <div className="claim-status-guide" aria-label="核验状态说明">
        <div className="claim-status-guide-item">
          <ClaimBadge status="VERIFIED" />
          <p>当前表述有经历库证据支持，可继续使用；这不等于外部事实已被独立证明。</p>
        </div>
        <div className="claim-status-guide-item">
          <ClaimBadge status="NEEDS_REVIEW" />
          <p>证据或措辞还需人工判断。查看来源后可保留原文或拒绝；修改后须重新核验。</p>
        </div>
        <div className="claim-status-guide-item">
          <ClaimBadge status="BLOCKED" />
          <p>存在无法支持的内容。不能确认或复制，须拒绝并排除后才能继续查看后续步骤。</p>
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
              className={
                v.state === 'BLOCKED'
                  ? 'item-block claim blocked'
                  : v.state === 'NEEDS_REVIEW'
                    ? 'item-block claim needs'
                    : 'item-block claim'
              }
            >
              <div className="item-head">
                <ClaimBadge status={v.state} />
                <span>
                  {v.claim_id.replace(/^claim_/, '陈述·')}: {displayText ?? '（草稿中缺失）'}
                </span>
              </div>
              <p>
                <strong>说明：</strong>
                {zhText(v.explanation)}
              </p>
              <p className="muted">
                支持度 {(v.support_score * 100).toFixed(0)}% · 是否锚定原文{' '}
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
                        {id.startsWith('evloc_') ? (
                          <LocalEvidencePeek
                            evidenceId={id}
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

              {v.state === 'VERIFIED' && (
                <p className="muted">
                  已核验：表示相对经历库元数据可支持原文，不等于外部事实证明。无需额外操作即可进入后续（除非你编辑）。
                </p>
              )}

              {v.state === 'NEEDS_REVIEW' && (
                <div className="action-pad">
                  <p className="warn-text">需要处理：确认保留、编辑（将变为待重新核验）、或拒绝。</p>
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
                      确认保留原文
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
                      内容已修改。后端暂无重新核验接口：保持「待重新核验」，不能作为已通过内容继续使用。
                    </p>
                  )}
                </div>
              )}

              {v.state === 'BLOCKED' && (
                <div className="action-pad">
                  <p className="danger-text">
                    已阻断：禁止确认为通过。只能拒绝并排除，相关网申字段也不可靠确认绕过。
                  </p>
                  <div className="btn-row">
                    <button type="button" className="btn secondary" disabled>
                      确认（禁用）
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
          请处理全部待复核项；拒绝全部已阻断项；不要把已编辑未重核验的内容当作通过。工作流状态：
          {workflow.workflow_status === 'BLOCKED' ? '已阻断' : '等待人工确认'}
        </div>
      )}

      <div className="btn-row end">
        <button
          type="button"
          className="btn primary"
          disabled={!proceedOk}
          onClick={() => navigate('/ats')}
        >
          下一步：网申模拟
        </button>
      </div>
    </section>
  )
}
