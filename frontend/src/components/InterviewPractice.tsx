import {ActionButton} from './ui/action-button'
import {useState} from 'react'
import type {PracticeTurn} from '../resume/interview'

export function InterviewPractice({initial}:{initial:PracticeTurn}) {
  const [turn,setTurn]=useState(initial),[answer,setAnswer]=useState(''),[busy,setBusy]=useState(false)
  const [error,setError]=useState(''),[answered,setAnswered]=useState(false)
  async function act(action:'answer'|'retry'|'next') {
    if(busy)return
    setBusy(true);setError('')
    try {
      const r=await fetch('/api/v1/interview/practice',{method:'POST',headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(120000),
        body:JSON.stringify({action,session:initial.session,revision:turn.revision,answer:action==='answer'?answer:undefined})})
      const data=await r.json()
      if(!r.ok)throw Error(data.error?.message||'本轮未完成，请重试。')
      setTurn({...initial,...data});setAnswer('')
      if(action==='answer')setAnswered(true)
    }catch(e){setError(e instanceof Error?e.message:'未完成，请重试。')}finally{setBusy(false)}
  }
  return <section className="profile-card"><h3>一次一问 · 模拟面试</h3>
    <p>{turn.question}</p><p className="muted">出题依据 · {turn.basis}</p>
    <details><summary>答题前查看评分标准</summary><p>{Object.values(initial.rubric).join('；')}。{initial.scale}</p></details>
    <label>你的回答<textarea value={answer} rows={4} maxLength={3000} onChange={e=>setAnswer(e.target.value)}/></label>
    <p className="muted">提交后，模型会阅读回答并追问。回答只记作本次练习自述。</p>
    <div className="btn-row"><ActionButton className="btn primary" disabledReason={busy?"正在处理上一题，请等待模型返回。":"请先填写回答。"} disabled={busy||!answer.trim()} onClick={()=>void act('answer')}>{busy?'正在处理…':'提交回答并听取追问'}</ActionButton>
      {answered&&<ActionButton className="btn secondary" disabled={busy} disabledReason="正在处理上一题，请等待模型返回。" onClick={()=>void act('retry')}>复练最弱一题</ActionButton>}
      {turn.can_next!==false&&<ActionButton className="btn secondary" disabled={busy} disabledReason="正在处理上一题，请等待模型返回。" onClick={()=>void act('next')}>下一题</ActionButton>}</div>
    {turn.feedback&&<p role="status">{turn.feedback} {Object.entries(turn.scores??{}).map(([k,v])=>initial.rubric[k]+' '+v+'/2').join(' · ')}</p>}
    {error&&<p role="alert">{error}</p>}</section>
}
