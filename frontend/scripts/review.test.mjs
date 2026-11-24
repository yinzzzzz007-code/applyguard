import assert from 'node:assert/strict'
import {test} from 'node:test'
import {readFileSync} from 'node:fs'
import {changeClaim,mergeReviewResult,reviewPriority,currentSupport,changedSpan} from '../src/resume/review.ts'
import {restoreTextVersion} from '../src/resume/groundingHistory.ts'
const fixture=()=>JSON.parse(readFileSync(new URL('../public/prerecorded/normal.json',import.meta.url)))
test('a user confirmation is independent of evidence, and text edits invalidate evidence',()=>{
 const w=fixture(), id=w.resume_claims[0].claim_id
 const confirmed=changeClaim(w,id,w.resume_claims[0].text,'accept')
 assert.deepEqual(confirmed.claim_verification,w.claim_verification)
 const edited=changeClaim(w,id,'User authored unsupported sentence','edit')
 assert.equal(edited.claim_verification[0].state,'NEEDS_REVIEW')
 assert.equal(edited.requires_reverification,true)
 assert.equal(edited.review_session.choices[id].text,edited.resume_claims[0].text)
 assert.equal(reviewPriority(edited,id),0)
 assert.equal(currentSupport(edited,id),'当前文字待核验')
 assert.throws(()=>changeClaim(w,id,'','edit'))
 assert.throws(()=>changeClaim(w,id,'x'.repeat(421),'edit'))
})
test('all model rewrites remain previews until a user explicitly adopts them',()=>{
 const w=fixture(), id=w.resume_claims[0].claim_id, old=w.resume_claims[0].text
 const result={resume_claims:w.resume_claims.map(c=>c.claim_id===id?{...c,text:'Changed suggestion'}:c),grounding:{results:{[id]:{original_text:old,final_text:'Changed suggestion',state:'VERIFIED',change_audit:{sensitive_change:false}}}}}
 const preview=mergeReviewResult(w,result)
 assert.equal(preview.resume_claims[0].text,old)
 assert.equal(preview.grounding.results[id].proposed_text,'Changed suggestion')
 assert.equal(preview.requires_reverification,true)
 const accepted=changeClaim(preview,id,'Changed suggestion','accept')
 assert.equal(accepted.resume_claims[0].text,'Changed suggestion')
 assert.equal(accepted.claim_verification[0].state,'NEEDS_REVIEW')
 result.grounding.results[id].change_audit.sensitive_change=true
 const held=mergeReviewResult(w,result)
 assert.equal(held.resume_claims[0].text,old)
 assert.equal(held.requires_reverification,true)
 assert.equal(held.review_session.choices[id],undefined)
 assert.equal(held.review_session.actions,0)
 assert.equal(reviewPriority(held,id),4)
 assert.equal(w.review_session,undefined)
})
test('history cannot restore a different application; restoring does not inherit confirmation',()=>{
 const w=fixture();w.review_session={choices:{a:{}},startedAt:1,actions:1,interruptions:0}
 assert.throws(()=>restoreTextVersion(w,{applicationId:'another',claims:[]}))
 const restored=restoreTextVersion(w,{applicationId:w.application_id,claims:[{claim_id:'claim_x',text:'old'}]})
 assert.deepEqual(restored.review_session.choices,{})
 assert.equal(restored.review_session.actions,2)
 assert.equal(restored.requires_reverification,true)
})
test('highlight finds changed part and retains full proposal',()=>{
 for(const [a,b] of [['参与开发','主导开发'],['仅离线测试','测试'],['约30%','30%']]) assert.equal(changedSpan(a,b).join(''),b)
})

