import assert from 'node:assert/strict'
import { test } from 'node:test'
import { reelProjects, reelFrame, projectStart, motionAllowed } from '../src/motion/reel.ts'

test('reel quotes the source without changing numbers, negation, role or time', () => {
  const original = '未主导项目；协助实现 Python 接口，测试 12 个用例。'
  const entries = [{ id: 'a', title: ' 接口测试 ', role: ' 协助开发 ', start: '2025-01', end: '2025-03', description: original }]
  const before = JSON.stringify(entries)
  const [project] = reelProjects(entries)
  assert.equal(project.excerpt, original)
  assert.equal(project.original, original)
  assert.equal(project.role, '协助开发')
  assert.equal(project.period, '2025-01 — 2025-03')
  assert.equal(JSON.stringify(entries), before)
})

test('empty projects are excluded and long quotes preserve Unicode plus an explicit ellipsis', () => {
  const entries = [
    { id: 'a', title: '', description: '不可成为项目' },
    { id: 'b', title: '无描述', description: '  ' },
    { id: 'c', title: '完整原文', description: '项目🧪'.repeat(40) },
  ]
  const [project] = reelProjects(entries)
  assert.equal(reelProjects(entries).length, 1)
  assert.equal(Array.from(project.excerpt).length, 87)
  assert.equal(project.excerpt, Array.from(entries[2].description).slice(0, 86).join('') + '…')
  assert.equal(project.original, entries[2].description)
})

test('one to four chapters fill the same 24 second timeline without a blank frame', () => {
  for (const count of [1, 2, 3, 4]) {
    assert.equal(reelFrame(0, count).phase, 'open')
    assert.equal(reelFrame(2.99, count).phase, 'open')
    for (let index = 0; index < count; index++) {
      const frame = reelFrame(projectStart(index, count) + .1, count)
      assert.equal(frame.phase, 'project')
      assert.equal(frame.index, index)
    }
    assert.equal(reelFrame(21, count).phase, 'close')
    assert.equal(reelFrame(23.99, count).phase, 'close')
    assert.deepEqual(reelFrame(24, count), reelFrame(0, count))
    assert.deepEqual(reelFrame(48.5, count), reelFrame(.5, count))
  }
})

test('autoplay stops for a user pause, reduced motion, an offscreen player or a hidden tab', () => {
  assert.equal(motionAllowed(false, false, true, true), true)
  for (const flags of [[true, false, true, true], [false, true, true, true], [false, false, false, true], [false, false, true, false]]) {
    assert.equal(motionAllowed(...flags), false)
  }
})

test('PDF presentation removes a repeated header while retaining source and limiting language', () => {
  const description = '项目 A Accepted · 协助\n研究：没有主导评测。参与整\n理 12 个样本。\n贡献：协助分析，未获得奖项。'
  const [project] = reelProjects([{id:'a',title:'项目 A',description}])
  assert.equal(project.original, description)
  assert.equal(project.body, '研究：没有主导评测。参与整理 12 个样本。\n贡献：协助分析，未获得奖项。')
  assert.match(project.excerpt,/没有主导/)
  assert.match(project.excerpt,/未获得奖项/)
})
