import { useLayoutEffect, useRef, useState } from 'react'
import { groundingRequest } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { session } from '../resume/review'

function download(text: string, filename: string, type: string) {
  const url=URL.createObjectURL(new Blob([text],{type}))
  const link=document.createElement('a');link.href=url;link.download=filename;link.click()
  setTimeout(() => URL.revokeObjectURL(url),1000)
}
export function GroundedExport({editing = false}: {editing?: boolean}) {
  const {workflow,resumeForm,claimDecisions,reviewDrafts} = useDemo()
  editing = editing || Object.keys(reviewDrafts).length > 0
  const [confirmed,setConfirmed] = useState('')
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
    <p>下载你确认的正文 TXT。未核验和冲突状态保留在审核记录中；此操作不代表材料已通过检查，也不进入网申填写。</p>
    <p className="muted">如需准备网申，请返回并选择“继续核验并准备网申”，通过材料检查后再模拟填写。</p>
    {editing && <p role="status">请先保存或取消正在编辑的句子，再确认导出。</p>}
    <div className="export-preview"><h4>将导出的正文（{claims.length} 条）</h4><p style={{whiteSpace:'pre-wrap'}}>{claims.map(c => c.text).join('\n')}</p></div>
    <label><input type="checkbox" checked={!editing && confirmed === signature} disabled={busy || editing || !claims.length}
      onChange={e => setConfirmed(e.target.checked ? signature : '')} />我确认最终正文，并知晓尚未获得材料支持或存在冲突的内容仍由我决定是否使用。</label>
    <button type="button" className="btn primary" disabled={busy || editing || confirmed !== signature || !claims.length}
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
          download(result.data.text,'ApplyGuard-个人草稿.txt','text/plain;charset=utf-8')
          setNotice(result.data.notice)
        } catch {setNotice('导出未完成，请检查连接后重试。草稿已保留。')}
        finally {setBusy(false)}
      }}>{busy ? '正在准备导出…' : '下载个人草稿 TXT'}</button>
    {record?.signature === signature && <button className="btn secondary" onClick={() => download(JSON.stringify(record.report,null,2),'ApplyGuard-审核记录.json','application/json')}>下载审核记录</button>}
    {!editing && notice.signature === signature && notice.text && <p role="status">{notice.text}</p>}
  </div>
}