test('a wording-approved rewrite stays in preview and does not upgrade insufficient evidence',()=>{
 const w=fixture(), id=w.resume_claims[0].claim_id, original=w.resume_claims[0].text, text='Reordered draft'
 const state={resume_claims:w.resume_claims.map(c=>c.claim_id===id?{...c,text}:c),grounding:{results:{[id]:{
   final_text:text,state:'NEEDS_REVIEW',relation:'INSUFFICIENT',proposal_applied:true,
   wording_auto_applied:true,change_audit:{sensitive_change:true}}}}}
 const preview=mergeReviewResult(w,state)
 assert.equal(preview.resume_claims[0].text,original)
 assert.equal(preview.grounding.results[id].proposed_text,text)
 assert.equal(reviewPriority(preview,id),1)
 const accepted=changeClaim(preview,id,text,'accept')
 assert.equal(accepted.resume_claims[0].text,text)
 assert.equal(accepted.claim_verification[0].state,'NEEDS_REVIEW')
 assert.equal(currentSupport(accepted,id),'当前文字待核验')
})

test('legacy demo labels retain blocking but edits still require verification',()=>{
 const w=JSON.parse(readFileSync(new URL('../public/prerecorded/unsupported_block.json',import.meta.url)))
 w._prerecorded={case:'unsupported_block',notice:'Demo only'}
 const id=w.resume_claims[0].claim_id
 assert.equal(currentSupport(w,id),'预录结果：已阻断')
 const edited=changeClaim(w,id,'A changed sentence','edit')
 assert.equal(currentSupport(edited,id),'当前文字待核验')
})

test('proposal status distinguishes supported, incomplete, contradictions and unavailable checks',async()=>{
 const {proposalStatus}=await import('../src/resume/review.ts')
 const base={verification_scope:'experience',proposal_rejected:false}
 assert.match(proposalStatus(base),/尚无独立事实核查/)
 assert.match(proposalStatus({...base,proposal_check:{relation:'SUPPORTED',complete:true}}),/已对照材料核查/)
 assert.match(proposalStatus({...base,proposal_check:{relation:'SUPPORTED',complete:true},proposal_rejected:true}),/其他改写检查未确认/)
 assert.match(proposalStatus({...base,proposal_check:{relation:'CONTRADICTED',complete:true}}),/存在冲突/)
 assert.match(proposalStatus({...base,proposal_check:{relation:'SUPPORTED',complete:false}}),/不完整/)
 assert.match(proposalStatus(base,'服务失败'),/核查未完成/)
})

test('education profile exemption requires exact form-bound identity and content',async()=>{
 const {isEducationProfile}=await import('../src/resume/review.ts')
 const form={education:[{id:'education_0',school:'华南理工大学',degree:'本科',major:'数据科学与大数据技术',start:'2024',end:'2028'}]}
 const claim={claim_id:'claim_education_0',text:'华南理工大学 · 本科 · 数据科学与大数据技术 · 2024 — 2028'}
 assert.equal(isEducationProfile(claim,form),true)
 assert.equal(isEducationProfile({...claim,text:claim.text+'，项目负责人'},form),false)
 assert.equal(isEducationProfile({...claim,claim_id:'claim_projects_0'},form),false)
 assert.equal(isEducationProfile(claim,null),false)
})

test('polish diff retains both texts and distinguishes unverified changes', async()=>{
 const {diffSpans, proposalNeedsReview}=await import('../src/resume/review.ts')
 for(const [before,after] of [['负责3个项目，准确率约80%','负责3个项目，准确率80%'],['ABCABC','ABCXABC'],['参与😀开发','主导😀开发'],['删除文字',''],['','新增文字']]){
  const diff=diffSpans(before,after)
  assert.equal(diff.original.map(p=>p.text).join(''),before)
  assert.equal(diff.proposal.map(p=>p.text).join(''),after)
  if(before!==after)assert.ok([...diff.original,...diff.proposal].some(p=>p.changed))
 }
 assert.equal(proposalNeedsReview({}),true)
 assert.equal(proposalNeedsReview({proposal_check:{relation:'SUPPORTED',complete:true}}),false)
 assert.equal(proposalNeedsReview({proposal_check:{relation:'CONTRADICTED',complete:true}}),true)
 assert.equal(proposalNeedsReview({proposal_check:{relation:'SUPPORTED',complete:true}},'核查失败'),true)
})


