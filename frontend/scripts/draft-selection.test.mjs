import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {initializeDraftSelection,remainingDraftClaims,addDraftClaim,removeDraftClaim,relevanceFor} from '../src/resume/draftSelection.ts'
import {loadReviewSession,saveReviewSession} from '../src/resume/reviewSession.ts'
function setup(){
 const workflow=JSON.parse(readFileSync(new URL('../public/prerecorded/normal.json',import.meta.url)))
 delete workflow._prerecorded
 Object.assign(workflow,{resume_claims:[],claim_verification:[],review_session:{startedAt:1,actions:0,interruptions:0,choices:{}},component_modes:{career_vault:'LOCAL_RESUME_DRAFT'},
   evidence_match:{matches:[{claim_ids:['claim_python'],requirement_id:'req_python',relevance_score:.9},{claim_ids:['claim_sql'],requirement_id:'req_sql',relevance_score:.65}]},
   resume_selection:{mode:'DETERMINISTIC_EVIDENCE_CONSTRAINED',removed_claims:[],max_claims:3,max_characters:420}})
 const entry=(id,title,description)=>({id,title,description,organization:'Example',role:'Contributor'})
 const form={candidateId:workflow.candidate_id,dirty:false,basic:{},education:[],internships:[],projects:[entry('python','Atlas Python API','Used Python to build an offline prototype, not production; wrote 12 unit tests.'),entry('sql','SQL data checks','Used SQL to inspect the dataset.'),entry('finance','Bond pricing','Built a bond valuation spreadsheet.')],awards:[]}
 return {workflow,form}
}
test('draft seeds the best score per claim, includes 3.5, and prioritizes scores of six and up',()=>{
 const {workflow,form}=setup()
 workflow.evidence_match.matches=[
   {claim_ids:['claim_sql'],requirement_id:'req1',relevance_score:.35},
   {claim_ids:['claim_python'],requirement_id:'req2',relevance_score:.1,score_breakdown:{ai_score_10:6}},
   {claim_ids:['claim_python'],requirement_id:'req3',relevance_score:.52},
   {claim_ids:['claim_finance'],requirement_id:'req4',relevance_score:.8,lead:{score:.34}}]
 const next=initializeDraftSelection(workflow,form)
 assert.deepEqual(next.resume_claims.map(c=>c.claim_id),['claim_python','claim_sql'])
 assert.deepEqual(next.resume_claims[0].requirement_ids,['req2','req3'])
 assert.ok(next.claim_verification.every(r=>r.state==='NEEDS_REVIEW'&&!r.grounded))
 assert.ok(next.field_controls.every(r=>r.action==='BLOCKED'))
 assert.equal(initializeDraftSelection(next,form),next)
})

test('removing all selected experiences survives storage and never silently refills',()=>{
 const {workflow,form}=setup()
 let next=initializeDraftSelection(workflow,form)
 for(const row of remainingDraftClaims(next,form))next=addDraftClaim(next,row)
 for(const claim of [...next.resume_claims])next=removeDraftClaim(next,claim.claim_id)
 const data=new Map(),storage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)}
 saveReviewSession({workflow:next,form,jd:'Python API role',drafts:{}},storage)
 const restored=loadReviewSession(storage)
 assert.equal(restored.workflow.resume_claims.length,0)
 assert.equal(initializeDraftSelection(restored.workflow,form),restored.workflow)
 assert.equal(remainingDraftClaims(restored.workflow,form).length,3)
})
test('manual add hides the item, remove returns it, repeated id or identical text never duplicates it',()=>{
 const {workflow,form}=setup(),initialized=initializeDraftSelection(workflow,form)
 const entry=remainingDraftClaims(initialized,form)[0]
 const added=addDraftClaim(initialized,entry)
 assert.equal(remainingDraftClaims(added,form).length,0)
 assert.equal(addDraftClaim(added,entry),added)
 assert.equal(addDraftClaim(added,{...entry,claim_id:'claim_alias'}),added)
 const removed=removeDraftClaim(added,entry.claim_id)
 assert.deepEqual(remainingDraftClaims(removed,form).map(row=>row.claim_id),[entry.claim_id])
 assert.equal(removeDraftClaim(removed,entry.claim_id),removed)
})
test('a manually restored strong match appears above lower-scoring body entries',()=>{
 const {workflow,form}=setup()
 workflow.evidence_match.matches[1].relevance_score=.4
 const seeded=initializeDraftSelection(workflow,form)
 const removed=removeDraftClaim(seeded,'claim_python')
 const restored=addDraftClaim(removed,remainingDraftClaims(removed,form).find(row=>row.claim_id==='claim_python'))
 assert.deepEqual(restored.resume_claims.map(c=>c.claim_id),['claim_python','claim_sql'])
})
test('old edited drafts and explicit manual removals retain user decisions',()=>{
 const {workflow,form}=setup()
 const custom=addDraftClaim(workflow,{claim_id:'claim_custom',text:'My edited statement.',evidence_ids:[]})
 delete custom.resume_selection.draft_initialized
 assert.ok(initializeDraftSelection(custom,form).resume_claims.some(item=>item.claim_id==='claim_custom' && item.text==='My edited statement.'))
 const legacy={...workflow,resume_selection:{...workflow.resume_selection,removed_claims:[{claim_id:'claim_python',reason:'手动移出：用户从简历草稿中拿掉。'}]}}
 assert.deepEqual(initializeDraftSelection(legacy,form).resume_claims.map(row=>row.claim_id),['claim_sql'])
})
test('current working vault drafts can compose, another candidate and recorded examples cannot',()=>{
 const {workflow,form}=setup()
 assert.equal(initializeDraftSelection(workflow,{...form,dirty:true}).resume_claims.length,2)
 assert.equal(initializeDraftSelection(workflow,{...form,candidateId:'cand_other'}),workflow)
 const recorded={...workflow,_prerecorded:{case:'normal',notice:'sample'}}
 assert.equal(initializeDraftSelection(recorded,form),recorded)
 const noMatch={...workflow,evidence_match:{matches:[]}}
 assert.equal(initializeDraftSelection(noMatch,form).resume_claims.length,0)
})

test('draft and matching page use the same score precedence',()=>{
 const {workflow}=setup()
 workflow.evidence_match.matches=[
  {claim_ids:['claim_python'],relevance_score:.01,lead:{score:.85}},
  {claim_ids:['claim_sql'],relevance_score:.95,score_breakdown:{ai_score_10:2}}
 ]
 assert.ok(relevanceFor(workflow,'claim_python')>relevanceFor(workflow,'claim_sql'))
})

test('reanalysis preserves edited text and explicit removals and adds new qualifying experience',()=>{
 const {workflow,form}=setup()
 let next=initializeDraftSelection(workflow,form)
 next=removeDraftClaim(next,'claim_python')
 next.resume_claims[0].text='My edited SQL statement.'
 next.resume_selection.auto_match_threshold=undefined
 next.evidence_match.matches.push({claim_ids:['claim_finance'],requirement_id:'req_new',relevance_score:.8})
 const rerun=initializeDraftSelection(next,form)
 assert.deepEqual(rerun.resume_claims.map(c=>c.claim_id),['claim_finance','claim_sql'])
 assert.equal(rerun.resume_claims[1].text,'My edited SQL statement.')
})
