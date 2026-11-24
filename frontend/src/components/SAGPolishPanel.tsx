import type {usePolishJob} from '../resume/usePolishJob'
import {RadarDialog} from './RadarDialog'
import {Button} from './ui/button'
import {reviewTransport} from '../resume/modelReview'
import {resumePolishOperationLock} from '../resume/operationLock'
import {editingRequirements} from '../guide'
import {ActionButton} from './ui/action-button'
import { forwardRef, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import { getApiClient } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { saveTextVersion } from '../resume/groundingHistory'
import { mergeReviewResult, polishResultSummary, session } from '../resume/review'
import { GroundingHistory } from './GroundingHistory'
import { Icon } from './Icon'

export type SAGPolishHandle = { startPolishing: () => void }

export const SAGPolishPanel = forwardRef<SAGPolishHandle,{cloudIssue:string;job:ReturnType<typeof usePolishJob>}>(function SAGPolishPanel({cloudIssue,job}, ref) {
  const {workflow,resumeForm,setWorkflow,reviewDrafts} = useDemo()
  const busy=useSyncExternalStore(resumePolishOperationLock.subscribe,resumePolishOperationLock.isLocked)||job.running
  const awaitingConsent=useRef(false)
  useEffect(()=>()=>{if(awaitingConsent.current)resumePolishOperationLock.release()},[])
  const [error,setError] = useState('')
  const [pendingOperation,setPendingOperation]=useState<{polish:boolean;forceModel:boolean}|null>(null)
  const editing = Object.keys(reviewDrafts).length > 0
  const signature = JSON.stringify([workflow,resumeForm,reviewDrafts])
  const current = useRef(signature)
  useLayoutEffect(() => {current.current = signature;return () => {current.current = ''}},[signature])
  useImperativeHandle(ref, () => ({startPolishing: () => start(true)}))
  if (!workflow) return null
  function start(polish:boolean,forceModel=false) {
    if(!workflow||editing||job.running)return
    const needsCloud = reviewTransport(polish,forceModel,workflow.local_only).usesModel
    if((needsCloud && cloudIssue)||!resumePolishOperationLock.acquire())return
    if(needsCloud){awaitingConsent.current=true;setPendingOperation({polish,forceModel})}
    else void run(polish,forceModel)
  }
  function releaseOperation() {awaitingConsent.current=false;resumePolishOperationLock.release()}
  function cancelOperation() {setPendingOperation(null);releaseOperation()}
  async function run(polish: boolean, forceModel=false) {
    awaitingConsent.current=false
    if (!workflow || editing) {releaseOperation();return}
    const transport=reviewTransport(polish,forceModel,workflow.local_only)
    const started = current.current
    setError('')
    try {
      if(polish){await job.start();return}
      const result = await getApiClient().reverifyWorkflow({...workflow,local_only:transport.local_only},workflow.resume_claims.map(({claim_id,text}) => ({claim_id,text})),resumeForm, transport.usesModel ? 'sag_atomic' : undefined)
      if (current.current !== started) {setError('草稿已变化，本次结果未覆盖你的编辑。请重新运行。');return}
      if (result.error || !result.data) {
        const review=session(workflow)
        setWorkflow({...workflow,review_session:{...review,interruptions:review.interruptions+1}})
        setError(result.error?.message ?? '处理未完成，原稿保留。');return
      }
      const next = mergeReviewResult({...workflow,local_only:transport.local_only},result.data)
      saveTextVersion(workflow,'核验前')
      saveTextVersion(next,'刷新材料支持情况')
      setWorkflow(next)
      setError(result.data.grounding?.error ?? '')
    } catch (cause) {setError(cause instanceof Error?cause.message:'处理未完成，请检查连接。')}
    finally {releaseOperation()}
  }
  const suggestions=polishResultSummary(workflow).count
  return <div className="sag-panel" aria-label="SAG润色与事实核验">
    <div className="sag-panel-heading"><Icon name="spark" /><h3>AI 简历润色</h3></div>
    <p>逐条润色当前正文中的项目、实习和获奖，结合目标岗位突出真实贡献。每条展示原文、建议和材料核查结果，由你决定是否采用。</p><p className="muted">按 ASu great-resume 的证据写作规范生成，不补写数字、头衔或未完成成果。</p>
    <p className="muted">原文与材料冲突时，保留该条原文并展示依据。其他经历继续润色，材料不足的标为待核查。教育等个人资料按表单使用。</p>
    <div className="sag-provider-note"><Icon name="lock" /><span>{workflow.local_only ? "本地核验在本机运行。只有确认生成 AI 建议时才发送相关内容。" : "生成 AI 建议或模型核验前会询问是否发送相关内容。"}</span></div>
    {!workflow.resume_claims.length&&<p role="status">请先在下方搜索或选择一条经历。</p>}
    {editing && <p role="status">请先保存或取消正在编辑的句子，再生成建议或核验。</p>}
    <div className="btn-row"><ActionButton data-guide="polish" guideRequirements={editing?editingRequirements(reviewDrafts):!workflow.resume_claims.length?[{id:"claims",label:"先从经历库加入至少一条草稿。",href:"/vault"}]:[]} className="btn primary" title="与下方的生成润色建议快捷入口相同，都会处理当前正文。" disabledReason={cloudIssue || (busy?'两个润色按钮是同一功能，正在处理，请等完成后再操作。':editing?'请先保存或取消正在编辑的句子。':'请先在下方搜索或选择一条经历。')} disabled={Boolean(cloudIssue) || busy || editing || !workflow.resume_claims.length} onClick={() => start(true)}>{busy ? pendingOperation ? '等待确认…' : '正在处理…' : '按目标岗位润色简历'}</ActionButton>
      <ActionButton className="btn secondary" disabledReason={(!workflow.local_only && cloudIssue) || (busy?'正在生成或核验，请稍候。':editing?'请先保存或取消正在编辑的句子。':'请先在下方搜索或选择一条经历。')} disabled={Boolean((!workflow.local_only && cloudIssue)) || busy || editing || !workflow.resume_claims.length} onClick={() => start(false)}>{workflow.local_only?'本地检查草稿材料':'AI 检查材料支持'}</ActionButton>
      {workflow.local_only&&<ActionButton className="btn secondary" guideRequirements={editing?editingRequirements(reviewDrafts):!workflow.resume_claims.length?[{id:'claims',label:'先加入至少一条草稿。',selector:'[data-guide="draft-pool"]'}]:[]} disabledReason={cloudIssue || (busy?'正在处理，请稍候。':editing?'请先保存或取消正在编辑的句子。':'请先加入至少一条草稿。')} disabled={Boolean(cloudIssue) || busy||editing||!workflow.resume_claims.length} onClick={()=>start(false,true)}>用 AI 重新核验</ActionButton>}</div>
    <details><summary>确认与材料支持有什么区别？</summary><p>你可以编辑、确认并导出自己的最终稿。材料不足或冲突会保留记录，用户确认不会把它变成“材料支持”。本地导出不等于提交招聘网站。</p></details>
    {job.running ? <p role="status">正在后台润色 {workflow.resume_claims.length} 条经历。可以离开本页，回来后会自动显示建议。</p> : busy&&!pendingOperation&&<p role="status">正在处理…</p>}
    {job.message && <p role="status">{job.message}</p>}
    {!!suggestions && <p role="status">已有 {suggestions} 条润色建议。 <button className="text-action" onClick={()=>document.querySelector('.polish-comparison')?.scrollIntoView({behavior:'smooth',block:'center'})}>查看原文与改写 ↓</button></p>}
    {!suggestions && !job.running && workflow.grounding?.polish_source && <p role="status">{workflow.grounding.error||'本次没有可采用的改写。请查看各条经历的原因。'}</p>}
    {error && <p className="danger-text" role="alert">{error}</p>}
    {pendingOperation&&<RadarDialog title="确认使用模型" onClose={cancelOperation}>
      <p>本次会处理当前正文中的每条经历，并把岗位说明、经历文字和关联材料发送到后端配置的模型服务，可能产生费用。请确认材料适合发送。</p>
      <p>确认后可离开本页。后台会保留建议，回来后可逐条对照并决定是否采用。</p>
      <div className="btn-row"><Button variant="secondary" onClick={cancelOperation}>取消</Button><Button onClick={()=>{const operation=pendingOperation;setPendingOperation(null);void run(operation.polish,operation.forceModel)}}>同意并开始</Button></div>
    </RadarDialog>}
    <GroundingHistory />
  </div>
})
