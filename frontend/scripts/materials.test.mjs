import assert from 'node:assert/strict'
import { test } from 'node:test'
import { materialStatus, materialName, materialFolder, orderedEvidenceSpans } from '../src/evidence/materials.ts'

test('recognition saved does not imply human review or an experience link', () => {
  const file = { relative_path: '证明.pdf', state: 'NEEDS_REVIEW', recognition_saved: true, evidence_review_state: 'UNREVIEWED' }
  assert.equal(materialStatus(file).key, 'review')
  assert.equal(materialStatus({ ...file, evidence_review_state: 'REVIEWED' }).key, 'reviewed')
})

test('failed or stale content does not retain a reviewed display', () => {
  const file = { relative_path: '证明.pdf', state: 'FAILED', recognition_saved: true, evidence_review_state: 'REVIEWED' }
  assert.equal(materialStatus(file).key, 'failed')
  assert.equal(materialStatus({ ...file, state: 'INDEXED', evidence_review_state: 'STALE' }).key, 'review')
})

test('a placeholder OCR span still needs manual inspection', () => {
  assert.equal(materialStatus({ relative_path: '证明.jpg', state: 'NEEDS_REVIEW', span_count: 1, recognition_saved: false, parse_error: '未运行本地 OCR' }).key, 'manual')
})

test('duplicate basenames remain distinguishable by their folders', () => {
  assert.equal(materialName('项目甲\\说明.md'), materialName('项目乙/说明.md'))
  assert.equal(materialFolder('项目甲\\说明.md'), '项目甲')
  assert.equal(materialFolder('项目乙/说明.md'), '项目乙')
})

test('text follows page and line order without changing the source array', () => {
  const spans = [
    { span_id: 'third', page: 2, line_start: 1 },
    { span_id: 'second', page: 1, line_start: 20 },
    { span_id: 'first', page: 1, line_start: 1 },
  ]
  assert.deepEqual(orderedEvidenceSpans(spans).map((span) => span.span_id), ['first', 'second', 'third'])
  assert.equal(spans[0].span_id, 'third')
})
