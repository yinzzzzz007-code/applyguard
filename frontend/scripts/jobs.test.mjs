import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseJobImport, canPrepareJob, importMessage } from '../src/jobs.ts'
import { saveApplicationHistory, loadApplicationHistory } from '../src/history.ts'
import { readFileSync } from 'node:fs'

test('imports JSON arrays/envelopes and JSONL, and rejects partial/oversized input', () => {
  const rows = [{ title: 'Fictional A' }, { title: 'Fictional B' }]
  for (const input of [rows, { items: rows }, { jobs: rows }]) {
    assert.deepEqual(parseJobImport(JSON.stringify(input)), rows)
  }
  assert.deepEqual(parseJobImport(rows.map((r) => JSON.stringify(r)).join('\n')), rows)
  for (const input of ['{broken', '[]', '{}', '[null]\ninvalid', JSON.stringify(Array(101).fill({}))]) {
    assert.throws(() => parseJobImport(input))
  }
  assert.throws(() => parseJobImport('x'.repeat(1_900_001)))
})

test('reference, closed and archived opportunities cannot prepare applications', () => {
  assert.equal(canPrepareJob({ status: 'open', stage: 'saved' }), true)
  assert.equal(canPrepareJob({ status: 'unknown', stage: 'preparing' }), true)
  for (const job of [{ status: 'reference', stage: 'saved' }, { status: 'closed', stage: 'saved' }, { status: 'open', stage: 'archived' }]) {
    assert.equal(canPrepareJob(job), false)
  }
  assert.match(importMessage({ created: 1, updated: 2, unchanged: 3 }), /新增 1，更新 2，未变化 3/)
})

test('application summary retains opportunity version without saving JD or evidence', () => {
  const workflow = JSON.parse(readFileSync(new URL('../public/prerecorded/normal.json', import.meta.url)))
  workflow.target_job = { id: 'job_1234567890abcdef', version: 2, title: 'Fictional job', company: 'Fictional company', content_hash: 'private-hash' }
  const entries = new Map()
  const store = { getItem: (key) => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value) }
  assert.equal(saveApplicationHistory(workflow, 'SIMULATED_CONFIRMED', store), true)
  const [record] = loadApplicationHistory(store)
  assert.equal(record.title, workflow.target_job.title)
  assert.equal(record.targetJobId, workflow.target_job.id)
  assert.equal(record.targetJobVersion, 2)
  assert.equal([...entries.values()].join('').includes('private-hash'), false)
  assert.equal([...entries.values()].join('').includes(workflow.parsed_jd.source_text), false)
})
