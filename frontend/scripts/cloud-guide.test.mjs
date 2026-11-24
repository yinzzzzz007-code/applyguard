import {test} from 'node:test'
import assert from 'node:assert/strict'
import {orderRequirements,editingRequirements,guideForPage,reopenGuide,GUIDE_PAGES} from '../src/guide.ts'
import {authorizationRequirements} from '../src/githubGuide.ts'
test('missing requirements point to real modules and disappear only after their inputs are completed',()=>{
 const initial={mode:'local',folders:0,repos:'',task:'找本人项目依据',privateRepo:false,disclosure:'',setup:{mcp_installed:true,connector_exists:true}}
 const missing=authorizationRequirements(initial)
 assert.deepEqual(missing.map(x=>x.id),['folders','disclosure'])
 const distances={folders:400,disclosure:120}
 assert.deepEqual(orderRequirements(missing,x=>distances[x.id]).map(x=>x.id),['disclosure','folders'])
 assert.deepEqual(authorizationRequirements({...initial,disclosure:'cloud_allowed'}).map(x=>x.id),['folders'])
 assert.deepEqual(authorizationRequirements({...initial,disclosure:'cloud_allowed',folders:1}),[])
 assert.equal(initial.disclosure,'')
})
test('equal-distance requirements keep their original order, off-page targets come last',()=>{
 const items=[{id:'a'},{id:'b'},{id:'c'}]
 assert.deepEqual(orderRequirements(items,x=>x.id==='a'?Infinity:20).map(x=>x.id),['b','c','a'])
 assert.deepEqual(items.map(x=>x.id),['a','b','c'])
})

test('each unsaved sentence is a separate guide item; saving one leaves the other',()=>{
 const drafts={claim_a:'first',claim_b:'second'}
 const items=editingRequirements(drafts)
 assert.deepEqual(items.map(x=>x.id),['editing-claim_a','editing-claim_b'])
 assert.deepEqual(editingRequirements({claim_b:drafts.claim_b}).map(x=>x.id),['editing-claim_b'])
 assert.equal(items[1].selector,'[data-claim-id="claim_b"]')
})

test('explicit AI polish and recheck use the model even when the JD was parsed offline',async()=>{
 const {reviewTransport}=await import('../src/resume/modelReview.ts')
 assert.deepEqual(reviewTransport(true,false,true),{usesModel:true,local_only:false})
 assert.deepEqual(reviewTransport(false,true,true),{usesModel:true,local_only:false})
 assert.deepEqual(reviewTransport(false,false,true),{usesModel:false,local_only:true})
})

test('every workspace page resolves its own guide even with no earlier completion events',()=>{
 const routes=['/','/vault','/evidence','/jobs','/jd','/match','/resume','/claims','/ats','/confirm','/history','/interview','/help']
 assert.equal(GUIDE_PAGES.length,routes.length)
 for(const path of routes){
   assert.equal(guideForPage(path)?.href,path)
   if(path!=='/')assert.notEqual(guideForPage(path)?.id,'import')
 }
 assert.equal(guideForPage('/interview/').id,'interview')
 assert.equal(guideForPage('/unknown'),undefined)
})

test('reopening on a restored later page preserves completion and never restarts the global tour',()=>{
 const previous={dismissed:true,completed:['import','vault','evidence','jd']}
 const reopened=reopenGuide(previous)
 assert.equal(reopened.dismissed,false)
 assert.deepEqual(reopened.completed,previous.completed)
 assert.equal(previous.dismissed,true)
 assert.equal(guideForPage('/resume').id,'resume')
 assert.equal(guideForPage('/jobs').id,'jobs')
})

test('only a real completion on the current page points to its next step',()=>{
 assert.equal(guideForPage('/vault','vault').id,'evidence')
 assert.equal(guideForPage('/confirm','confirm').id,'history')
 assert.equal(guideForPage('/resume','import').id,'resume')
 assert.equal(guideForPage('/interview','jd').id,'interview')
 assert.equal(guideForPage('/jobs','jobs').id,'jobs')
})

test('resume guide points to the actual prerequisite instead of an unusable polish button',()=>{
 const state={hasWorkflow:true,hasForm:true,formDirty:false,claimCount:0,editingIds:[]}
 assert.equal(guideForPage('/resume',undefined,state).selector,'[data-guide="draft-pool"]')
 assert.equal(guideForPage('/resume',undefined,{...state,claimCount:3}).selector,'[data-guide="draft-document"]')
 assert.equal(guideForPage('/resume',undefined,{...state,claimCount:3,editingIds:['claim_python']}).selector,'[data-claim-id="claim_python"]')
 assert.equal(guideForPage('/resume',undefined,{...state,hasWorkflow:false}).href,'/jd')
 assert.equal(guideForPage('/resume',undefined,{...state,formDirty:true}).selector,'[data-guide="draft-pool"]')
})
