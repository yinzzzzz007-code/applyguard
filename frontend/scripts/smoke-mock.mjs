/**
 * Contract-aligned gate smoke (no browser).
 * Run: node scripts/smoke-mock.mjs
 */
import assert from 'node:assert/strict'

function canProceed(claims, decisions = {}) {
  for (const v of claims) {
    const d = decisions[v.claim_id]
    if (d?.decision === 'edit' || d?.freshness === 'edited_pending_reverify') return false
    if (d?.decision === 'reject' || d?.freshness === 'rejected') continue
    if (d?.decision === 'confirm' && (v.state === 'BLOCKED' || v.state === 'NEEDS_REVIEW')) continue
    if (v.state === 'BLOCKED' || v.state === 'NEEDS_REVIEW') return false
    if (v.state === 'VERIFIED') continue
    return false
  }
  const hasPassable = claims.some((v) => {
    const d = decisions[v.claim_id]
    if (d?.decision === 'reject' || d?.freshness === 'rejected') return false
    return v.state === 'VERIFIED'
      || ((v.state === 'NEEDS_REVIEW' || v.state === 'BLOCKED') && d?.decision === 'confirm')
  })
  const onlyBlockedHandled = claims.length > 0 && claims.every((v) => {
    if (v.state !== 'BLOCKED') return false
    const d = decisions[v.claim_id]
    return d?.decision === 'reject' || d?.decision === 'confirm' || d?.freshness === 'rejected'
  })
  return hasPassable || onlyBlockedHandled
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
  true,
  'BLOCKED can acknowledge mismatch and keep',
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
