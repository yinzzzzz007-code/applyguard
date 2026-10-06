/* Browser regression for the D-2 repair. Uses only fictional demo data. */
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const playwrightPath = process.env.PLAYWRIGHT_MODULE || 'C:/Users/16X/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
const { chromium } = require(playwrightPath)
const out = process.env.D2_EVIDENCE_DIR || path.resolve(__dirname, '../evidence/20261006-repair-01')
const frontendBase = process.env.FRONTEND_BASE_URL || 'http://127.0.0.1:5173'
fs.mkdirSync(out, { recursive: true })
const events = []
const mark = (id, result, detail = '') => events.push({ id, result, detail, at: new Date().toISOString() })

async function main() {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_EXE || 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'zh-CN' })
  await context.tracing.start({ screenshots: true, snapshots: true })
  const page = await context.newPage()
  const failures = []
  page.on('pageerror', error => failures.push(error.message))
  try {
    await page.goto(`${frontendBase}/`, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: '经历库 · 简历编辑' }).waitFor()
    const preflightResponse = await page.request.get('http://127.0.0.1:8000/api/v1/vault?candidate_id=cand_demo_001')
    assert.equal(preflightResponse.status(), 200, 'TEST_FIXTURE: active vault is unavailable')
    const preflightVault = await preflightResponse.json()
    assert.ok(preflightVault.experiences?.some(e => e.experience_id === 'exp_api_course_project'),
      'TEST_FIXTURE: expected seed project is absent; use a fresh isolated backend directory')
    mark('E2E-01', 'PASS', '经历库可加载且预期种子项目存在')

    if (await page.getByRole('button', { name: '保存简历' }).count()) {
      await page.getByRole('button', { name: '保存简历' }).click()
    }
    await page.getByRole('button', { name: '已保存' }).waitFor()
    const initial = await page.request.get('http://127.0.0.1:8000/api/v1/vault/draft?candidate_id=cand_demo_001')
    assert.equal(initial.status(), 200)
    mark('E2E-02', 'PASS', '保存成功后才显示已保存，后端可读回')
    await page.screenshot({ path: path.join(out, '01-saved.png'), fullPage: true })

    const firstProject = page.locator('.resume-entry').filter({ hasText: '项目条目' }).first()
    const editedDescription = `只参加课堂讨论，未完成接口或测试。复测 ${Date.now()}`
    await firstProject.locator('textarea').fill(editedDescription)
    assert.equal(await page.getByRole('button', { name: '下一步：输入 JD' }).isDisabled(), true)
    await page.getByRole('button', { name: '保存简历' }).click()
    await page.getByRole('button', { name: '已保存' }).waitFor()
    const vault = await (await page.request.get('http://127.0.0.1:8000/api/v1/vault')).json()
    const edited = vault.experiences.find(e => e.experience_id === 'exp_api_course_project')
    assert.equal(edited.summary, editedDescription)
    assert.deepEqual(edited.claims, [])
    assert.deepEqual(edited.evidence_sources, [])
    mark('E2E-03', 'PASS', '编辑保存后旧种子证据不再出现在活动经历')
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: '经历库 · 简历编辑' }).waitFor()
    assert.equal(await page.locator('.resume-entry').filter({ hasText: '项目条目' }).first().locator('textarea').inputValue(), editedDescription)
    mark('E2E-04', 'PASS', '刷新后从后端恢复草稿')

    await page.getByRole('button', { name: '下一步：输入 JD' }).click()
    await page.getByRole('button', { name: '运行离线工作流' }).click()
    await page.getByRole('heading', { name: '工作流已返回' }).waitFor()
    await page.getByRole('button', { name: '下一步：证据匹配' }).click()
    await page.getByRole('button', { name: '下一步：简历审查' }).click()
    await page.locator('#rr-manual').fill('我曾独立领导百人团队并取得全国一等奖。')
    await page.getByRole('button', { name: '加入草稿' }).first().click()
    await page.getByRole('button', { name: '下一步：陈述核验' }).click()
    await page.getByText('我曾独立领导百人团队并取得全国一等奖。').waitFor()
    const blocked = page.locator('article.claim.blocked').filter({ hasText: '全国一等奖' })
    assert.equal(await blocked.count(), 1)
    assert.equal(await blocked.getByRole('button', { name: '确认（禁用）' }).isDisabled(), true)
    mark('E2E-05', 'PASS', '无证据手填陈述不能确认通过')
    await page.screenshot({ path: path.join(out, '02-manual-blocked.png'), fullPage: true })

    await page.getByRole('link', { name: '岗位说明' }).click()
    await page.locator('#jd-input').fill('招聘数据工程实习生，要求使用 Python 和 SQL 完成数据处理。')
    assert.equal(await page.getByText('工作流已返回').count(), 0)
    await page.goBack()
    await page.goBack()
    await page.goBack()
    await page.getByRole('heading', { name: '尚未运行工作流' }).waitFor()
    mark('E2E-06', 'PASS', '修改 JD 后旧匹配与旧复制授权失效')
    await page.screenshot({ path: path.join(out, '03-jd-stale-cleared.png'), fullPage: true })

    assert.deepEqual(failures, [])
    mark('E2E-07', 'PASS', '无页面脚本异常')
  } catch (error) {
    mark('E2E-FAIL', 'FAIL', error.stack || String(error))
    await page.screenshot({ path: path.join(out, 'failure.png'), fullPage: true }).catch(() => {})
    throw error
  } finally {
    fs.writeFileSync(path.join(out, 'browser-results.json'), JSON.stringify({ events, pageErrors: failures, browserVersion: browser.version() }, null, 2))
    await context.tracing.stop({ path: path.join(out, 'browser-trace.zip') })
    await browser.close()
  }
}

main().catch(error => { console.error(error); process.exitCode = 1 })
