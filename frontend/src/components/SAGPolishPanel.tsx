import { useLayoutEffect, useRef, useState } from 'react'
import { groundingRequest, getApiClient } from '../api/client'
import type { WorkflowResponse } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { saveTextVersion } from '../resume/groundingHistory'
import { mergeReviewResult, session } from '../resume/review'
import { GroundingHistory } from './GroundingHistory'
import { Icon } from './Icon'

export function SAGPolishPanel() {
  const {workflow,resumeForm,setWorkflow,reviewDrafts} = useDemo()
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const editing = Object.keys(reviewDrafts).length > 0
  const signature = JSON.stringify([workflow,resumeForm,reviewDrafts])
  const current = useRef(signature)
  useLayoutEffect(() => {current.current = signature;return () => {current.current = ''}},[signature])
  if (!workflow) return null
  async function run(polish: boolean) {
    if (!workflow || editing) return
    if ((polish || !workflow.local_only) && !window.confirm(
      '本操作可能把岗位说明、草稿陈述及相关材料发送给后端配置的模型服务。继续？')) return
    const started = current.current
    setBusy(true);setError('')
    try {
      const result = polish
        ? await groundingRequest<Partial<WorkflowResponse>>('polish',workflow,resumeForm,{grounding_mode:'sag_atomic'})
        : await getApiClient().reverifyWorkflow(workflow,workflow.resume_claims.map(({claim_id,text}) => ({claim_id,text})),resumeForm, workflow.local_only ? undefined : 'sag_atomic')
      if (current.current !== started) {setError('草稿已变化，本次结果未覆盖你的编辑。请重新运行。');return}
      if (result.error || !result.data) {
        const review=session(workflow)
        setWorkflow({...workflow,review_session:{...review,interruptions:review.interruptions+1}})
        setError(result.error?.message ?? '处理未完成，原稿保留。');return
      }
      const next = mergeReviewResult(workflow,result.data)
      saveTextVersion(workflow,polish ? '润色前' : '核验前')
      saveTextVersion(next,polish ? '建议已生成：等待预览与采用' : '刷新材料支持情况')
      setWorkflow(next)
      setError(result.data.grounding?.error ?? '')
    } catch {setError('处理或保存未完成，原稿已保留。请检查连接及本机存储。')}
    finally {setBusy(false)}
  }
  return <div className="sag-panel" aria-label="SAG润色与事实核验">
    <div className="sag-panel-heading"><Icon name="spark" /><h3>表达建议与材料核验</h3></div>
    <p>先预览改写，再逐句采用。生成建议不会替换你的正文。</p>
    <p className="muted">个人资料和教育信息按表单使用；项目、竞赛与实习核对原件。</p>
    <div className="sag-provider-note"><Icon name="lock" /><span>{workflow.local_only ? "本地核验在本机运行。只有确认生成 AI 建议时才发送相关内容。" : "生成 AI 建议或模型核验前会询问是否发送相关内容。"}</span></div>
    {editing && <p role="status">请先保存或取消正在编辑的句子，再生成建议或核验。</p>}
    <div className="btn-row"><button className="btn primary" disabled={busy || editing || !workflow.resume_claims.length} onClick={() => void run(true)}>{busy ? '正在处理…' : '生成建议（不改正文）'}</button>
      <button className="btn secondary" disabled={busy || editing || !workflow.resume_claims.length} onClick={() => void run(false)}>检查草稿的材料支持</button></div>
    <details><summary>确认与材料支持有什么区别？</summary><p>你可以编辑、确认并导出自己的最终稿。材料不足或冲突会保留记录，用户确认不会把它变成“材料支持”。本地导出不等于提交招聘网站。</p></details>
    {error && <p className="danger-text" role="alert">{error}</p>}
    <GroundingHistory />
  </div>
}
