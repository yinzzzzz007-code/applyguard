import type {EditableResumeForm, LocalClaimDecision, WorkflowResponse} from '../api/types'

export function reviewedResume(form:EditableResumeForm, workflow:WorkflowResponse|null, decisions:Record<string,LocalClaimDecision>):EditableResumeForm {
  if(!workflow||workflow._prerecorded||workflow.candidate_id!==form.candidateId)return form
  const claims=new Map(workflow.resume_claims.filter(c=>decisions[c.claim_id]?.decision!=='reject').map(c=>[c.claim_id,c.text]))
  const idFor=(id:string)=>{
    const safe=id.replace(/^exp_/,'').replace(/[^a-zA-Z0-9_]+/g,'_').replace(/^_+|_+$/g,'').toLowerCase()
    return (safe.startsWith('claim_')?safe:`claim_${safe||'item'}`).slice(0,96)
  }
  const project=(rows:EditableResumeForm['projects'])=>rows.filter(row=>claims.has(idFor(row.id))).map(row=>({...row,description:claims.get(idFor(row.id))!}))
  const known=new Set([...form.projects,...form.internships,...form.awards].map(row=>idFor(row.id)))
  const education=new Set(form.education.map(row=>idFor(row.id)))
  const manual=workflow.resume_claims.filter(c=>!known.has(c.claim_id)&&!education.has(c.claim_id)&&claims.has(c.claim_id)).map(c=>({id:c.claim_id,title:'补充经历',description:c.text,organization:'',role:'',start:'',end:'',location:'',techStack:'',link:''}))
  return {...form,projects:[...project(form.projects),...manual],internships:project(form.internships),awards:form.awards.filter(row=>claims.has(idFor(row.id))).map(row=>({...row,description:claims.get(idFor(row.id))!}))}
}
