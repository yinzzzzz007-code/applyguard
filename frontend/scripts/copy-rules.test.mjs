import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { copyableClaim, copyableField } from '../src/copyRules.ts'
import { loadTextVersions, restoreTextVersion, saveTextVersion } from '../src/resume/groundingHistory.ts'

const normal = JSON.parse(readFileSync(new URL('../public/prerecorded/normal.json', import.meta.url)))
const blocked = JSON.parse(readFileSync(new URL('../public/prerecorded/unsupported_block.json', import.meta.url)))

test('grounded copying binds final text, atomic mode and complete result', () => {
  const value=structuredClone(normal)
  const v=value.claim_verification.find(c => c.state === 'VERIFIED')
  const c=value.resume_claims.find(c => c.claim_id === v.claim_id)
  value.grounding={mode:'sag_atomic',error:null,results:{[c.claim_id]:{state:'VERIFIED',final_text:c.text}}}
  assert.equal(copyableClaim(value,{},c.claim_id),true)
  value.grounding.mode='sag'
  assert.equal(copyableClaim(value,{[c.claim_id]:{decision:'confirm'}},c.claim_id),false)
  value.grounding.mode='sag_atomic';value.grounding.error='timeout'
  assert.equal(copyableClaim(value,{},c.claim_id),false)
  value.grounding.error=null;c.text+=' changed'
  assert.equal(copyableClaim(value,{},c.claim_id),false)
})

test('text history preserves wording but never stores verification credentials', () => {
  const data=new Map();const storage={getItem:k => data.get(k) ?? null,setItem:(k,v) => data.set(k,v)}
  const value=structuredClone(normal)
  saveTextVersion(value,'before',storage)
  const original=value.resume_claims[0].text
  value.resume_claims[0].text='Revised wording'
  saveTextVersion(value,'after',storage)
  const versions=loadTextVersions(value.candidate_id,storage)
  assert.equal(versions.length,2);assert.equal(versions[1].claims[0].text,original)
  assert.equal('claim_verification' in versions[0],false)
  assert.equal('evidence_ids' in versions[0].claims[0],false)
  assert.equal(loadTextVersions('another_candidate',storage).length,0)
  for(let n=0;n<25;n++){value.resume_claims[0].text=String(n);saveTextVersion(value,'edit',storage)}
  assert.equal(loadTextVersions(value.candidate_id,storage).length,20)
})

test('rollback restores deleted wording and records a new version without restoring approval', () => {
  const data=new Map();const storage={getItem:k => data.get(k) ?? null,setItem:(k,v) => data.set(k,v)}
  const original=structuredClone(normal)
  saveTextVersion(original,'initial',storage)
  const historical=loadTextVersions(original.candidate_id,storage)[0]
  const edited={...original,resume_claims:original.resume_claims.slice(1)}
  saveTextVersion(edited,'before rollback',storage)
  const restored=restoreTextVersion(edited,historical)
  saveTextVersion(restored,'rollback',storage,historical.id)
  assert.deepEqual(restored.resume_claims.map(c => c.text),original.resume_claims.map(c => c.text))
  assert.equal(restored.requires_reverification,true)
  assert.ok(restored.claim_verification.every(c => c.state==='NEEDS_REVIEW' && !c.grounded))
  assert.ok(restored.resume_claims.every(c => !copyableClaim(restored,{},c.claim_id)))
  assert.deepEqual(restored.human_confirmation.allowed_actions,['EDIT','CANCEL'])
  const history=loadTextVersions(original.candidate_id,storage)
  assert.equal(history[0].restoredFrom,historical.id)
  assert.deepEqual(restoreTextVersion(restored,history[1]).resume_claims.map(c => c.text),edited.resume_claims.map(c => c.text))
  assert.throws(() => restoreTextVersion(original,{...historical,candidateId:'different'}))
})

