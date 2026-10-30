import assert from 'node:assert/strict'
import { test } from 'node:test'
import { parseJobImport, canPrepareJob, importMessage, filterJobs } from '../src/jobs.ts'
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

const uiRows = [
  {title:'Python 后端',company:'北桥实验室',location:'深圳',description:'API 自动化测试',status:'open',stage:'saved',imported_at:'2026-10-20'},
  {title:'数据工程',company:'枫叶实验室',location:'上海',description:'Python SQL ETL',status:'unknown',stage:'preparing',imported_at:'2026-10-28'},
  {title:'前端开发',company:'港湾实验室',location:'深圳',description:'React TypeScript',status:'closed',stage:'archived',imported_at:'2026-10-29'},
]
test('job search combines words across fields and normalizes whitespace and case', () => {
  assert.deepEqual(filterJobs(uiRows,'  python   深圳 API  ','active','all','newest').map(j => j.title),['Python 后端'])
  assert.equal(filterJobs(uiRows,'python 上海','active','open','newest').length,0)
})
test('job views separate preparing, archived and source status without changing eligibility', () => {
  assert.deepEqual(filterJobs(uiRows,'','preparing','all','newest').map(j => j.title),['数据工程'])
  const [archived] = filterJobs(uiRows,'','archived','closed','newest')
  assert.equal(archived.title,'前端开发')
  assert.equal(canPrepareJob(archived),false)
  assert.equal(filterJobs(uiRows,'','active','closed','newest').length,0)
})
test('job sorting is deterministic and does not reorder the stored collection', () => {
  const before=uiRows.map(j => j.title)
  assert.deepEqual(filterJobs(uiRows,'','all','all','newest').map(j => j.title),['前端开发','数据工程','Python 后端'])
  assert.deepEqual(uiRows.map(j => j.title),before)
  const companies=filterJobs(uiRows,'','all','all','company').map(j => j.company)
  assert.deepEqual(companies,[...companies].sort((a,b) => a.localeCompare(b,'zh-CN')))
})
