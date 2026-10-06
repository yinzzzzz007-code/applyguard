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

test('manual claim without evidence cannot be copied after confirmation', () => {
  const manual = {
    ...normal,
    resume_claims: [...normal.resume_claims, {
      claim_id: 'claim_manual_test', text: '虚构一等奖', evidence_ids: [],
      requirement_ids: [], evidence_support_score: 0, status: 'DRAFT',
    }],
    claim_verification: [...normal.claim_verification, {
      claim_id: 'claim_manual_test', state: 'NEEDS_REVIEW', grounded: false,
      support_score: 0, explanation: '无来源', unsupported_fragments: [],
    }],
  }
  assert.equal(copyableClaim(manual, {
    claim_manual_test: { claim_id: 'claim_manual_test', decision: 'confirm', freshness: 'as_returned' },
  }, 'claim_manual_test'), false)
})

test('linked review needs explicit confirmation and no unsupported fragment', () => {
  const original = normal.resume_claims[0]
  const reviewed = {
    ...normal,
    claim_verification: normal.claim_verification.map(item => item.claim_id === original.claim_id
      ? { ...item, state: 'NEEDS_REVIEW', grounded: false, unsupported_fragments: [] }
      : item),
  }
  const confirmed = { [original.claim_id]: { claim_id: original.claim_id, decision: 'confirm', freshness: 'as_returned' } }
  assert.equal(copyableClaim(reviewed, {}, original.claim_id), false)
  assert.equal(copyableClaim(reviewed, confirmed, original.claim_id), true)
  reviewed.claim_verification.find(item => item.claim_id === original.claim_id).unsupported_fragments = ['未证实内容']
  assert.equal(copyableClaim(reviewed, confirmed, original.claim_id), false)
})
