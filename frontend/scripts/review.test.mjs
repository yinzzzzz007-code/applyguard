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
