import {useEffect,useRef,useState} from 'react'
import {getApiClient,discoverMaterials} from '../api/client'
import type {EvidenceRecord,ResumeMatchItem} from '../api/types'
import {useDemo} from '../context/DemoContext'
import {targetForClaim} from '../resume/supplementRecheck'

type Candidate={row:ResumeMatchItem;record:EvidenceRecord;selected:boolean}
export function ReviewMaterials({onStart,label}:{onStart:()=>void;label:string}) {
  const {workflow,resumeForm}=useDemo()
  const [candidates,setCandidates]=useState<Candidate[]>([])
  const [missing,setMissing]=useState<string[]>([])
  const [linked,setLinked]=useState<string[]>([])
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [sagMessage,setSagMessage]=useState('')
  const mounted=useRef(true)
  useEffect(()=>{
    let active=true;mounted.current=true
    void (async()=>{
      const api=getApiClient(), spaces=await api.listEvidenceWorkspaces()
      if(spaces.error)throw Error(spaces.error.message)
      if(!workflow||!resumeForm)return
      const reports=await Promise.all((spaces.data??[]).map(async space=>{
        const result=await api.matchResumeEvidence(space.workspace_id,{projects:resumeForm.projects,internships:resumeForm.internships,awards:resumeForm.awards.map(a=>({...a,award_id:a.id}))})
        if(result.error)throw Error(result.error.message)
        return result.data?.results??[]
      }))
      const rows=reports.flat(), found:Candidate[]=[], absent:string[]=[], existing:string[]=[]
      for(const claim of workflow.resume_claims){
        const target=targetForClaim(claim.claim_id,resumeForm)
        if(!target)continue
        const matches=rows.filter(row=>row.target_type===target.target_type&&row.target_id===target.target_id)
        if(matches.some(row=>row.status==='LINKED')){existing.push(matches.find(row=>row.status==='LINKED')!.label);continue}
        const row=matches.filter(row=>row.evidence_id&&['NEEDS_CONFIRM','MATCHED','CONFLICT'].includes(row.status)).sort((a,b)=>b.score-a.score)[0]
        if(!row?.evidence_id){absent.push(matches[0]?.label||claim.text.slice(0,48));continue}
        const detail=await api.getEvidence(row.evidence_id)
        if(detail.error||!detail.data)throw Error(detail.error?.message||'无法读取候选原文')
        found.push({row,record:detail.data,selected:true})
      }
      if(active){setCandidates(found);setMissing(absent);setLinked(existing)}
    })().catch(e=>{if(active)setError(e instanceof Error?e.message:'读取材料清单失败')}).finally(()=>{if(active)setLoading(false)})
    return ()=>{active=false;mounted.current=false}
  },[])
  async function searchSAG(){
    if(!workflow||!resumeForm)return
    setBusy(true);setSagMessage('SAG 正在从材料库检索相关原文，可以稍候查看。')
    try{
      const result=await discoverMaterials(workflow,resumeForm),api=getApiClient(),found:Candidate[]=[]
      for(const row of [...result.results,...result.unresolved_candidates]){
        if(!mounted.current)return
        if(candidates.some(c=>c.row.target_id===row.target_id&&c.row.evidence_id===row.evidence_id))continue
        const detail=await api.getEvidence(row.evidence_id!)
        if(!detail.data||detail.error)throw Error(detail.error?.message||'读取命中原文失败')
        if(detail.data.file?.sha256!==row.file_sha256)throw Error('检索后材料版本已变化，请重试')
        found.push({row,record:detail.data,selected:false})
      }
      if(mounted.current){setCandidates(prev=>[...prev,...found]);setSagMessage(`SAG 已检索 ${result.source_count} 份原文，新增 ${found.length} 个候选。请核对并勾选；语义相关不代表事实已支持。`)}
    }catch(e){if(mounted.current)setSagMessage(e instanceof Error?e.message:'SAG 检索未完成')}
    finally{if(mounted.current)setBusy(false)}
  }
  async function confirm(){
    setBusy(true);setError('')
    try{
      const api=getApiClient()
      for(const {row,record} of candidates.filter(c=>c.selected)){
        if(!mounted.current)return
        const current=await api.getEvidence(record.evidence_id)
        if(current.error||current.data?.file?.sha256!==record.file?.sha256)throw Error('候选原文已更新，请重新核对材料')
        const reviewed=await api.reviewEvidence(record.evidence_id,{normalized_fields:record.normalized_fields??{},review_state:'REVIEWED',kind:record.kind})
        if(reviewed.error)throw Error(reviewed.error.message)
        const linked=await api.createEvidenceLink({target_type:row.target_type,target_id:row.target_id,evidence_id:record.evidence_id,association_confirmed:true})
        if(linked.error)throw Error(linked.error.message)
      }
      if(mounted.current)onStart()
    }catch(e){setError(e instanceof Error?e.message:'材料关联未完成，尚未启动模型')}
    finally{setBusy(false)}
  }
  return <div className="review-materials">
    <h4>本次实际核对的材料</h4>
    {loading&&<p role="status">正在检查正文与材料库的关联…</p>}
    {!!linked.length&&<p>已有 {linked.length} 条经历完成关联：{linked.join('、')}</p>}
    {candidates.map(({row,record,selected},index)=><div key={`${row.target_type}:${row.target_id}:${row.evidence_id}`} className="callout">
      <label><input type="checkbox" checked={selected} disabled={busy} onChange={e=>setCandidates(prev=>prev.map((c,i)=>i===index?{...c,selected:e.target.checked}:c))}/>{row.label} ↔ {row.relative_path}</label>
      <p className="muted">{row.notes.join('；')}</p>
      <details><summary>核对候选原文与项目归属</summary><pre style={{whiteSpace:'pre-wrap',maxHeight:240,overflow:'auto'}}>{record.spans?.map(span=>span.raw_text).join('\n')}</pre></details>
      <p className="muted">勾选并开始即确认这份材料属于该经历、识别原文可用于核对；数字是否一致由本次模型核验判断。</p>
    </div>)}
    {!!missing.filter(label=>!candidates.some(c=>c.row.label===label)).length&&<p className="callout warn">尚无相关原件：{missing.filter(label=>!candidates.some(c=>c.row.label===label)).join('、')}。这些经历将标为待确认，不会算作材料支持。</p>}
    <p className="muted">文件名未匹配时，可用 SAG 语义搜索。会将本次经历和材料库原文交给配置的模型服务，可能产生费用。</p>
    <button type="button" className="btn secondary" disabled={loading||busy||!!error} onClick={()=>void searchSAG()}>用 SAG 搜索尚未关联的材料</button>
    {sagMessage&&<p role="status">{sagMessage}</p>}
    {error&&<p role="alert" className="danger-text">{error}；尚未启动模型。请检查材料后重新打开。</p>}
    <button type="button" className="btn primary" disabled={loading||busy||!!error} onClick={()=>void confirm()}>{loading?'正在读取材料…':busy?'正在关联所选材料…':label}</button>
  </div>
}
