const assert = require('node:assert/strict')
const { spawn } = require('node:child_process')
const fs = require('node:fs/promises')
const path = require('node:path')
const { once } = require('node:events')
const { setTimeout: delay } = require('node:timers/promises')
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')

const fixtureServer = [
  'import os, time',
  'from unittest.mock import patch',
  'from backend import app',
  'from backend.services.job_sources.base import Snapshot, SourceError',
  'from backend.services.job_sources.registry import SOURCES',
  'from backend.services.local_store import save_resume_draft',
  'from tests.test_official_jobs import sample',
  'save_resume_draft({"candidateId":"cand_demo_001","basic":{"name":"Synthetic"},"projects":[{"id":"test","title":"Test","description":"Python HTTP API and automated testing"}],"intention":{"expectCity":"上海"}})',
  'counts={}',
  'def fetch(adapter):',
  '    key=adapter.source_id',
  '    counts[key]=counts.get(key,0)+1',
  '    time.sleep(0.35)',
  '    if key=="huawei" and counts[key]>1: raise SourceError("模拟官网超时")',
  '    job=sample(key)',
  '    job.update(title=key+" 浏览器岗位",company=adapter.company,url=adapter.source_url,source_url=adapter.source_url)',
  '    if key=="baidu" and counts[key]>2: job["requirements"] += " 欢迎熟悉 SQL。"',
  '    return Snapshot([job], True)',
  'for adapter in SOURCES.values(): adapter.fetch=fetch',
  'server=app.create_server("127.0.0.1",0)',
  'print(server.server_address[1],flush=True)',
  'server.serve_forever()',
].join('\n')

async function run() {
  const out = path.resolve('output/test-reports', new Date().toISOString().replace(/[:.]/g, '-') + '_official-jobs-browser')
  await fs.mkdir(out, { recursive: true })
  const backend = spawn(process.env.APPLYGUARD_TEST_PYTHON || 'python', ['-X', 'utf8', '-c', fixtureServer], {
    env: { ...process.env, APPLYGUARD_LOCAL_DIR: out, APPLYGUARD_JOB_AI_MATCH: 'false',
      APPLYGUARD_JOB_SOURCES: 'baidu,huawei,bytedance_seed' }, windowsHide: true,
  })
  let browser
  let startup = ''
  backend.stderr.on('data', chunk => { startup += chunk })
  try {
    const [address] = await Promise.race([
      once(backend.stdout, 'data'), once(backend, 'exit').then(() => { throw new Error(startup || 'Fixture backend exited') }),
    ])
    const base = 'http://127.0.0.1:' + String(address).trim()
    browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--no-proxy-server'] })
    const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } })
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    const waitForResponse = async (route, predicate) => {
      const deadline = Date.now() + 15000
      while (Date.now() < deadline) {
        const result = await page.request.get(base + route).then(response => response.json())
        if (predicate(result)) return result
        await delay(200)
      }
      throw new Error('Timed out waiting for ' + route)
    }
    const checkStatus = async (expected, previous) => {
      const status = await waitForResponse('/api/v1/jobs/refresh/status',
        status => status.state === expected && status.last && status.last.id !== previous)
      return status.last.id
    }
    await page.goto(base + '/jobs')
    const dashboard = page.getByRole('region', { name: '官网动态' })
    const refreshAll = dashboard.getByRole('button', { name: '刷新全部官网' })
    await dashboard.waitFor()
    assert.equal(await dashboard.getAttribute('data-slot'), 'card')
    const surface = await dashboard.evaluate(element => {
      const style = getComputedStyle(element)
      return { color: style.backgroundColor, radius: style.borderRadius, wash: style.backgroundImage }
    })
    assert.equal(surface.color, 'rgb(250, 248, 245)')
    assert.equal(surface.radius, '24px')
    assert.match(surface.wash, /linear-gradient/)
    assert.equal(await refreshAll.evaluate(element => getComputedStyle(element).borderRadius), '999px')
    await refreshAll.click()
    let runId = await checkStatus('success', '')
    await page.getByLabel('官网来源').selectOption('baidu')
    await page.getByLabel('提醒', { exact: true }).selectOption('new')
    await page.getByLabel('匹配等级').selectOption('high')
    await page.getByRole('button', { name: /baidu 浏览器岗位/ }).click()
    const match = page.getByRole('region', { name: '岗位匹配' })
    await match.getByText(/岗位提到Python/).waitFor()
    await page.screenshot({ path: path.join(out, 'matched-desktop.png') })
    await page.getByRole('button', { name: '标记岗位已读' }).click()
    await page.getByLabel('提醒', { exact: true }).selectOption('unread')
    await page.getByText('没有匹配的岗位', { exact: true }).waitFor()
    await page.getByLabel('提醒', { exact: true }).selectOption('')
    await page.getByRole('button', { name: /baidu 浏览器岗位/ }).click()
    await page.getByRole('button', { name: '重新提醒' }).click()
    await page.getByRole('button', { name: '标记岗位已读' }).waitFor()
    await dashboard.getByText('来源状态与计划', { exact: true }).click()
    await dashboard.getByLabel('百度刷新间隔').selectOption('12')
    await waitForResponse('/api/v1/jobs/sources',
      data => data.items.some(item => item.source_id === 'baidu' && item.interval_hours === 12))
    await dashboard.getByLabel('强制刷新').check()
    await dashboard.getByLabel('选择刷新来源').selectOption('baidu')
    await dashboard.getByRole('button', { name: '刷新选中来源' }).click()
    runId = await checkStatus('success', runId)
    const stable = await page.request.get(base + '/api/v1/jobs?source=baidu').then(response => response.json())
    assert.equal(stable.items[0].version, 1)
    await refreshAll.click()
    await checkStatus('partial', runId)
    await dashboard.getByText(/模拟官网超时/).waitFor()
    const stableHuawei = await page.request.get(base + '/api/v1/jobs?source=huawei').then(response => response.json())
    assert.equal(stableHuawei.items[0].status, 'open')
    await page.getByRole('button', { name: /baidu 浏览器岗位/ }).click()
    await page.getByRole('tab', { name: '版本记录' }).click()
    await page.getByRole('button', { name: '读取版本记录' }).click()
    await page.locator('.radar-versions summary').filter({ hasText: /v2/ }).waitFor()
    await page.getByRole('button', { name: '用此岗位准备申请' }).click()
    await page.waitForURL('**/jd?job=*')
    await page.goto(base + '/jobs')
    await page.setViewportSize({ width: 390, height: 844 })
    await dashboard.waitFor()
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    await page.getByRole('button', { name: /baidu 浏览器岗位/ }).click()
    assert.ok(await dashboard.isHidden())
    await page.getByRole('button', { name: '返回岗位列表' }).click()
    await dashboard.waitFor()
    assert.deepEqual(errors, [])
    await page.screenshot({ path: path.join(out, 'radar-mobile.png') })
    console.log('PASS ' + out)
  } finally {
    if (browser) await browser.close()
    backend.kill()
  }
}
run().catch(error => { console.error(error); process.exitCode = 1 })
