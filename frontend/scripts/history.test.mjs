import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { loadApplicationHistory, removeApplicationHistory, saveApplicationHistory } from '../src/history.ts'

const workflow = JSON.parse(readFileSync(new URL('../public/prerecorded/normal.json', import.meta.url)))

function memoryStore() {
  const data = new Map()
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
    data,
  }
}

test('local history stores only a simulation summary and can remove it', () => {
  const store = memoryStore()
  assert.equal(saveApplicationHistory(workflow, 'SIMULATED_CONFIRMED', store), true)
  const records = loadApplicationHistory(store)
  assert.equal(records.length, 1)
  assert.equal(records[0].outcome, 'SIMULATED_CONFIRMED')
  const raw = [...store.data.values()].join('')
  assert.equal(raw.includes(workflow.parsed_jd.source_text), false)
  assert.equal(raw.includes(workflow.resume_claims[0].text), false)
  assert.equal(removeApplicationHistory(records[0].id, store), true)
  assert.deepEqual(loadApplicationHistory(store), [])
})
