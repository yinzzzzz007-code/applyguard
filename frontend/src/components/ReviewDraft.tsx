import { useState } from 'react'
import type { WorkflowResponse } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { changeClaim, changedSpan, currentSupport, needsAttention, reviewPriority, session } from '../resume/review'
import { saveTextVersion } from '../resume/groundingHistory'
import { AtomicEvidence } from './AtomicEvidence'
import { GroundedExport } from './GroundedExport'
import { SAGPolishPanel } from './SAGPolishPanel'

export function ReviewDraft() {
  const {workflow,setWorkflow,reviewDrafts:drafts,setReviewDraft:onEdit,reviewStorageError} = useDemo()
  const [undo,setUndo] = useState<WorkflowResponse[]>([])
  const [notice,setNotice] = useState('')
  const [selectedId,setSelectedId] = useState('')
  const [toolsOpen,setToolsOpen] = useState(() => window.matchMedia('(min-width:761px)').matches)
  if (!workflow) return null
  const priority = [...workflow.resume_claims].sort((a,b) => reviewPriority(workflow,b.claim_id)-reviewPriority(workflow,a.claim_id))
    .filter(c => reviewPriority(workflow,c.claim_id)>0).slice(0,3)
  const selected = workflow.resume_claims.find(c => c.claim_id === selectedId) ?? workflow.resume_claims[0]
  const row = selected ? workflow.grounding?.results[selected.claim_id] : undefined
  const proposal = row?.proposed_text
  const proposedChange = Boolean(selected && proposal && proposal !== selected.text)
  const parts = selected && proposal ? changedSpan(selected.text,proposal) : null
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
    <div className="review-workspace">
      <div className="review-draft">
        <div className="review-document-heading"><h3>完整草稿</h3><span role="status">{editing ? `${Object.keys(drafts).length} 处输入已暂存，尚未保存到正文` : '正文已保存到本标签页'}</span></div>
        <p className="muted">直接编辑句子；选择一条后，可查看建议和材料依据。暂存输入切页后仍保留。</p>
        {reviewStorageError && <p className="danger-text" role="alert">{reviewStorageError}</p>}
        {!!priority.length && <div className="review-priority"><span>建议先看</span>{priority.map(c => <button type="button" className="text-action" key={c.claim_id} onClick={() => focusClaim(c.claim_id)}>第 {workflow.resume_claims.indexOf(c)+1} 条</button>)}</div>}
        {!workflow.resume_claims.length && <p>草稿还没有内容。请从下方“添加内容”选入一条经历。</p>}
        {workflow.resume_claims.map((claim,index) => {
          const pending = drafts[claim.claim_id]
          const support = currentSupport(workflow,claim.claim_id)
          const choice = workflow.review_session?.choices[claim.claim_id]
          const supportClass = support === '材料支持' ? 'supported' : support === '材料有冲突' ? 'conflict' : 'pending'
          return <article key={claim.claim_id} className={`review-sentence${selected?.claim_id === claim.claim_id ? ' is-selected' : ''}`} data-claim-id={claim.claim_id}>
            <div className="review-labels"><span className={`support-state ${pending !== undefined ? 'pending' : supportClass}`}>材料检查：{pending !== undefined ? '修改后需重新检查' : support}</span>
              <span className="user-choice">我的选择：{choice?.text === claim.text ? ({original:'保留原句',edit:'自己修改',accept:'已确认采用'} as const)[choice.action] : '未处理'}</span></div>
            <label className="field-label" htmlFor={`edit-${claim.claim_id}`}>第 {index+1} 条草稿</label>
            <textarea id={`edit-${claim.claim_id}`} name={`claim-${claim.claim_id}`} className="jd-input" rows={3} maxLength={420}
              value={pending ?? claim.text} onFocus={() => setSelectedId(claim.claim_id)} onChange={e => onEdit(claim.claim_id,e.target.value)} />
            <div className="btn-row">
              {pending !== undefined ? <><button type="button" className="btn primary" disabled={!pending.trim()} onClick={() => commit(claim.claim_id,pending,'edit')}>保存修改</button>
                <button type="button" className="btn secondary" onClick={() => onEdit(claim.claim_id,null)}>取消编辑</button></> :
                <button type="button" className="btn secondary" onClick={() => commit(claim.claim_id,claim.text,'original')}>保留当前句</button>}
              <button type="button" className="text-action" onClick={() => {setSelectedId(claim.claim_id);setToolsOpen(true)}}>查看建议与依据</button>
            </div>
          </article>
        })}
        <div className="btn-row"><button type="button" className="btn secondary" disabled={!undo.length || editing} onClick={() => {
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
        }}>撤销上一操作</button></div>
        {notice && <p role="status">{notice}</p>}
      </div>
      <aside className="review-rail">
        <details className="review-tools" open={toolsOpen} onToggle={e => setToolsOpen(e.currentTarget.open)}>
          <summary>当前句子的建议与依据</summary>
          <div className="selected-review" aria-live="polite">
            <h3>{selected ? `第 ${workflow.resume_claims.indexOf(selected)+1} 条` : '选择一句草稿'}</h3>
            {selected && <p className="selected-original">{drafts[selected.claim_id] ?? selected.text}</p>}
            {proposedChange && proposal && parts && selected ? <div className="review-proposal">
              <h4>建议预览</h4><p>{parts[0]}<mark>{parts[1] || '〔此处有删除〕'}</mark>{parts[2]}</p>
              {row && needsAttention(row) && <p className="warn-text">建议包含需要复核的变化。请对照原件；采用后也不会自动获得材料支持。</p>}
              {row?.proposal_notice && <p className="warn-text">{row.proposal_notice}</p>}
              {row?.preservation?.lost_supported_details.map((detail,i) => <p key={i} className="warn-text">请核对：{detail}</p>)}
              <div className="btn-row"><button type="button" className="btn primary" disabled={editing} onClick={() => commit(selected.claim_id,proposal,'accept')}>采用此建议</button>
                <button type="button" className="btn secondary" disabled={editing} onClick={() => commit(selected.claim_id,selected.text,'original')}>保留当前句</button></div>
            </div> : <p className="muted">尚无待采用的改写。可生成建议，正文会保持不变。</p>}
            <details><summary>材料检查记录{row?.final_text !== selected?.text ? '（历史记录）' : ''}</summary>{row ? <AtomicEvidence result={row} /> : <p>尚无此句的检查记录。请补充材料后核验。</p>}</details>
          </div>
          <SAGPolishPanel />
        </details>
      </aside>
    </div>
    <details className="review-export-section" id="review-export"><summary>检查并导出个人草稿</summary><GroundedExport editing={editing} /></details>
  </div>
}
