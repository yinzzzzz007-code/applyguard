import { useState } from 'react'
import type { ResumeClaim, WorkflowResponse } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { changeClaim, changedSpan, currentSupport, needsAttention, reviewPriority, session } from '../resume/review'
import { saveTextVersion } from '../resume/groundingHistory'
import { AtomicEvidence } from './AtomicEvidence'
import { GroundedExport } from './GroundedExport'

function EditableClaim({claim, workflow, onCommit, draft, onEdit}: {claim: ResumeClaim; workflow: WorkflowResponse;
  draft?: string; onEdit: (id: string, text: string | null) => void;
  onCommit: (id: string, text: string, action: 'original'|'edit'|'accept') => boolean}) {
  const editing = draft !== undefined
  const text = draft ?? claim.text
  const row = workflow.grounding?.results[claim.claim_id]
  const choice = workflow.review_session?.choices[claim.claim_id]
  const proposal = row?.proposed_text
  const parts = row && proposal ? changedSpan(row.original_text, proposal) : null
  return <article className="review-sentence" data-claim-id={claim.claim_id}>
    <div className="review-labels"><span>{editing ? '正在编辑，尚未保存' : currentSupport(workflow,claim.claim_id)}</span>
      <span>{choice?.text === claim.text ? '用户已确认' : '用户未确认'}</span></div>
    <label className="field-label" htmlFor={`edit-${claim.claim_id}`}>第 {workflow.resume_claims.findIndex(c => c.claim_id === claim.claim_id) + 1} 条草稿</label>
    <textarea id={`edit-${claim.claim_id}`} className="jd-input" rows={3} maxLength={420} value={editing ? text : claim.text}
      onChange={e => onEdit(claim.claim_id,e.target.value)} />
    {editing && <div className="btn-row"><button className="btn primary" disabled={!text.trim()} onClick={() => {if (onCommit(claim.claim_id,text,'edit')) onEdit(claim.claim_id,null)}}>保存修改</button>
      <button className="btn secondary" onClick={() => onEdit(claim.claim_id,null)}>取消编辑</button></div>}
    {row && proposal && proposal !== row.original_text && <div className="review-proposal">
      <p className="muted">原句：{row.original_text}</p>
      <p>AI 建议：{needsAttention(row) && parts ? <>{parts[0]}<mark>{parts[1] || '〔此处有删除〕'}</mark>{parts[2]}</> : proposal}</p>
      {row.proposal_notice && <p className="warn-text">{row.proposal_notice}</p>}
      {row.preservation?.lost_supported_details.map((detail,i) => <p className="warn-text" key={i}>请核对：{detail}</p>)}
      <div className="btn-row"><button className="btn secondary" disabled={editing} onClick={() => onCommit(claim.claim_id,row.original_text,'original')}>用原句</button>
        <button className="btn secondary" onClick={() => {onEdit(claim.claim_id,claim.text);document.getElementById(`edit-${claim.claim_id}`)?.focus()}}>自己改</button>
        <button className="btn primary" disabled={editing} onClick={() => onCommit(claim.claim_id,proposal,'accept')}>确认采用</button></div>
    </div>}
    {(!proposal || proposal === row?.original_text) && <button className="btn secondary" disabled={editing} onClick={() => onCommit(claim.claim_id,claim.text,'accept')}>确认当前句</button>}
    <details><summary>查看核验依据{row?.final_text !== claim.text ? '（修改前的记录）' : ''}</summary>{row ? <AtomicEvidence result={row} /> : <p className="muted">尚无此句的模型核验记录，可在右侧核验当前草稿。</p>}</details>
  </article>
}

export function ReviewDraft() {
  const {workflow,setWorkflow} = useDemo()
  const [undo,setUndo] = useState<WorkflowResponse[]>([])
  const [notice,setNotice] = useState('')
  const [drafts,setDrafts] = useState<Record<string,string>>({})
  const onEdit = (id: string, text: string | null) => setDrafts(values => {const next={...values};if (text === null) delete next[id];else next[id]=text;return next})
  if (!workflow) return null
  const ranked = [...workflow.resume_claims].sort((a,b) => reviewPriority(workflow,b.claim_id)-reviewPriority(workflow,a.claim_id))
  const priority = ranked.filter(c => reviewPriority(workflow,c.claim_id)>0).slice(0,3)
  const rest = workflow.resume_claims.filter(c => !priority.includes(c))
  function commit(id: string, text: string, action: 'original'|'edit'|'accept') {
    if (!workflow) return false
    try {
      const next = changeClaim(workflow,id,text,action)
      saveTextVersion(workflow,'逐句编辑前')
      saveTextVersion(next,action === 'original' ? '使用原句' : action === 'edit' ? '自己修改' : '用户确认采用')
      setUndo(values => [...values,workflow].slice(-20)); setWorkflow(next);setNotice('已保存。用户确认不会改写材料支持情况。');return true
    } catch (error) {setNotice(error instanceof Error ? error.message : '保存失败，草稿未变。');return false}
  }
  const metrics = session(workflow)
  return <div className="review-editor">
    <h3>优先看这 {priority.length} 处</h3><p className="muted">先看有事实变化或缺少材料的句子。直接编辑最终草稿；黄色只标记需要核对的建议改动。</p>
    {priority.map(claim => <EditableClaim key={claim.claim_id} claim={claim} workflow={workflow} onCommit={commit} draft={drafts[claim.claim_id]} onEdit={onEdit} />)}
    {!priority.length && <p>没有待优先处理的句子，仍可展开全部草稿修改。</p>}
    {!!rest.length && <details className="review-rest"><summary>其余 {rest.length} 条草稿（展开编辑）</summary>
      {rest.map(claim => <EditableClaim key={claim.claim_id} claim={claim} workflow={workflow} onCommit={commit} draft={drafts[claim.claim_id]} onEdit={onEdit} />)}</details>}
    <div className="btn-row"><button className="btn secondary" disabled={!undo.length || Object.keys(drafts).length > 0} onClick={() => {
      const previous = undo.at(-1)
      if (!previous || previous.application_id !== workflow.application_id || previous.candidate_id !== workflow.candidate_id) {setUndo([]);return}
      try {
        // Restore text and decisions, but never reinstate a historical evidence pass.
        const next = {...previous, requires_reverification:true, grounding:previous.grounding ? {...previous.grounding,error:'恢复后的正文需重新核验；以下为历史记录。'} : undefined,
          review_session:{...session(previous), actions:metrics.actions+1, interruptions:metrics.interruptions},
          claim_verification:previous.claim_verification.map(v => ({...v,state:'NEEDS_REVIEW' as const,grounded:false,support_score:0})),
          human_confirmation:{...previous.human_confirmation,allowed_actions:['EDIT','CANCEL']}}
        saveTextVersion(workflow,'撤销前');saveTextVersion(next,'撤销上一操作');setWorkflow(next);setUndo(values => values.slice(0,-1));setNotice('已撤销；材料核验需按当前原件刷新。')
      } catch {setNotice('历史保存失败，尚未撤销。')}
    }}>撤销上一操作</button></div>
    {notice && <p role="status">{notice}</p>}
    <GroundedExport editing={Object.keys(drafts).length > 0} />
  </div>
}
