import {completeGuideStep,editingRequirements} from '../guide'
import {ActionButton} from '../components/ui/action-button'
import { useEffect, useMemo, useState } from 'react'
import {claimsFromResumeForm,remainingDraftClaims,initializeDraftSelection,addDraftClaim} from '../resume/draftSelection'
import { Link, useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/States'
import { ReviewDraft } from '../components/ReviewDraft'
import { saveTextVersion } from '../resume/groundingHistory'
import {QuickReviewActions} from '../components/QuickReviewActions'
import { useDemo } from '../context/DemoContext'
import { Icon } from '../components/Icon'

export function ResumeReviewPage() {
  const navigate = useNavigate()
  const { workflow, patchWorkflow, resumeForm, reviewDrafts, finishReviewStep, reviewAdvanceReason } = useDemo()
  const [draftText, setDraftText] = useState('')
  const [historyError,setHistoryError] = useState('')
  const [sourceQuery,setSourceQuery] = useState('')
  const [sourceKind,setSourceKind] = useState('all')

  const draftClaims = useMemo(() => claimsFromResumeForm(resumeForm), [resumeForm])
  const draftById = useMemo(() => new Map(draftClaims.map((c) => [c.claim_id, c])), [draftClaims])

  useEffect(()=>{
    if(!workflow||!resumeForm||Object.keys(reviewDrafts).length)return
    if(initializeDraftSelection(workflow,resumeForm)!==workflow)
      patchWorkflow(previous=>initializeDraftSelection(previous,resumeForm))
  },[workflow,resumeForm,reviewDrafts,patchWorkflow])

  if (!workflow) {
    return (
      <section data-guide="review-editing" className="panel">
        <header className="panel-head">
          <h2>简历审查</h2>
        </header>
        <EmptyState
          title="无工作流数据"
          detail="请先在岗位说明页分析。结果会预存到本机后端，源头变更后需重新分析。"
          actionLabel="去岗位说明"
          onAction={() => navigate('/jd')}
        />
      </section>
    )
  }

  const { resume_claims: claims, resume_selection: selection } = workflow
  const usingDraftVault = workflow.component_modes?.career_vault === 'LOCAL_RESUME_DRAFT'
  const available = draftClaims.length?remainingDraftClaims(workflow,resumeForm):selection.removed_claims
    .filter(row=>!claims.some(claim=>claim.claim_id===row.claim_id))
    .map(row=>({claim_id:row.claim_id,text:row.text||row.claim_id,evidence_ids:[] as string[],experienceTitle:'工作流候选经历',kind:'陈述'}))

  const seedLike =
    !usingDraftVault &&
    draftClaims.length > 0 &&
    claims.some((c) => !draftById.has(c.claim_id)) &&
    /lora|pipeline|fullstack|python_api/i.test(claims.map((c) => c.claim_id).join(' '))

  const visibleSources = available.filter(item => (sourceKind === 'all' || item.kind === sourceKind) &&
    (item.text+' '+item.experienceTitle).toLocaleLowerCase().includes(sourceQuery.trim().toLocaleLowerCase()))
  const characters = claims.reduce((sum,claim) => sum+Array.from(claim.text).length,0)

  function addClaim(input:{claim_id:string;text:string;evidence_ids:string[]}) {
    if(!workflow)return
    try {
      const next=addDraftClaim(workflow,input)
      if(next===workflow)return
      saveTextVersion(workflow,'补选经历前')
      patchWorkflow(next);setHistoryError('')
    } catch(error){setHistoryError(error instanceof Error?error.message:'补选未完成，正文保留。')}
  }
  function clearSeedDraft() {
    if(!workflow)return
    try {saveTextVersion(workflow,'清空前自动备份')} catch {setHistoryError('历史保存失败，尚未清空草稿。');return}
    patchWorkflow(previous=>({...previous,resume_claims:[],claim_verification:[],
      resume_selection:{...previous.resume_selection,draft_initialized:true,removed_claims:[]}}))
  }

  function addCustom() {
    const text = draftText.trim()
    if (!text) return
    addClaim({
      claim_id: `claim_manual_${Date.now().toString(36)}`,
      text,
      evidence_ids: [],
    })
    setDraftText('')
  }

  return (
    <section data-guide="review-editing" className="panel">
      <header className="panel-head">
        <h2>审核申请草稿</h2>
        <QuickReviewActions/>
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
          {selection.draft_notice || `正文来自经历库；还有 ${available.length} 条可补选。`}
          {resumeForm?.dirty && <span> 经历库修改尚未最终保存，此处先作为申请草稿使用。</span>}
        </p>
      )}

      <div className="draft-summary-strip">
        <div><strong>{claims.length}</strong><span>条草稿</span></div>
        <div><strong>{characters}</strong><span>个字符</span></div>
        <p>按岗位相关度查看经历，可补选到正文或手动移除。<br /><span>进入正文不代表事实已经核验。</span></p>
      </div>

      <div className="review-content">
      {historyError && <p className="danger-text" role="alert">{historyError}</p>}
      <ReviewDraft key={workflow.application_id} />
      <section className="review-source-picker" id="review-source-pool" data-guide="draft-pool" aria-label="补充经历">
        <div className="source-pool-heading"><h3>从经历库补选</h3><span>{available.length} 条尚未加入正文</span></div>
        <p className="muted">已在正文中的经历不重复显示；选择后直接加入，正文里的经历可随时移除。</p>
        <div className="review-source-controls">
          <label className="work-search source-search"><Icon name="search" /><input aria-label="搜索可补选的经历" value={sourceQuery} onChange={e=>setSourceQuery(e.target.value)} placeholder="搜索项目名、技术或经历内容" />
            {sourceQuery&&<button type="button" aria-label="清除经历搜索" onClick={()=>setSourceQuery('')}><Icon name="close" /></button>}</label>
          <label>经历类型<select aria-label="筛选经历类型" value={sourceKind} onChange={e=>setSourceKind(e.target.value)}>{['all','实习','项目','获奖'].map(kind=><option key={kind} value={kind}>{kind==='all'?'全部类型':kind}</option>)}</select></label>
          <label>选择经历<select aria-label="选择要补选的经历" value="" onChange={e=>{const entry=available.find(row=>row.claim_id===e.target.value);if(entry)addClaim(entry)}}>
            <option value="">选择后加入正文…</option>{visibleSources.map(row=><option key={row.claim_id} value={row.claim_id}>{row.kind} · {row.experienceTitle}</option>)}
          </select></label>
        </div>
        {!available.length?<p>可用经历都已在正文中；也可以去<Link to="/vault">经历库</Link>继续新增。</p>:
          !visibleSources.length?<p>没有找到匹配项，请换个关键词或类型。</p>:
          <details><summary>浏览可补选经历（{visibleSources.length}）</summary><div className="review-source-results">{visibleSources.map(row=><article key={row.claim_id}>
            <div><strong>{row.experienceTitle}</strong><span className="muted">{row.kind}</span><p>{row.text}</p></div>
            <button className="btn secondary" type="button" onClick={()=>addClaim(row)}>加入正文</button>
          </article>)}</div></details>}
      </section>
      <details className="review-add-content"><summary>自行填写补充内容</summary>
        <label className="field-label" htmlFor="rr-manual">补充句子</label>
        <textarea id="rr-manual" maxLength={420} className="jd-input" rows={3} value={draftText} onChange={e=>setDraftText(e.target.value)} placeholder="也可以自行填写尚未整理进经历库的内容…" />
        <ActionButton type="button" className="btn secondary" disabledReason={claims.length>=20?'每份草稿最多 20 条，请先移出不需要的经历。':'请先填写补充内容。'} disabled={!draftText.trim()||claims.length>=20} onClick={addCustom}>加入正文</ActionButton>
      </details></div>
      <div className="btn-row end review-footer">
        <span role="status">{Object.keys(reviewDrafts).length ? '进入下一步时会保存当前编辑。' : claims.length ? `已整理 ${claims.length} 条正文，可预览并导出。` : '请先选择或写入一条草稿陈述。'}</span>
        <ActionButton type="button" className="btn primary" disabledReason={!claims.length?'请先加入至少一条草稿。':'请先保存或取消正在编辑的句子。'} guideRequirements={[...editingRequirements(reviewDrafts),...(!claims.length?[{id:'claims',label:'请先选择或写入一条草稿。',selector:'[data-guide="draft-pool"]'}]:[])]} disabled={!claims.length || !!Object.keys(reviewDrafts).length} onClick={() => {
          const panel = document.getElementById('review-export') as HTMLDetailsElement | null
          if (panel) {panel.open = true; panel.scrollIntoView({behavior:'smooth',block:'start'});panel.querySelector('summary')?.focus()}
        }}>检查并导出</ActionButton>
        <ActionButton type="button" className="btn secondary" disabledReason={reviewAdvanceReason} guideRequirements={editingRequirements(reviewDrafts)}
          disabled={!!reviewAdvanceReason} onClick={() => {if (finishReviewStep(false)) {completeGuideStep('resume');navigate('/claims')}}}>
          继续核验并准备网申
        </ActionButton>
      </div>
    </section>
  )
}
