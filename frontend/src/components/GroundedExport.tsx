import { useLayoutEffect, useRef, useState } from 'react'
import { groundingRequest } from '../api/client'
import { useDemo } from '../context/DemoContext'

export function GroundedExport() {
  const {workflow,resumeForm,claimDecisions,canSubmitAts} = useDemo()
  const [confirmed,setConfirmed] = useState('')
  const [busy,setBusy] = useState(false)
  const [notice,setNotice] = useState('')
  const signature = JSON.stringify([workflow,resumeForm,claimDecisions])
  const current = useRef(signature)
  useLayoutEffect(() => {current.current = signature},[signature])
  if (!workflow?.grounding) return null
  return <div className="item-block">
    <h3>导出核验后的陈述</h3>
    <label><input type="checkbox" checked={confirmed === signature} disabled={busy || !canSubmitAts()}
      onChange={e => setConfirmed(e.target.checked ? signature : '')} />我已核对最终正文、个人贡献及引用原件</label>
    <button type="button" className="btn primary" disabled={busy || confirmed !== signature || !canSubmitAts()}
      onClick={async () => {
        setBusy(true);setNotice('');const started = current.current
        try {
          const result = await groundingRequest<{text:string}>('export',workflow,resumeForm,{
            human_confirmed:true,claims:workflow.resume_claims.filter(c => claimDecisions[c.claim_id]?.decision !== 'reject')
              .map(({claim_id,text}) => ({claim_id,text})),
          })
          if (started !== current.current) {setNotice('内容已变化，本次导出已取消。');return}
          if (!result.data || result.error) {setNotice(result.error?.message ?? '导出失败');return}
          const url=URL.createObjectURL(new Blob([result.data.text],{type:'text/plain;charset=utf-8'}))
          const link=document.createElement('a');link.href=url;link.download='ApplyGuard-核验陈述.txt';link.click()
          setTimeout(() => URL.revokeObjectURL(url),1000)
          setNotice('已重新核验并导出文本，没有向招聘平台投递。')
        } finally {setBusy(false)}
      }}>{busy ? '正在复查当前原件…' : '重新核验并导出 TXT'}</button>
    {notice && <p role="status">{notice}</p>}
  </div>
}
