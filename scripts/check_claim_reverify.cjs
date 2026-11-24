const assert = require('node:assert/strict')
const {chromium} = require('playwright')

async function main() {
  const [address, consent] = process.argv.slice(2)
  const url = new URL(address)
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || consent !== '--live-twice') {
    throw Error('指定本机地址和 --live-twice，会向配置的云模型提交当前草稿两次。')
  }
  const browser = await chromium.launch({channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge'})
  try {
    const page = await browser.newPage()
    await page.route('**/api/v1/workflow/draft', route => route.request().method() === 'GET'
      ? route.continue() : route.fulfill({json: {saved: true}}))
    await page.goto(url.origin + '/claims')
    async function confirm() {
      await page.locator('#claims-recheck').click()
      await page.getByRole('button', {name: '同意并开始核验', exact: true}).click()
    }
    const receipts = []
    for (let attempt = 0; attempt < 2; attempt++) {
      const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v1/workflow/reverify',
        {timeout: 620000})
      await confirm()
      await page.locator('#claims-progress').waitFor()
      if (attempt === 0) {
        await page.locator('a[href="/match"]').first().click()
        await page.locator('a[href="/claims"]').first().click()
      }
      const http = await response
      assert.equal(http.status(), 200)
      const report = (await http.json()).grounding
      const rows = Object.values(report.results).filter(r => r.verification_scope === 'experience')
      const noSources = rows.filter(r => r.material_status === 'no_related_material')
      const result = {run: report.run_id, seconds: report.elapsed_ms / 1000, models: report.model_routing.response_models,
        claims: rows.length, withoutSources: noSources.length, atoms: noSources.reduce((n,r) => n+r.atoms.length,0), error: report.error_code}
      console.log(JSON.stringify(result))
      assert.equal(report.error, null)
      assert.equal(report.fresh_atomic, true)
      assert.ok(result.models.length)
      assert.ok(noSources.every(r => r.state === 'NEEDS_REVIEW' && r.atoms.length && r.atoms.every(a =>
        a.method === 'model_split_without_sources' && a.relation === 'INSUFFICIENT' && !a.citations.length)))
      await page.getByTestId('verification-receipt').getByText(result.run, {exact:true}).waitFor()
      receipts.push(result.run)
    }
    assert.notEqual(receipts[0],receipts[1])
    await page.route('**/api/v1/workflow/reverify', route => route.abort('connectionrefused'))
    await confirm()
    await page.getByRole('alert').filter({hasText:'未收到核验回执'}).waitFor()
    assert.equal(await page.getByTestId('verification-receipt').count(), 0)
    console.log('Distinct receipts, in-app navigation and simulated connection loss verified.')
  } finally {
    await browser.close()
  }
}

main().catch(error => {console.error(error.message); process.exitCode = 1})
