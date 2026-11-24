import {completeGuideStep,editingRequirements} from '../guide'
import {ActionButton} from './ui/action-button'
import { useLayoutEffect, useRef, useState } from 'react'
import { groundingRequest } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { session } from '../resume/review'
import {buildLatex,downloadFile} from '../resume/latex'

export function GroundedExport({editing = false}: {editing?: boolean}) {
  const {workflow,resumeForm,claimDecisions,reviewDrafts} = useDemo()
  editing = editing || Object.keys(reviewDrafts).length > 0
  const [confirmed,setConfirmed] = useState('')
  const [format,setFormat] = useState<'txt'|'tex'>('txt')
  const [busy,setBusy] = useState(false)
  const [notice,setNoticeState] = useState({signature:'',text:''})
  const [record,setRecord] = useState<{signature:string; report:unknown} | null>(null)
  const signature = JSON.stringify([workflow,resumeForm,claimDecisions,reviewDrafts])
  const current = useRef(signature)
  useLayoutEffect(() => {current.current = signature;return () => {current.current = ''}},[signature])
  const setNotice = (text: string) => setNoticeState({signature:current.current,text})
  if (!workflow) return null
  const claims=workflow.resume_claims.filter(c => claimDecisions[c.claim_id]?.decision !== 'reject')
    .map(c => ({claim_id:c.claim_id,text:(claimDecisions[c.claim_id]?.editedText ?? c.text).trim()}))
  return <div className="review-export">
    <h3>导出个人草稿</h3>
    <p>可下载纯文本或 LaTeX 源文件。待核验和冲突仍记入审核记录。</p>
    {editing && <p role="status">请先保存或取消正在编辑的句子，再确认导出。</p>}
    <div className="export-preview"><h4>将导出的正文（{claims.length} 条）</h4><p style={{whiteSpace:'pre-wrap'}}>{claims.map(c => c.text).join('\n')}</p></div>
    {!claims.length&&<p role="status">请先加入至少一条草稿。</p>}
    {!editing&&claims.length>0&&confirmed!==signature&&<p className="muted">请勾选下方最终正文确认，才可下载。</p>}
    <label data-guide="export-confirm"><input type="checkbox" checked={!editing && confirmed === signature} disabled={busy || editing || !claims.length}
      onChange={e => setConfirmed(e.target.checked ? signature : '')} />我确认最终正文，并知晓尚未获得材料支持或存在冲突的内容仍由我决定是否使用。</label>
    <label>文件格式 <select value={format} disabled={busy} onChange={e=>setFormat(e.target.value === 'tex' ? 'tex' : 'txt')}>
      <option value="txt">纯文本（.txt）</option><option value="tex">LaTeX 源文件（.tex，XeLaTeX 编译）</option>
    </select></label>
    <ActionButton type="button" className="btn primary" disabledReason={busy?'正在准备导出，请稍候。':editing?'请先保存或取消正在编辑的句子。':!claims.length?'请先加入至少一条草稿。':'请先勾选最终正文确认。'} guideRequirements={[
      ...editingRequirements(reviewDrafts),
      ...(!claims.length?[{id:'claims',label:'先从经历库加入至少一条草稿。',href:'/vault'}]:[]),
      ...(!editing&&claims.length>0&&confirmed!==signature?[{id:'confirm',label:'先阅读最终正文，再勾选此处确认；这不等于材料核验通过。',selector:'[data-guide="export-confirm"]'}]:[])
    ]} disabled={busy || editing || confirmed !== signature || !claims.length}
      onClick={async () => {
        setBusy(true);setNotice('');const started=current.current
        try {
          const text=claims.map(c => c.text).join('\n')
          const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))
          const sha=Array.from(new Uint8Array(bytes),x => x.toString(16).padStart(2,'0')).join('')
          const result=await groundingRequest<{text:string;sha256:string;notice:string;review_record:unknown}>('export',workflow,resumeForm,{
            export_policy:'user_confirmed', human_confirmed:true, acknowledge_unverified:true, confirmed_text_sha256:sha, claims,
          })
          if (started !== current.current) {setNotice('草稿已变化，本次导出已取消，请确认最新正文。');return}
          if (!result.data || result.error) {setNotice(result.error?.message ?? '导出失败');return}
          if (result.data.sha256 !== sha || result.data.text !== text) {setNotice('导出正文与确认稿不一致，已停止下载。');return}
          const metrics=session(workflow)
          setRecord({signature:started,report:{...result.data, review_session:{...metrics,
            elapsed_seconds:Math.round((Date.now()-metrics.startedAt)/1000),
            metric_notice:'从本次导入开始（未导入时从工作流载入）到导出，包括等待与离开时间；不是人工可用性测评。'},
            prior_model_checks:workflow.grounding ? {snapshot:workflow.grounding.snapshot,
              results:workflow.grounding.results,notice:'历史模型记录；不代表导出时再次核验，须逐句比对 final_text。'} : null}})
          if (format === 'tex') downloadFile(buildLatex(claims.map(c=>({kind:'text',text:c.text}))),'ApplyGuard-个人草稿.tex','application/x-tex;charset=utf-8')
          else downloadFile(result.data.text,'ApplyGuard-个人草稿.txt','text/plain;charset=utf-8')
          setNotice(result.data.notice)
          completeGuideStep('confirm')
        } catch {setNotice('导出未完成，请检查连接后重试。草稿已保留。')}
        finally {setBusy(false)}
      }}>{busy ? '正在准备导出…' : format === 'tex' ? '下载个人草稿 LaTeX' : '下载个人草稿 TXT'}</ActionButton>
    {record?.signature === signature && <button className="btn secondary" onClick={() => downloadFile(JSON.stringify(record.report,null,2),'ApplyGuard-审核记录.json','application/json')}>下载审核记录</button>}
    {!editing && notice.signature === signature && notice.text && <p role="status">{notice.text}</p>}
  </div>
}
