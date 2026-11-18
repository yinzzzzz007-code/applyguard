import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const UNCOVERED_RE = /JD requirement (req_\d+) has no ready evidence/i
const OFFLINE_HINT = '当前为全离线模式'

function loadJson(rel) {
  return JSON.parse(readFileSync(join(root, rel), 'utf8'))
}

function summarize(workflow) {
  const uncovered = []
  let offline = 0
  for (const risk of workflow.risk_result.risks) {
    const match = risk.message.match(UNCOVERED_RE)
    if (match) {
      if (!uncovered.includes(match[1])) uncovered.push(match[1])
      continue
    }
    if (risk.message.includes(OFFLINE_HINT)) offline += 1
  }
  for (const row of workflow.evidence_match?.uncovered_requirements ?? []) {
    if (!uncovered.includes(row.requirement_id)) uncovered.push(row.requirement_id)
  }
  const summary =
    workflow.ats_form_mapping.fields.find((f) =>
      /candidate_summary|候选人摘要|Candidate summary/i.test(`${f.field_id} ${f.label}`),
    ) ?? null
  return {
    blocked: workflow.workflow_status === 'BLOCKED' || workflow.risk_result.action === 'BLOCKED',
    needsEvidence: workflow.claim_verification.some((v) => v.state === 'BLOCKED' || v.state === 'NEEDS_REVIEW'),
    summarySources: summary?.source_claim_ids?.length ?? 0,
    offline,
    uncovered: uncovered.length,
  }
}

test('local draft merges offline and uncovered risks', () => {
  const workflow = loadJson('public/prerecorded/unsupported_block.json')
  workflow.risk_result.risks = [
    { message: '当前为全离线模式，未执行模型核验。' },
    { message: '当前为全离线模式，请核对材料。' },
    { message: 'JD requirement req_011 has no ready evidence' },
  ]
  workflow.evidence_match.uncovered_requirements = [
    { requirement_id: 'req_011' }, { requirement_id: 'req_012' },
  ]
  const stats = summarize(workflow)
  assert.equal(stats.blocked, true)
  assert.equal(stats.needsEvidence, true)
  assert.equal(stats.summarySources, 1)
  assert.equal(stats.offline, 2)
  assert.equal(stats.uncovered, 2)
})

test('prerecorded block / confirm / pass shapes', () => {
  const block = summarize(loadJson('public/prerecorded/unsupported_block.json'))
  const confirm = summarize(loadJson('public/prerecorded/timeout_fallback.json'))
  const pass = summarize(loadJson('public/prerecorded/normal.json'))
  assert.equal(block.blocked, true)
  assert.equal(block.needsEvidence, true)
  assert.equal(block.summarySources, 1)
  assert.equal(confirm.blocked, false)
  assert.equal(confirm.needsEvidence, false)
  assert.equal(confirm.offline, 0)
  assert.equal(pass.blocked, false)
  assert.equal(pass.needsEvidence, false)
})
