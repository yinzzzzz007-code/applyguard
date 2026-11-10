import assert from 'node:assert/strict'
import {test} from 'node:test'
import {readFileSync} from 'node:fs'
import {loadReviewSession,saveReviewSession} from '../src/resume/reviewSession.ts'
const fixture=()=>JSON.parse(readFileSync(new URL('../public/prerecorded/normal.json',import.meta.url)))
const store=()=>{const data=new Map();return {getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)}}
test('refresh recovers pending text but never historical filling permission',()=>{
 const s=store(),w=fixture(),id=w.resume_claims[0].claim_id
 saveReviewSession({workflow:w,jd:'Python job',form:null,drafts:{[id]:'unsaved text',foreign:'wrong application'}},s)
 const restored=loadReviewSession(s)
 assert.equal(restored.drafts[id],'unsaved text');assert.equal(restored.drafts.foreign,undefined)
 assert.equal(restored.workflow.requires_reverification,true)
 assert.ok(restored.workflow.claim_verification.every(v=>v.state==='NEEDS_REVIEW'&&!v.grounded))
 assert.ok(restored.workflow.field_controls.every(v=>v.action==='BLOCKED'))
 assert.deepEqual(restored.workflow.human_confirmation.allowed_actions,['EDIT','CANCEL'])
 assert.deepEqual(restored.workflow.resume_claims,w.resume_claims)
 saveReviewSession(null,s);assert.equal(loadReviewSession(s),null)
})
test('malformed and incompatible sessions do not crash hydration',()=>{
 assert.equal(loadReviewSession({getItem:()=>'{bad'}),null)
 assert.equal(loadReviewSession({getItem:()=>JSON.stringify({version:2,workflow:fixture()})}),null)
 assert.equal(loadReviewSession({getItem:()=>{throw Error('disabled')}}),null)
})
