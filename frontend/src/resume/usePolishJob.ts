import {useEffect, useRef, useState} from 'react'
import {groundingRequest} from '../api/client'
import type {GroundingReport} from '../api/types'
import {useDemo} from '../context/DemoContext'
import {saveTextVersion} from './groundingHistory'
import {invalidateRestoredWorkflow} from './reviewSession'
import {polishResultSummary} from './review'

type Job = {state:'idle'|'running'|'ready'|'seen'|'stale'|'failed'; run_id?:string; message?:string; grounding?:GroundingReport}

export function usePolishJob() {
  const {workflow,resumeForm,reviewDrafts,setWorkflow} = useDemo()
  const [running,setRunning] = useState(false)
  const [message,setMessage] = useState('')
  const [revision,setRevision] = useState(0)
  const retryRun = useRef('')
  const editing = Object.keys(reviewDrafts).length > 0

  useEffect(()=>{
    let active = true, timer:ReturnType<typeof setTimeout>|undefined, checking=false
    setRunning(false)
    setMessage('')
    retryRun.current=''
    if(!workflow || workflow._prerecorded || workflow._historyReplay || !workflow.resume_claims.length) return
    const draft = workflow
    async function check() {
      if(!active||checking)return
      checking=true
      clearTimeout(timer)
      const result=await groundingRequest<Job>('polish/status',draft,resumeForm,{
        grounding_mode:'sag_atomic',local_only:false,known_run:draft.grounding?.run_id})
      checking=false
      if(!active)return
      const job=result.data
      if(!job) {
        setMessage('暂时无法读取后台进度，将自动重试。')
        timer=setTimeout(check,8000);return
      }
      setRunning(job.state==='running')
      setMessage(job.message||'')
      if(job.state==='running') {timer=setTimeout(check,3500);return}
      if(job.state==='seen'||job.state==='stale'||job.state==='failed') {retryRun.current=job.run_id||'';return}
      const report=job.grounding
      if(job.state!=='ready'||!report||report.run_id===draft.grounding?.run_id)return
      if(editing){setMessage('建议已保存在本机。请先保存或取消正在编辑的正文。');return}
      if(!draft.resume_claims.every(c=>report.results[c.claim_id]?.original_text===c.text))return
      const next={...invalidateRestoredWorkflow(draft,'润色建议待审阅，请按当前正文核验。'),grounding:report,_historyReplay:undefined}
      // Browser history is optional. A full storage quota must not hide the server result.
      try {
        saveTextVersion(draft,'润色前')
        if(polishResultSummary(next).count)saveTextVersion(next,'建议已生成：等待预览与采用')
      }catch { /* The backend keeps the original run. */ }
      setWorkflow(next)
    }
    void check()
    window.addEventListener('focus',check)
    return ()=>{active=false;clearTimeout(timer);window.removeEventListener('focus',check)}
  },[workflow,resumeForm,editing,revision,setWorkflow])

  async function start(){
    if(!workflow||editing||running)return
    if(workflow._historyReplay)setWorkflow({...workflow,_historyReplay:undefined})
    const result=await groundingRequest<Job>('polish/start',workflow,resumeForm,{
      grounding_mode:'sag_atomic',local_only:false,known_run:retryRun.current||workflow.grounding?.run_id})
    setRevision(n=>n+1)
    if(!result.data){throw Error(result.error?.message||'未收到后台确认。返回本页可查看任务状态。')}
  }
  return {running,message,start}
}