test('supplement recheck is bound to the selected claim, application, and consent window',async()=>{
 const {targetForClaim,savePendingRecheck,getPendingRecheck,completePendingLink,clearPendingRecheck}=await import('../src/resume/supplementRecheck.ts')
 const form={projects:[{id:'projects_0'}],internships:[{id:'exp_work_1'}],awards:[{id:'award_1'}]}
 assert.deepEqual(targetForClaim('claim_projects_0',form),{target_type:'project',target_id:'projects_0'})
 assert.deepEqual(targetForClaim('claim_work_1',form),{target_type:'internship',target_id:'exp_work_1'})
 assert.equal(targetForClaim('claim_manual_1',form),null)
 const map=new Map();const storage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)}
 const pending={target_type:'project',target_id:'projects_0',claim_id:'claim_projects_0',candidate_id:'cand_1',application_id:'app_1',created_at:Date.now(),ready:false}
 savePendingRecheck(storage,pending)
 assert.equal(completePendingLink(storage,{target_type:'project',target_id:'other'},'cand_1','app_1'),null)
 assert.equal(completePendingLink(storage,pending,'other','app_1'),null)
 assert.equal(getPendingRecheck(storage,pending.created_at+31*60*1000),null)
 assert.equal(completePendingLink(storage,pending,'cand_1','app_1').ready,true)
 assert.equal(completePendingLink(storage,pending,'cand_1','app_1'),null)
 clearPendingRecheck(storage);assert.equal(getPendingRecheck(storage),null)
})

test('shared polish lock prevents duplicate starts until cancellation or completion', async()=>{
 const {createOperationLock}=await import('../src/resume/operationLock.ts')
 const lock=createOperationLock()
 const observed=[]
 const unsubscribe=lock.subscribe(value=>observed.push(value))
 assert.equal(lock.acquire(),true)
 assert.equal(lock.isLocked(),true)
 assert.equal(lock.acquire(),false)
 assert.deepEqual(observed,[true])
 unsubscribe()
 lock.release()
 assert.equal(lock.acquire(),true)
 assert.equal(lock.acquire(),false)
 lock.release()
 assert.equal(lock.acquire(),true)
})

test('failed and partial polish outcomes do not create a false success history label',async()=>{
 const {polishResultSummary,historyVersionLabel}=await import('../src/resume/review.ts')
 assert.deepEqual(polishResultSummary({grounding:{error:'服务失败',results:{}}}),{count:0,error:'服务失败'})
 assert.deepEqual(polishResultSummary({grounding:{error:null,results:{a:{original_text:'原文',proposed_text:'原文'}}}}),{count:0,error:null})
 assert.deepEqual(polishResultSummary({grounding:{error:'核验未完成',results:{a:{proposed_text:'建议'}}}}),{count:1,error:'核验未完成'})
 assert.match(historyVersionLabel('建议已生成：等待预览与采用',0),/未生成建议/)
 assert.equal(historyVersionLabel('建议已生成：等待预览与采用',1),'建议已生成：等待预览与采用')
 assert.equal(historyVersionLabel('建议已生成：等待预览与采用',null),'建议已生成：等待预览与采用')
})

test('the unresolved current conflict comes before other suggestions without reordering the draft',async()=>{
 const {reviewPriority}=await import('../src/resume/review.ts')
 const workflow={resume_claims:[{claim_id:'a',text:'draft A'},{claim_id:'b',text:'draft B'}],grounding:{results:{
   a:{original_text:'draft A',final_text:'draft A',proposed_text:'revised A',state:'NEEDS_REVIEW'},
   b:{original_text:'draft B',final_text:'draft B',state:'BLOCKED',relation:'CONTRADICTED'}}}}
 assert.ok(reviewPriority(workflow,'b')>reviewPriority(workflow,'a'))
 workflow.resume_claims[1].text='user correction'
 assert.ok(reviewPriority(workflow,'b')<5)
})
