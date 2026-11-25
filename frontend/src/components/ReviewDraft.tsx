import {usePolishJob} from '../resume/usePolishJob'
import {relevanceFor, STRONG_MATCH_SCORE} from '../resume/draftSelection'
import {removeDraftClaim} from '../resume/draftSelection'
import {ActionButton} from './ui/action-button'
import { useLocation } from 'react-router-dom'
import { getApiClient } from '../api/client'
import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import {resumePolishOperationLock} from '../resume/operationLock'
import type { WorkflowResponse } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { changeClaim, currentSupport, diffSpans, needsAttention, proposalNeedsReview, proposalStatus, reviewPriority, session, isEducationProfile } from '../resume/review'
import { saveTextVersion } from '../resume/groundingHistory'
import { AtomicEvidence } from './AtomicEvidence'
import { GroundedExport } from './GroundedExport'
import { SAGPolishPanel, type SAGPolishHandle } from './SAGPolishPanel'
import { HistoryReplayNotice } from './HistoryReplayNotice'

export function ReviewDraft() {
  const location = useLocation()
  const {workflow,resumeForm,setWorkflow,reviewDrafts:drafts,setReviewDraft:onEdit,reviewStorageError} = useDemo()
  const [undo,setUndo] = useState<WorkflowResponse[]>([])
  const [notice,setNotice] = useState('')
  const polishJob=usePolishJob()
  const polishBusy=useSyncExternalStore(resumePolishOperationLock.subscribe,resumePolishOperationLock.isLocked)||polishJob.running
  const [cloudIssue,setCloudIssue] = useState('正在检查云端模型配置…')
  useEffect(() => {
    let active = true
    async function check() {
      const {data} = await getApiClient().getHealth()
      if (active) setCloudIssue(!data ? '无法连接本机服务，请检查服务后刷新页面。'
        : data.cloud_model_configured === false ? '请先在右上角「模型设置」中配置服务地址、模型和 API Key。' : '')
    }
    void check()
    window.addEventListener('focus',check)
    window.addEventListener('applyguard:model-settings-updated',check)
    return () => {active = false; window.removeEventListener('focus',check); window.removeEventListener('applyguard:model-settings-updated',check)}
  },[])
  const [selectedId,setSelectedId] = useState('')
  const [toolsOpen,setToolsOpen] = useState(() => window.matchMedia('(min-width:761px)').matches)
  const exportPanel = useRef<HTMLDetailsElement>(null)
  const polishPanel = useRef<SAGPolishHandle>(null)
  useLayoutEffect(() => {
    const panel = exportPanel.current
    if (location.hash !== '#review-export' || !panel) return
    panel.open = true
    const frame = requestAnimationFrame(() => panel.scrollIntoView({ block: 'start' }))
    return () => cancelAnimationFrame(frame)
  }, [location.hash])
  if (!workflow) return null
  const priority = [...workflow.resume_claims].sort((a,b) => reviewPriority(workflow,b.claim_id)-reviewPriority(workflow,a.claim_id))
    .filter(c => reviewPriority(workflow,c.claim_id)>0).slice(0,3)
  const selected = workflow.resume_claims.find(c => c.claim_id === selectedId) ?? workflow.resume_claims[0]
  const row = selected ? workflow.grounding?.results[selected.claim_id] : undefined
  const proposal = row?.proposed_text
  const proposedChange = Boolean(selected && proposal && proposal !== selected.text)
  const parts = selected && proposal ? diffSpans(row?.original_text ?? selected.text,proposal) : null
  const editing = Object.keys(drafts).length > 0
  const metrics = session(workflow)

  function commit(id: string, text: string, action: 'original'|'edit'|'accept') {
    if (!workflow) return false
    try {
      const next = changeClaim(workflow,id,text,action)
      saveTextVersion(workflow,'逐句编辑前')
      saveTextVersion(next,action === 'original' ? '保留当前句' : action === 'edit' ? '保存修改' : '用户采用建议')
      setUndo(values => [...values,workflow].slice(-20)); setWorkflow(next)
      onEdit(id,null); setNotice('文字已保存；材料检查状态单独记录。'); return true
    } catch (error) {setNotice(error instanceof Error ? error.message : '保存失败，草稿未变。');return false}
  }
  function focusClaim(id: string) {
    setSelectedId(id)
    document.getElementById(`edit-${id}`)?.focus()
  }
  return <div className="review-editor">
    <HistoryReplayNotice />
    <SAGPolishPanel ref={polishPanel} cloudIssue={cloudIssue} job={polishJob} />
    <div className="review-workspace">
      <div className="review-draft">
        <div className="review-document-heading" data-guide="draft-document"><h3>完整草稿</h3><span role="status">{editing ? `${Object.keys(drafts).length} 处输入已暂存，尚未保存到正文` : '正文已保存到本标签页'}</span></div>
        <p className="muted">直接编辑句子；选择一条后，可查看建议和材料依据。暂存输入切页后仍保留。</p>
        {reviewStorageError && <p className="danger-text" role="alert">{reviewStorageError}</p>}
        {!!priority.length && <div className="review-priority"><span>建议先看</span>{priority.map(c => <button type="button" className="text-action" key={c.claim_id} onClick={() => focusClaim(c.claim_id)}>第 {workflow.resume_claims.indexOf(c)+1} 条</button>)}</div>}
        {!workflow.resume_claims.length && <p>正文还没有经历。请从下方“从经历库补选”搜索或选择。</p>}
        {workflow.resume_claims.map((claim,index) => {
          const pending = drafts[claim.claim_id]
          const matchScore = Number((relevanceFor(workflow,claim.claim_id)*10).toFixed(1))
          const support = currentSupport(workflow,claim.claim_id)
          const choice = workflow.review_session?.choices[claim.claim_id]
          const supportClass = support === '材料支持' ? 'supported' : support === '材料有冲突' ? 'conflict' : 'pending'
          return <article key={claim.claim_id} data-guide={pending!==undefined?"sentence-editing":undefined} className={`review-sentence${selected?.claim_id === claim.claim_id ? ' is-selected' : ''}`} data-claim-id={claim.claim_id}>
            <div className="review-labels">{matchScore>0 && <span className={matchScore>=STRONG_MATCH_SCORE?'em-chip strong':'em-chip'}>{matchScore>=STRONG_MATCH_SCORE?'较强匹配':'岗位相关度'} · {matchScore}/10</span>}<span className={`support-state ${pending !== undefined ? 'pending' : supportClass}`}>材料检查：{pending !== undefined ? '修改后需重新检查' : support}</span>
              <span className="user-choice">我的选择：{choice?.text === claim.text ? ({original:'保留原句',edit:'自己修改',accept:'已确认采用'} as const)[choice.action] : '未处理'}</span></div>
            <label className="field-label" htmlFor={`edit-${claim.claim_id}`}>第 {index+1} 条草稿</label>
            <textarea id={`edit-${claim.claim_id}`} name={`claim-${claim.claim_id}`} className="jd-input" rows={Math.max(3,(pending ?? claim.text).split(/\r?\n/).reduce((total,line)=>total+Math.max(1,Math.ceil(line.length/55)),0))} maxLength={420}
              value={pending ?? claim.text} onFocus={() => setSelectedId(claim.claim_id)} onChange={e => onEdit(claim.claim_id,e.target.value)} />
            {workflow.grounding?.polish_source && !workflow.grounding?.results[claim.claim_id]?.proposed_text && !isEducationProfile(claim,resumeForm) && <p className="warn-text" role="status">此条暂未生成润色建议，请检查服务状态后重试；原文保留。</p>}
            {workflow.grounding?.results[claim.claim_id]?.proposed_text && (()=>{
              const comparison=workflow.grounding!.results[claim.claim_id]
              const suggestion=comparison.proposed_text!
              const adopted=suggestion===claim.text&&suggestion!==comparison.original_text
              const stale=claim.text!==comparison.original_text && claim.text!==suggestion
              if (!stale && suggestion===comparison.original_text && comparison.original_check?.relation==='CONTRADICTED') {
                return <section className="polish-check needs-review" aria-label={`第 ${index+1} 条材料冲突`}>
                  <strong>材料冲突，请先核查</strong>
                  <p>已保留本条原文。请对照引用修改正文，或补充能解释差异的材料后重新核验。</p>
                  <details><summary>查看冲突事实和材料原文</summary><AtomicEvidence result={comparison} /></details>
                </section>
              }
              const edits=(comparison.change_audit?.changes??[]).filter(change=>change.before!==change.after)
              const spans=diffSpans(comparison.original_text,suggestion)
              const reviewRequired=stale||proposalNeedsReview(comparison,workflow.grounding?.error)
              return <section className="inline-polish" aria-label={`第 ${index+1} 条润色对照`}>
                <div className="inline-polish-heading"><h4>润色与核查</h4><span>{adopted?'已采用 · 正文已更新':stale?'历史建议 · 正文已修改':comparison.original_check?.relation==='CONTRADICTED'?'材料冲突 · 请先核查':suggestion===comparison.original_text?'暂未改写':'等待你确认'}</span></div>
                <p className="polish-legend">黄色：与原文不同的内容；蓝色提示：整条建议需要核查，颜色不定位具体风险。原文中删除的内容也会标出。</p>
                <div className="polish-comparison"><div><strong>润色前</strong><p>{spans.original.map((part,i)=>part.changed?<mark className="polish-diff removed change" key={i}>{part.text}</mark>:<span key={i}>{part.text}</span>)}</p></div>
                  <div><strong>润色建议</strong><p>{spans.proposal.map((part,i)=>part.changed?<mark className="polish-diff change" key={i}>{part.text}</mark>:<span key={i}>{part.text}</span>)}</p></div></div>
                <div className={`polish-check ${reviewRequired?'needs-review':''}`}><strong>建议核查：</strong>{workflow._historyReplay ? '这是当时的核查记录，采用或编辑后需按当前材料重新核验。' : stale?'正文已变化，以下是历史结果，请重新润色或核验。':proposalStatus(comparison,workflow.grounding?.error)}</div>
                {comparison.proposal_notice&&<p className="warn-text">{comparison.proposal_notice}</p>}
                {comparison.preservation?.lost_supported_details?.map((detail,i)=><p className="warn-text" key={i}>可能遗漏：{detail}</p>)}
                <details><summary>具体改了什么{edits.length?`（${edits.length} 处）`:''}</summary>
                  {edits.length>5?<p>这是一处较大幅度的重写，请直接对照上方两段完整文字，重点检查职责、数字和限定条件。</p>:edits.length?<ol>{edits.map((change,i)=><li key={i}><span>原文：{change.before||'（无）'}</span><span>建议：{change.after||'（删除）'}</span></li>)}</ol>:<p>两版文字一致，或没有可用的逐项改动记录。</p>}
                </details>
                {comparison.proposal_check&&<details><summary>查看建议的逐项核查</summary><AtomicEvidence result={{...comparison,...comparison.proposal_check,verification_scope:'experience'}} /></details>}
                <div className="btn-row"><ActionButton type="button" className="btn primary" disabledReason={adopted?'已采用这条建议，正文已更新。':stale?'正文已变化，请重新生成建议。':suggestion===claim.text?'本次没有有效改写，请重新生成。':'请先保存或取消正在编辑的句子。'} disabled={editing||stale||suggestion===claim.text} onClick={()=>commit(claim.claim_id,suggestion,'accept')}>{adopted?'已采用':'采用建议'}</ActionButton>
                  <ActionButton type="button" className="btn secondary" disabledReason={'请先保存或取消正在编辑的句子。'} disabled={editing} onClick={()=>commit(claim.claim_id,claim.text,'original')}>保留原文</ActionButton></div>
              </section>
            })()}
            <div className="btn-row">
              {pending !== undefined ? <><ActionButton type="button" className="btn primary" disabledReason={'请先填写要保存的句子。'} disabled={!pending.trim()} onClick={() => commit(claim.claim_id,pending,'edit')}>保存修改</ActionButton>
                <button type="button" className="btn secondary" onClick={() => onEdit(claim.claim_id,null)}>取消编辑</button></> :
                <button type="button" className="btn secondary" onClick={() => commit(claim.claim_id,claim.text,'original')}>保留当前句</button>}
              <button type="button" className="text-action" onClick={() => {setSelectedId(claim.claim_id);setToolsOpen(true)}}>查看建议与依据</button>
              <button type="button" className="text-action remove-draft-claim" onClick={()=>{
                try {
                  const before=pending?.trim()?changeClaim(workflow,claim.claim_id,pending,'edit'):workflow
                  const next=removeDraftClaim(before,claim.claim_id)
                  saveTextVersion(before,'移除经历前');setUndo(values=>[...values,before].slice(-20));setWorkflow(next)
                  onEdit(claim.claim_id,null);setNotice('已从正文移除，可在下方经历库候选中重新加入，也可撤销。')
                } catch {setNotice('保存移除记录失败，正文未改变。')}
              }}>从正文移除</button>
            </div>
          </article>
        })}
        <div className="btn-row"><ActionButton type="button" className="btn secondary" disabledReason={editing?'请先保存或取消正在编辑的句子。':'还没有可以撤销的修改。'} disabled={!undo.length || editing} onClick={() => {
          const previous = undo.at(-1)
          if (!previous || previous.application_id !== workflow.application_id || previous.candidate_id !== workflow.candidate_id) {setUndo([]);return}
          try {
            const next = {...previous,requires_reverification:true,
              grounding:previous.grounding ? {...previous.grounding,error:'恢复后的正文需重新核验；以下为历史记录。'} : undefined,
              review_session:{...session(previous),actions:metrics.actions+1,interruptions:metrics.interruptions},
              claim_verification:previous.claim_verification.map(v => ({...v,state:'NEEDS_REVIEW' as const,grounded:false,support_score:0})),
              field_controls:previous.field_controls.map(c => ({...c,action:'BLOCKED' as const})),
              human_confirmation:{...previous.human_confirmation,allowed_actions:['EDIT','CANCEL']}}
            saveTextVersion(workflow,'撤销前');saveTextVersion(next,'撤销上一操作');setWorkflow(next);setUndo(values => values.slice(0,-1));setNotice('已撤销，当前材料需重新检查。')
          } catch {setNotice('历史保存失败，尚未撤销。')}
        }}>撤销上一操作</ActionButton></div>
        {notice && <p role="status">{notice}</p>}
      </div>
      <aside className="review-rail">
        <details className="review-tools" open={toolsOpen} onToggle={e => setToolsOpen(e.currentTarget.open)}>
          <summary>当前句子的建议与依据</summary>
          <div className="selected-review" aria-live="polite">
            <h3>{selected ? `第 ${workflow.resume_claims.indexOf(selected)+1} 条` : '选择一句草稿'}</h3>
            {selected && <p className="selected-original">{drafts[selected.claim_id] ?? selected.text}</p>}
            {proposedChange && proposal && parts && selected ? <div className="review-proposal">
              <h4>建议预览</h4><p>{parts.proposal.map((part,i)=>part.changed?<mark key={i} className="polish-diff change">{part.text}</mark>:<span key={i}>{part.text}</span>)}</p>
              <p className="polish-legend">黄色标出改写部分；蓝色提示表示整条建议需要核查。仅删除的内容请看正文中的“润色前”。</p>
              {row && (needsAttention(row)||proposalNeedsReview(row,workflow.grounding?.error)) && <p className="polish-check needs-review">需要核查整条建议。请对照原件；采用后也不会自动获得材料支持。</p>}
              {row?.proposal_notice && <p className="warn-text">{row.proposal_notice}</p>}
              {row?.preservation?.lost_supported_details.map((detail,i) => <p key={i} className="warn-text">请核对：{detail}</p>)}
              <div className="btn-row"><ActionButton type="button" className="btn primary" disabledReason={'请先保存或取消正在编辑的句子。'} disabled={editing} onClick={() => commit(selected.claim_id,proposal,'accept')}>采用此建议</ActionButton>
                <ActionButton type="button" className="btn secondary" disabledReason={'请先保存或取消正在编辑的句子。'} disabled={editing} onClick={() => commit(selected.claim_id,selected.text,'original')}>保留当前句</ActionButton></div>
            </div> : selected && isEducationProfile(selected,resumeForm) ? <p className="muted">这条是教育资料，按表单填写；润色重点是正文中的项目、实习和获奖经历。</p> : selected && row?.proposed_text ? <p className="muted">{workflow.review_session?.choices[selected.claim_id]?.action === 'accept' ? '你已采用这条润色建议。' : row.proposed_text === row.original_text ? (row.original_check?.relation==='CONTRADICTED'?'材料与原文有冲突。请展开材料检查记录，核对引用后修改或补充材料。':'本次未生成有效改写，可重新生成。') : '当前正文已是这条建议，或建议已过期；请检查正文。'}</p> : selected ? <div className="review-empty-proposal"><p>这条经历还没有润色结果。下方是上方“按目标岗位润色简历”的快捷入口，都会处理当前正文中的所有经历。</p><ActionButton type="button" className="btn primary" title="与上方的按目标岗位润色简历相同，都会处理当前正文。" disabled={editing||polishBusy||Boolean(cloudIssue)} disabledReason={cloudIssue|| (polishBusy?'两个润色按钮是同一功能，正在处理，请等完成后再操作。':'请先保存或取消正在编辑的句子。')} onClick={()=>polishPanel.current?.startPolishing()}>生成润色建议（快捷入口）</ActionButton></div> : <p className="muted">请先选择一条经历，再生成润色建议。</p>}
            <details><summary>材料检查记录{workflow._historyReplay || row?.final_text !== selected?.text ? '（历史记录）' : ''}</summary>{workflow._historyReplay?.legacy ? <p>旧版历史未保存逐项核验引用，请按当前材料重新核验。</p> : row ? <AtomicEvidence result={row} historical={!!workflow._historyReplay} /> : <p>尚无此句的检查记录。请补充材料后核验。</p>}</details>
          </div>
        </details>
      </aside>
    </div>
    <details className="review-export-section" id="review-export" ref={exportPanel}><summary>检查并导出个人草稿</summary><GroundedExport editing={editing} /></details>
  </div>
}
