import {completeGuideStep, type GuideRequirement} from '../guide'
import {ActionButton} from '../components/ui/action-button'
import { useEffect, useMemo, useState } from 'react'
import { targetForClaim, getPendingRecheck, savePendingRecheck, clearPendingRecheck, type SupplementTarget } from '../resume/supplementRecheck'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getApiClient } from '../api/client'
import type { CareerVaultSeed, ClaimEvidenceCheck, EvidenceLink, EvidenceRecord, ResumeMatchItem } from '../api/types'
import { ClaimBadge, EmptyState } from '../components/States'
import {reviewMarks} from '../resume/reviewHighlights'
import {ClaimStatement} from '../components/ClaimStatement'
import { AtomicEvidence } from '../components/AtomicEvidence'
import { GroundingHistory } from '../components/GroundingHistory'
import { RadarDialog } from '../components/RadarDialog'
import {QuickReviewActions} from '../components/QuickReviewActions'
import { useDemo } from '../context/DemoContext'
import {evidenceCoverage, isQuantitative} from '../resume/claimReview'
import { zhText } from '../i18n'
import {isEducationProfile} from '../resume/review'

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
  const matches = record?.spans?.filter(span => span.raw_text.trim().length >= 4 && claimText.includes(span.raw_text.trim()))
  const hit = matches?.length === 1 ? matches[0] : undefined

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
    resumeForm,
    workflowSourceNotice,
    claimDecisions,
    setClaimDecision,
    finishReviewStep, reviewAdvanceReason,
    recheckAttempt, reverifyClaims,
    reviewDrafts, setReviewDraft, saveClaimEdit,
  } = useDemo()
  const attempt = recheckAttempt && recheckAttempt.application === workflow?.application_id &&
    recheckAttempt.candidate === workflow?.candidate_id ? recheckAttempt : null
  const rechecking = !!recheckAttempt?.running
  const runningElsewhere = rechecking && !attempt
  const [recheckError, setRecheckError] = useState('')
  const [confirmRecheck, setConfirmRecheck] = useState(false)
  const [supplement, setSupplement] = useState<{claimId:string;target:SupplementTarget}|null>(null)
  const [vault, setVault] = useState<CareerVaultSeed | null>(null)
  const [matches,setMatches] = useState<ResumeMatchItem[]>([])
  const [lookup,setLookup] = useState<'loading'|'ready'|'error'>('loading')
  const [localLinks, setLocalLinks] = useState<EvidenceLink[]>([])

  useEffect(() => {
    void fetch(`${import.meta.env.BASE_URL}data/career-vault.seed.json`)
      .then((r) => r.json())
      .then((d: CareerVaultSeed) => setVault(d))
      .catch(() => setVault(null))
  }, [])

  useEffect(() => {
    let active = true
    const api = getApiClient()
    setLookup('loading')
    setMatches([])
    setLocalLinks([])
    void (async () => {
      const [links, spaces] = await Promise.all([api.listEvidenceLinks({}), api.listEvidenceWorkspaces()])
      if (!active) return
      setLocalLinks(links.data ?? [])
      let preferred = ''
      try { preferred = localStorage.getItem('applyguard.evidence.workspaceId') ?? '' } catch { /* storage optional */ }
      const space = spaces.data?.find(s => s.workspace_id === preferred) ?? spaces.data?.[0]
      const match = space && resumeForm ? await api.matchResumeEvidence(space.workspace_id, {
        awards: resumeForm.awards?.map(a => ({...a,award_id:a.id})),
        projects: resumeForm.projects, internships: resumeForm.internships,
      }) : null
      if (!active) return
      setMatches(match?.data?.results ?? [])
      setLookup(links.error || spaces.error || match?.error ? 'error' : 'ready')
    })().catch(() => { if (active) setLookup('error') })
    return () => { active = false }
  }, [resumeForm])

  useEffect(() => {
    const id = location.hash.replace(/^#/, '')
    if (!id || !workflow) return
    const timer = window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 50)
    return () => window.clearTimeout(timer)
  }, [location.hash, workflow])

  useEffect(() => {
    if (!workflow || rechecking || Object.keys(reviewDrafts).length) return
    const pending=getPendingRecheck(sessionStorage)
    if (!pending?.ready || pending.candidate_id!==workflow.candidate_id || pending.application_id!==workflow.application_id) return
    clearPendingRecheck(sessionStorage)
    setRecheckError('')
    void reverifyClaims()
  }, [workflow, reverifyClaims, rechecking, reviewDrafts])

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
  const profile = (id:string) => isEducationProfile(claimsById[id],resumeForm)
  const rows = workflow.claim_verification
  const pendingEdits: GuideRequirement[] = Object.keys(reviewDrafts).map(id => {
    const index = rows.findIndex(row => row.claim_id === id)
    return index < 0
      ? {id, href: '/resume', label: '打开简历审查，保存或取消暂存的修改。'}
      : {id, selector: '#edit-' + CSS.escape(id), label: `第 ${index + 1} 条陈述还在编辑。在蓝框内选择“保存修改”或“取消编辑”。`}
  })
  const hasExperience = workflow.resume_claims.some(c => !profile(c.claim_id) && claimDecisions[c.claim_id]?.decision !== 'reject')
  const guidance = rechecking ? [{id:'running', selector:'#claims-progress', label:'已有核验正在运行，请等待结果。'}] : pendingEdits
  const blockedReason = rechecking ? guidance[0].label : pendingEdits.length ? '有未保存的陈述：' + pendingEdits.map(edit => edit.label.split('。')[0]).join('、') : !hasExperience ? '请在简历正文中保留至少一条经历，再启动模型核验。' : undefined
  const failed = !workflow.requires_reverification && workflow.grounding?.error
  const kept = workflow.resume_claims.filter(c => claimDecisions[c.claim_id]?.decision !== 'reject').length
  const nextReason = reviewAdvanceReason
  function advance() {
    if (finishReviewStep(true)) { completeGuideStep('claims'); navigate('/ats') }
  }

  const cardData = rows.map((verification,index) => {
    const id = verification.claim_id
    const claim = claimsById[id]
    const decision = claimDecisions[id]
    const result = workflow.grounding?.results[id]
    const personal = profile(id)
    const editing = Object.hasOwn(reviewDrafts, id)
    const needsDecision = !personal && verification.state !== 'VERIFIED'
    const supplementTarget = targetForClaim(id,resumeForm)
    const canEdit = !personal
    const needsRecheck = workflow.requires_reverification || decision?.freshness === 'edited_pending_reverify'
    const text = editing ? reviewDrafts[id] : claim?.text
    const materials = new Map<string, { id: string; state?: EvidenceLink['link_state'] }>()
    const evidenceKey = (rawId: string) => rawId.replace(/^ev_local_/, 'evloc_')
    for (const source of result?.retrieved_sources ?? []) materials.set(evidenceKey(source.evidence_id), {id:source.evidence_id})
    for (const evidenceId of claim?.evidence_ids ?? []) {
      if (evidenceId.startsWith('ev_draft_') || result?.excluded_links?.some(x => evidenceKey(x.evidence_id) === evidenceKey(evidenceId))) continue
      if (result && !result.retrieved_sources.some(source => evidenceKey(source.evidence_id) === evidenceKey(evidenceId))) continue
      materials.set(evidenceKey(evidenceId), { id: evidenceId })
    }
    const scopedLinks = localLinks.filter(link => link.link_state === 'ACTIVE'
      && ((link.target_type === 'claim' && link.target_id === id) || (supplementTarget && link.target_id === supplementTarget.target_id &&
        [supplementTarget.target_type, 'experience'].includes(link.target_type)))
      && !result?.excluded_links?.some(x => evidenceKey(x.evidence_id) === evidenceKey(link.evidence_id)))
    for (const link of scopedLinks) {
      const key = evidenceKey(link.evidence_id)
      materials.set(key, { id: materials.get(key)?.id ?? link.evidence_id, state: link.link_state })
    }
    const atomTexts = new Set(result?.atoms.map(atom => atom.text))
    const extraFragments = (verification.unsupported_fragments ?? []).filter(fragment => !atomTexts.has(fragment))
    const stateClass = personal ? '' : verification.state === 'BLOCKED' ? 'blocked' : verification.state === 'NEEDS_REVIEW' ? 'needs' : ''
    const title = `第 ${index + 1} 条陈述`

    const currentCheck = !personal && !failed && !needsRecheck && !editing && result?.final_text===text
    const candidate = matches.find(m => m.target_type === supplementTarget?.target_type && m.target_id === supplementTarget.target_id &&
      !!m.evidence_id && ['MATCHED','NEEDS_CONFIRM','CONFLICT'].includes(m.status) &&
      !result?.excluded_links?.some(x => evidenceKey(x.evidence_id) === evidenceKey(m.evidence_id!)))
    const coverage = evidenceCoverage(result, scopedLinks.length > 0, !!candidate, !!currentCheck, lookup)
    const currentText = !failed && !needsRecheck && !editing && (!result || result.final_text===text)
    const historicalCheck = Boolean(workflow._historyReplay && !editing && result?.final_text===text)
    const marks = reviewMarks(text ?? '',result,!!currentText || historicalCheck,needsDecision && !editing && decision?.decision!=='reject', verification.unsupported_fragments)
    const candidatePath = candidate && supplementTarget ? '/evidence?' + new URLSearchParams({view:'materials',return_claim:id,
      target_type:supplementTarget.target_type,target_id:supplementTarget.target_id,evidence_id:candidate.evidence_id!}) : ''
    return {verification, id, claim, decision, result, personal, editing, needsDecision, supplementTarget, canEdit, needsRecheck, text, materials, evidenceKey, extraFragments, stateClass, title, coverage, marks, candidate, candidatePath}
  })
  const report = workflow.grounding
  const receipt = !workflow.requires_reverification && report?.fresh_atomic && report.operation === 'verify' ? report : null
  const checked = receipt ? Object.values(receipt.results).filter(r => r.verification_scope === 'experience') : []
  const withoutSources = checked.filter(r => r.material_status === 'no_related_material')
  const firstCandidate = cardData.find(c => c.candidatePath)
  const totals = new Map<string,number>()
  for (const card of cardData) {
    const label = card.personal ? '个人资料' : card.coverage.label
    totals.set(label,(totals.get(label) ?? 0)+1)
  }

  return (
    <section className="panel claim-verification-page">
      <header className="panel-head">
        <h2>陈述核验</h2>
        {workflowSourceNotice && <p className="callout warn">{workflowSourceNotice}</p>}
      </header>

      <QuickReviewActions/>
      <div className="claim-overview">
        <div className="claim-summary" aria-label="核验结果汇总">
          {[...totals].map(([label,count]) => <div key={label}><strong>{count}</strong><span>{label}</span></div>)}
        </div>
        <ActionButton id="claims-recheck" type="button" className="btn primary" guideRequirements={guidance} disabledReason={blockedReason} disabled={!!blockedReason} onClick={() => setConfirmRecheck(true)}>
          {rechecking ? '正在核验当前正文…' : failed ? '重新核验当前正文' : '启动 AI 原子核验'}
        </ActionButton>
      </div>

      {rechecking && <p id="claims-progress" role="status" className="callout">{runningElsewhere ? '另一份草稿正在核验，完成后可核验当前正文。' : '已发送新的核验请求，正在等待模型。可以切到站内其他页面，回来查看结果。'}</p>}
      {attempt?.error && <p role="alert" className="callout warn">{attempt.error}</p>}
      {workflow._historyReplay && <p className="callout warn" role="status"><strong>历史回放：</strong>{workflow._historyReplay.label}。你可以编辑或保留正文，当前材料仍需重新核验。{workflow._historyReplay.legacy ? ' 此旧版未保存逐项核验引用。' : '下方为当时的核验结果。'}</p>}
      <GroundingHistory />
      {receipt && !attempt?.error && !rechecking && <div role="status" className={receipt.error ? 'callout warn' : 'callout'} data-testid="verification-receipt">
        <strong>{receipt.error ? '后端已返回，本次核验未完成' : '本次模型核验已返回'}</strong>
        <p>{receipt.at && new Date(receipt.at).toLocaleTimeString()} · 后端耗时 {((receipt.elapsed_ms ?? 0) / 1000).toFixed(1)} 秒 · 运行编号 <code>{receipt.run_id}</code></p>
        {!receipt.error && <p>{checked.length} 条经历中，{checked.length - withoutSources.length} 条按关联材料核对，{withoutSources.length} 条缺少关联原件。{withoutSources.length > 0 && '模型已列出待核对事实，这些事实仍待复核。'}</p>}
        {!!receipt.model_routing?.response_models?.length && <p>响应模型 · {receipt.model_routing.response_models.join('、')}</p>}
        {withoutSources.length > 0 && <Link to={firstCandidate?.candidatePath || '/evidence?view=materials'}>{firstCandidate ? '核对并关联已有文件' : '去补充证明材料'}</Link>}
      </div>}
      <div className="claim-ink-legend" aria-label="正文标色说明">
        <span className="claim-ink claim-ink-pending">蓝色 · 待核对</span>
        <span className="claim-ink claim-ink-conflict">红色 · 材料冲突</span>
        <span>点击正文中的彩色词句可查看原因。</span>
      </div>
      {failed && !attempt?.error && !rechecking && <div role="alert" className="callout warn"><strong>{workflow.grounding?.error_code && workflow.grounding.failure_stage ? workflow.grounding.failure_stage+'未完成' : '本次核验未完成'}</strong>
        <p>{failed}</p><p>先处理上方提示，再点击“重新核验当前正文”。本次失败本身无需修改简历文字。</p></div>}
      {confirmRecheck && <RadarDialog title="确认启动 AI 原子核验" onClose={() => setConfirmRecheck(false)}>
        <p>当前正文、岗位说明和关联材料将发送到配置的模型服务，可能产生费用。教育等个人资料按表单使用。</p>
        <p>每次确认都会重新请求模型。有原件的经历逐项对照材料；缺少关联原件的经历会拆出待核对事实。</p>
        <div className="btn-row"><button type="button" className="btn secondary" onClick={() => setConfirmRecheck(false)}>取消</button><button type="button" className="btn primary" onClick={() => {
          setConfirmRecheck(false)
          setRecheckError('')
          void reverifyClaims()
        }}>同意并开始核验</button></div>
      </RadarDialog>}
      {supplement && <RadarDialog title="补充材料并自动核验" onClose={()=>setSupplement(null)}>
        <p>请选择并确认关联这条经历的材料。关联完成后会自动返回此页，对当前正文重新运行 AI 原子核验。</p>
        <p>岗位说明、正文和关联材料会发送到配置的模型服务，可能产生费用；核验不会自动修改正文。</p>
        <div className="btn-row"><button type="button" className="btn secondary" onClick={()=>setSupplement(null)}>取消</button><button type="button" className="btn primary" onClick={()=>{
          try {
            savePendingRecheck(sessionStorage,{...supplement.target,claim_id:supplement.claimId,candidate_id:workflow.candidate_id,application_id:workflow.application_id,created_at:Date.now(),ready:false})
            const query=new URLSearchParams({view:'relations',target_type:supplement.target.target_type,target_id:supplement.target.target_id})
            setSupplement(null);navigate(`/evidence?${query}`)
          } catch {setSupplement(null);setRecheckError('无法暂存自动核验请求，请检查浏览器存储后重试。')}
        }}>同意并选择材料</button></div>
      </RadarDialog>}
      {workflow.requires_reverification && <p className="callout warn" role="status">请重新核验当前草稿，更新材料支持状态。</p>}
      {recheckError && recheckError !== failed && <p className="danger-text" role="alert">{recheckError}</p>}
      <details className="claim-help">
        <summary>核验状态说明</summary>
        <ul>
          <li><strong>已核验</strong> · 当前表述有材料支持，仍需核对原文和归属。</li>
          <li><strong>待复核 / 已阻断</strong> · 可以补充材料、修改陈述、保留或排除。保留后，材料核验状态仍会显示。</li>
          <li><strong>个人资料</strong> · 按表单填写的信息使用。</li>
        </ul>
      </details>

      <div className="stack claim-cards">
        {cardData.map(({verification, id, claim, decision, result, personal, editing, needsDecision, supplementTarget, canEdit, needsRecheck, text, materials, evidenceKey, extraFragments, stateClass, title, coverage, marks, candidate, candidatePath}) => {
          return (
            <article key={id} id={id} className={`item-block claim ${stateClass}`} aria-labelledby={`title-${id}`}>
              <header className="claim-card-heading">
                <h3 id={`title-${id}`}>{title}</h3>
                <ClaimBadge status={personal ? "VERIFIED" : verification.state} personal={personal} />
                {decision?.decision === 'confirm' && <span className="claim-choice">已选择保留</span>}
                {decision?.decision === 'reject' && <span className="claim-choice">已排除</span>}
                {editing && <span className="claim-choice">编辑中 · 待重新核验</span>}
              </header>

              {editing ? (
                <div className="claim-edit-fields">
                  <label htmlFor={`text-${id}`}>{title} · 修改正文</label>
                  <textarea id={`text-${id}`} className="jd-input" rows={4} value={text ?? ''} maxLength={420}
                    onChange={event => setReviewDraft(id,event.target.value)} />
                  {!text?.trim() && <p role="status">请填写陈述，或取消本次编辑。</p>}
                  <div className="btn-row" id={`edit-${id}`}><button type="button" className="btn primary" disabled={!text?.trim() || text.trim().length>420}
                    onClick={() => saveClaimEdit(id,text ?? '')}>保存修改</button>
                    <button type="button" className="btn secondary" onClick={() => setReviewDraft(id,null)}>取消编辑</button></div>
                </div>
              ) : <ClaimStatement id={id} text={text ?? '草稿中缺少该条陈述。'} marks={marks} />}

              {needsDecision && !editing && decision?.decision !== 'reject' && !marks.length && <p className="claim-meta">这条陈述仍待核对。当前结果未定位到具体词句，可展开核验明细。</p>}
              {personal && <p className="claim-meta">教育信息按经历库表单填写使用；如需修改，请到<Link to="/vault">经历库</Link>编辑。</p>}
              {!personal && <p className="claim-meta"><strong>{coverage.label}</strong>
                {coverage.supported.length > 0 && <> · 已有原文支持 {coverage.supported.length} 项</>}
                {candidate && <>{' · '}<Link to={candidatePath}>核对并关联已有文件「{candidate.relative_path?.split(/[\\/]/).pop() || '查看原件'}」</Link></>}
              </p>}

              {needsDecision && !editing && decision?.decision !== 'reject' && <div className="claim-review-reason">
                <strong>{needsRecheck ? '这条陈述需要重新核验' : failed && verification.state==='NEEDS_REVIEW' ? '尚未取得核验结论' : '需要核对的事实'}</strong>
                <p>{failed && verification.state==='NEEDS_REVIEW' ? <>本次检查中断，暂时无法定位需要修改的词句。<a href="#claims-recheck" onClick={event=>{event.preventDefault();const button=document.getElementById('claims-recheck');button?.scrollIntoView({block:'center'});button?.focus()}}>去页首重新核验</a></> : needsRecheck ? '正文或材料已变化，可重新核验最新版本。' : coverage.related
                  ? coverage.supported.length ? '已获支持的细节可在明细里查看。只需核对下面列出的部分。' : '请对照原件。只有材料明确提到的事实才能标为已支持。'
                  : candidate ? '材料库中已有候选原件。核对文件并关联到这条经历后，即可重新核验。'
                  : lookup === 'ready' ? '可以关联已有材料或上传原件，也可以直接进入下一步，按本人陈述保留。' : coverage.label}</p>
                {coverage.unresolved.map(atom=>{
                  const excerpt = (atom.claim_excerpt || atom.text).trim().replace(/[。；;.]$/, '')
                  const located = excerpt.length>=2 && !!text && text.includes(excerpt) && text.indexOf(excerpt)===text.lastIndexOf(excerpt)
                  return <div className="claim-fact-reason" key={atom.atom_id}>
                    <strong>{atom.relation==='CONTRADICTED' && atom.citations.some(c=>c.quote) ? '材料与表述冲突' : isQuantitative(atom.claim_excerpt || atom.text) ? '量化细节待确认' : '这项细节待确认'}</strong>
                    <p>{located ? <>核对原文「{excerpt}」</> : <>待核对事实（未能定位到唯一原文）：“{atom.text}”</>}</p>
                    <p>{atom.reason || '当前材料未能支持这项事实。'}</p>
                    {atom.relation==='CONTRADICTED' && atom.citations.filter(c=>c.quote).map((c,i) => <blockquote key={i}>材料原文「{c.quote}」</blockquote>)}
                  </div>
                })}
                {supplementTarget ? <ActionButton type="button" className="btn secondary" disabled={!!blockedReason} disabledReason={blockedReason} guideRequirements={guidance} onClick={()=>setSupplement({claimId:id,target:supplementTarget})}>补充材料并自动核验</ActionButton> : <p className="muted">这条手写内容尚未对应经历库条目；可先在<Link to="/vault">经历库</Link>添加经历，再关联材料。</p>}
              </div>}

              <div className="claim-card-controls">
                {!personal && <details className="claim-details">
                  <summary>
                    {needsRecheck ? '材料与上次核验' : '材料与核验明细'}
                    <span>{` · ${materials.size} 份材料`}</span>
                  </summary>
                  {verification.explanation && result?.material_status!=='no_related_material' && <p className="claim-detail-note">{zhText(verification.explanation)}</p>}
                  {extraFragments.length > 0 && (
                    <div className="claim-details-group">
                      <h4>待核对片段</h4>
                      <ul>{extraFragments.map((fragment, index) => <li key={index}>{fragment}</li>)}</ul>
                    </div>
                  )}
                  {workflow._historyReplay?.legacy ? <p>旧版历史未保存逐项核验引用，请按当前材料重新核验。</p> : <AtomicEvidence result={result} historical={!!workflow._historyReplay} />}
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
                </details>}

                {(needsDecision || canEdit) && <div className="btn-row claim-action-bar" id={'actions-'+id}>
                  {canEdit && !editing && !rechecking && (
                    <button type="button" className="btn secondary"
                      onClick={() => {setReviewDraft(id,claim?.text ?? ''); requestAnimationFrame(() => document.getElementById('text-'+id)?.focus())}}>
                      编辑陈述
                    </button>
                  )}
                  {canEdit && !editing && !rechecking && (
                    <button type="button" className="btn secondary" aria-pressed={decision?.decision === 'reject'}
                      onClick={() => setClaimDecision(id, decision?.decision === 'reject' ? {decision:null, freshness:'as_returned'} : {decision:'reject', freshness:'rejected'})}>
                      {decision?.decision === 'reject' ? '撤销排除' : '排除'}
                    </button>
                  )}
                </div>}
              </div>
            </article>
          )
        })}
      </div>

      <div className="claim-page-footer">
        <p className="muted" role="status">{nextReason ?? `将保存当前编辑并保留 ${kept} 条陈述。待确认和冲突会随个人稿保留记录。`}</p>
        <ActionButton id="claims-next" type="button" className="btn primary" guideRequirements={pendingEdits} disabledReason={nextReason} disabled={!!nextReason} onClick={advance}>
          知悉并保留，下一步：申请内容检查
        </ActionButton>
      </div>
    </section>
  )
}