test('state-only changes and rejected suggestions are retained in history', () => {
  const data=new Map();const storage={getItem:k => data.get(k) ?? null,setItem:(k,v) => data.set(k,v)}
  const workflow=structuredClone(normal);saveTextVersion(workflow,'before',storage)
  workflow.requires_reverification=true
  workflow.grounding={results:{claim_1:{proposed_text:'Rejected suggestion',proposal_rejected:true}}}
  saveTextVersion(workflow,'after',storage)
  const history=loadTextVersions(workflow.candidate_id,storage)
  assert.equal(history.length,2)
  assert.equal(history[0].stateSnapshot.proposals[0].rejected,true)
  assert.equal(history[0].stateSnapshot.requiresReverification,true)
})

test('verified claim is copyable, blocked and edited claims are not', () => {
  const verified = normal.claim_verification.find((item) => item.state === 'VERIFIED')
  assert.ok(verified)
  assert.equal(copyableClaim(normal, {}, verified.claim_id), true)
  assert.equal(copyableClaim(normal, {
    [verified.claim_id]: { claim_id: verified.claim_id, decision: 'edit', freshness: 'edited_pending_reverify', editedText: 'changed' },
  }, verified.claim_id), false)
  const denied = blocked.claim_verification.find((item) => item.state === 'BLOCKED')
  assert.ok(denied)
  assert.equal(copyableClaim(blocked, {}, denied.claim_id), false)
  assert.equal(copyableClaim(blocked, {
    [denied.claim_id]: { claim_id: denied.claim_id, decision: 'confirm', freshness: 'as_returned' },
  }, denied.claim_id), false)
})

test('blocked field cannot be copied, and confirmation is required for a normal field', () => {
  const deniedField = blocked.ats_form_mapping.fields.find((field) =>
    blocked.field_controls.some((control) => control.field_id === field.field_id && control.action === 'BLOCKED'))
  assert.ok(deniedField)
  assert.equal(copyableField(blocked, {}, {}, deniedField), false)
  const normalField = normal.ats_form_mapping.fields.find((field) => field.source_claim_ids.length)
  assert.ok(normalField)
  assert.equal(copyableField(normal, {}, {}, normalField), true)
  const needsConfirmation = {
    ...normal,
    field_controls: normal.field_controls.map((control) => control.field_id === normalField.field_id
      ? { ...control, action: 'REQUIRES_CONFIRMATION', level: 'L2' }
      : control),
  }
  assert.equal(copyableField(needsConfirmation, {}, {}, normalField), false)
  assert.equal(copyableField(needsConfirmation, {}, {
    [normalField.field_id]: { field_id: normalField.field_id, confirmed: true, acknowledgedBlocked: false },
  }, normalField), true)
})

test('unsupported manual claims remain uncopyable even after confirmation', () => {
  const id = 'claim_manual_unknown'
  const value = structuredClone(normal)
  value.resume_claims.push({claim_id: id, text: 'Invented 900% result', evidence_ids: []})
  value.claim_verification.push({claim_id: id, state: 'NEEDS_REVIEW', grounded: false, support_score: 0})
  assert.equal(copyableClaim(value, {[id]: {decision: 'confirm', freshness: 'as_returned'}}, id), false)
})

test('draft placeholders and pending revalidation never unlock copying', () => {
  const value = structuredClone(normal)
  const claim = value.resume_claims[0]
  value.requires_reverification = true
  assert.equal(copyableClaim(value, {}, claim.claim_id), false)
  value.requires_reverification = false
  claim.evidence_ids = ['ev_draft_unverified']
  assert.equal(copyableClaim(value, {[claim.claim_id]: {decision: 'confirm'}}, claim.claim_id), false)
})

test('legacy drafts with missing basic fields remain editable', async () => {
  const { normalizeResumeForm, resumeCompleteness } = await import('../src/resume/formModel.ts')
  const draft = normalizeResumeForm({candidateId:'cand_demo_001', basic:{name:'Fictional'}, intention:{}, extras:{}, awards:[], internships:[], projects:[], education:[]})
  assert.equal(draft.basic.phone, '')
  assert.doesNotThrow(() => resumeCompleteness(draft))
})
