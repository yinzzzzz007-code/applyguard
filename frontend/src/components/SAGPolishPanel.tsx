import { useLayoutEffect, useRef, useState } from 'react'
import { groundingRequest, getApiClient } from '../api/client'
import type { GroundingMode, WorkflowResponse } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { AtomicEvidence } from './AtomicEvidence'
import { ClaimBadge } from './States'
import { saveTextVersion } from '../resume/groundingHistory'
import { GroundingHistory } from './GroundingHistory'
import { Icon } from './Icon'

export function SAGPolishPanel() {
  const {workflow,resumeForm,setWorkflow} = useDemo()
  const [mode,setMode] = useState<GroundingMode>('sag_atomic')
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const [pending,setPending] = useState<Partial<WorkflowResponse> | null>(null)
  const signature = JSON.stringify([workflow,resumeForm])
  const current = useRef(signature)
  useLayoutEffect(() => {current.current = signature},[signature])
  const proposalSignature = useRef('')
  if (!workflow) return null

  async function run(polish: boolean) {
    if (!workflow) return
    const started = current.current
    setBusy(true); setError(''); setPending(null)
    try {
      const result = polish
        ? await groundingRequest<Partial<WorkflowResponse>>('polish',workflow,resumeForm,{grounding_mode:mode})
        : await getApiClient().reverifyWorkflow(workflow,
            workflow.resume_claims.map(({claim_id,text}) => ({claim_id,text})),resumeForm,mode)
      if (current.current !== started) { setError('输入已改变，请针对最新内容重新运行。'); return }
      if (result.error || !result.data) {setError(result.error?.message ?? '未完成');return}
      proposalSignature.current = started
      setPending(result.data)
    } catch {setError('处理未完成，原稿已保留。请检查服务连接后重试。')}
    finally {setBusy(false)}
  }

  return <div className="sag-panel" aria-label="SAG润色与事实核验">
    <div className="sag-panel-heading"><Icon name="spark" /><h3>有依据的润色</h3></div>
    <p>检索相关原件，优化表达；逐项检查新增、夸大或错配的事实。</p>
    <label className="field-label" htmlFor="sag-mode">处理方式</label>
    <select id="sag-mode" value={mode} disabled={busy} onChange={event => {setMode(event.target.value as GroundingMode);setPending(null)}}>
      <option value="sag_atomic">SAG＋原子事实核验</option>
      <option value="sag">SAG检索与润色预览</option>
    </select>
    <div className="sag-provider-note"><Icon name="lock" /><span>材料将发送给本机配置的模型服务。</span></div>
    <div className="btn-row">
      <button className="btn primary" type="button" disabled={busy || !workflow.resume_claims.length} onClick={() => void run(true)}>
        {busy ? '正在检索与处理…' : '生成润色建议'}
      </button>
      <button className="btn secondary" type="button" disabled={busy || !workflow.resume_claims.length} onClick={() => void run(false)}>
        核验当前原稿
      </button>
    </div>
    <details className="sag-policy"><summary>核验与导出规则</summary><p>仅检索不能标为事实已通过。待复核、引用无效或失败的内容，需要补充材料或编辑后重核验，不能靠人工确认绕过。</p></details>
    {error && <p className="danger-text" role="alert">{error}</p>}
    {pending?.grounding && <div>
      {pending.grounding.error && <p className="danger-text">{pending.grounding.error}</p>}
      {Object.entries(pending.grounding.results).map(([id,result]) => <article className="item-block" key={id}>
        <ClaimBadge status={result.state} />
        <div className="proposal-comparison"><div><span>原稿</span><p>{result.original_text}</p></div><div><span>AI 建议</span><p>{result.proposed_text ?? result.final_text}</p></div></div>
        {result.proposal_rejected && <p className="warn-text" role="status">{result.proposal_notice}</p>}
        {result.preservation?.lost_supported_details.map((text,index) => <p className="warn-text" key={index}>可能丢失有效信息：{text}</p>)}
        {result.change_audit?.sensitive_change && <p className="warn-text">涉及数字、职责、时间或限定词变化，请重点核对。</p>}
        <p><strong>待采用正文：</strong>{result.final_text}</p>
        <AtomicEvidence result={result} />
      </article>)}
      <div className="btn-row">
        <button className="btn primary" type="button" disabled={busy} onClick={() => {
          if (proposalSignature.current !== current.current) {setPending(null);setError('原稿已变化，请重新运行。');return}
          try {
            saveTextVersion(workflow,'采用建议前')
            saveTextVersion({...workflow,...pending},'采用建议后')
          } catch {setError('无法保存本机历史，请检查浏览器存储权限后重试。');return}
          setWorkflow({...workflow,...pending})
          setPending(null)
        }}>采用本次结果，进入人工核对</button>
        <button className="btn secondary" type="button" onClick={() => {
          try {
            const report = pending.grounding
            saveTextVersion({...workflow,grounding:report ? {...report,results:Object.fromEntries(
              Object.entries(report.results).map(([id,row]) => [id,{...row,proposal_rejected:true}]))} : workflow.grounding},
              '保留原稿，未采用建议留档')
            setPending(null)
          } catch {setError('建议留档失败，尚未关闭本次结果。')}
        }}>保留原稿并留档建议</button>
      </div>
    </div>}
    <GroundingHistory />
  </div>
}
