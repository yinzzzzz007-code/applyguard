import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { copyableClaim, copyableField } from '../src/copyRules.ts'

const normal = JSON.parse(readFileSync(new URL('../public/prerecorded/normal.json', import.meta.url)))
const blocked = JSON.parse(readFileSync(new URL('../public/prerecorded/unsupported_block.json', import.meta.url)))

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
