import {useState} from 'react'
import {Link} from 'react-router-dom'
import {useDemo} from '../context/DemoContext'
import {GroundedExport} from './GroundedExport'

export function QuickReviewActions() {
  const {workflow,claimDecisions,reviewDrafts}=useDemo()
  const [open,setOpen]=useState(false)
  if(!workflow)return null
  const claims=workflow.resume_claims.filter(c=>claimDecisions[c.claim_id]?.decision!=='reject').map(c=>{
    const text=claimDecisions[c.claim_id]?.editedText??c.text
    const checked=workflow.grounding?.results[c.claim_id]
    const state=checked?.final_text===text && !workflow.requires_reverification?checked.state:'尚未核验'
    return {id:c.claim_id,text,state}
  })
  const ready=claims.length>0&&!Object.keys(reviewDrafts).length
  return <section aria-label="快速完成"><div className="btn-row">
    <button className="btn secondary" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>跳过核验，导出个人稿</button>
    {ready&&<Link className="btn secondary" to="/interview" state={{selectedClaims:claims}}>用当前正文准备面试</Link>}
    {!ready&&<span>准备面试前请保存正在编辑的正文，并保留至少一条经历。</span>}</div>
    {open&&<GroundedExport editing={Object.keys(reviewDrafts).length>0}/>}</section>
}
