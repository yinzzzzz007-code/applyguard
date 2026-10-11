/**
 * Contract-aligned gate smoke (no browser).
 * Run: node scripts/smoke-mock.mjs
 */
import assert from 'node:assert/strict'

function canProceed(claims, decisions = {}) {
  for (const v of claims) {
    const d = decisions[v.claim_id]
    if (v.state === 'BLOCKED') {
      if (d?.decision === 'confirm') return false
      if (d?.decision !== 'reject') return false
    }
    if (v.state === 'NEEDS_REVIEW') {
      if (!d?.decision) return false
      if (d.decision === 'edit' || d.freshness === 'edited_pending_reverify') return false
    }
    if (d?.freshness === 'edited_pending_reverify') return false
  }
  const hasPassable = claims.some((v) => {
    const d = decisions[v.claim_id]
    if (d?.decision === 'reject') return false
    return v.state === 'VERIFIED' || (v.state === 'NEEDS_REVIEW' && d?.decision === 'confirm')
  })
  const onlyBlocked = claims.length > 0 && claims.every((v) => v.state === 'BLOCKED')
  return hasPassable || onlyBlocked
}

assert.equal(
  canProceed([{ claim_id: 'a', state: 'VERIFIED' }]),
  true,
  'VERIFIED can proceed',
)
assert.equal(
  canProceed([{ claim_id: 'a', state: 'NEEDS_REVIEW' }]),
  false,
  'NEEDS_REVIEW needs handling',
)
assert.equal(
  canProceed([{ claim_id: 'a', state: 'BLOCKED' }], {
    a: { decision: 'confirm' },
  }),
  false,
  'BLOCKED cannot confirm-around',
)
assert.equal(
  canProceed(
    [
      { claim_id: 'a', state: 'BLOCKED' },
      { claim_id: 'b', state: 'BLOCKED' },
    ],
    { a: { decision: 'reject' }, b: { decision: 'reject' } },
  ),
  true,
  'all BLOCKED rejected can inspect ATS',
)
assert.equal(
  canProceed([{ claim_id: 'a', state: 'NEEDS_REVIEW' }], {
    a: { decision: 'edit', freshness: 'edited_pending_reverify' },
  }),
  false,
  'edited pending reverify blocked',
)

console.log('SMOKE_MOCK_PASSED')
