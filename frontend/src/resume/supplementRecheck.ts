import type {EditableResumeForm} from '../api/types'

export type SupplementTarget = {target_type:'project'|'internship'|'award'; target_id:string}
export type PendingRecheck = SupplementTarget & {claim_id:string; candidate_id:string; application_id:string; created_at:number; ready:boolean}
const KEY='applyguard.supplement-recheck.v1'
const MAX_AGE=30*60*1000

function claimId(raw:string):string {
  const body=raw.replace(/^exp_/,'').replace(/[^a-zA-Z0-9_]+/g,'_').replace(/^_+|_+$/g,'').toLowerCase()
  return (body.startsWith('claim_')?body:`claim_${body||'item'}`).slice(0,96)
}
export function targetForClaim(id:string,form:EditableResumeForm|null):SupplementTarget|null {
  if(!form)return null
  const rows:SupplementTarget[]=[
    ...form.projects.map(item=>({target_type:'project' as const,target_id:item.id})),
    ...form.internships.map(item=>({target_type:'internship' as const,target_id:item.id})),
    ...(form.awards??[]).map(item=>({target_type:'award' as const,target_id:item.id})),
  ].filter(item=>claimId(item.target_id)===id)
  return rows.length===1?rows[0]:null
}
export function getPendingRecheck(storage:Pick<Storage,'getItem'>, now=Date.now()):PendingRecheck|null {
  try {
    const value=JSON.parse(storage.getItem(KEY)??'null') as PendingRecheck|null
    if(!value||!['project','internship','award'].includes(value.target_type)||!value.target_id||!value.claim_id||
      !value.candidate_id||!value.application_id||typeof value.created_at!=='number'||
      now-value.created_at>MAX_AGE||now<value.created_at||typeof value.ready!=='boolean')return null
    return value
  } catch {return null}
}
export function savePendingRecheck(storage:Pick<Storage,'setItem'>,pending:PendingRecheck):void {storage.setItem(KEY,JSON.stringify(pending))}
export function clearPendingRecheck(storage:Pick<Storage,'removeItem'>):void {storage.removeItem(KEY)}
export function completePendingLink(storage:Pick<Storage,'getItem'|'setItem'>, target:SupplementTarget,
  candidateId:string|undefined,applicationId:string|undefined):PendingRecheck|null {
  const pending=getPendingRecheck(storage)
  if(!pending||pending.ready||pending.target_type!==target.target_type||pending.target_id!==target.target_id||
    pending.candidate_id!==candidateId||pending.application_id!==applicationId)return null
  const ready={...pending,ready:true}
  savePendingRecheck(storage,ready)
  return ready
}
