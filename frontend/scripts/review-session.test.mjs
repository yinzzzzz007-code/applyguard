import assert from 'node:assert/strict'
import {test} from 'node:test'
import {readFileSync} from 'node:fs'
import {exitHistoryReplay,loadReviewSession,saveReviewSession} from '../src/resume/reviewSession.ts'
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
test('ending replay preserves current text and invalidates historical evidence',()=>{
 const w=fixture();w._historyReplay={label:'历史',createdAt:'2026-11-25'}
 w.resume_claims[0].text='用户编辑后的正文'
 w.grounding={mode:'sag_atomic',engine:'历史回放',snapshot:'',prompt_version:'',export_requires_atomic:true,results:{old:{}}}
 const next=exitHistoryReplay(w)
 assert.equal(next.resume_claims[0].text,'用户编辑后的正文')
 assert.equal(next._historyReplay,undefined)
 assert.equal(next.requires_reverification,true)
 assert.deepEqual(next.grounding.results,{})
 assert.equal(w._historyReplay.label,'历史')
})
