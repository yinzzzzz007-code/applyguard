const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const routes = {
  interview: '.interview-questions details',
  match: '.em-req-list > li',
  resume: '.review-sentence textarea',
  claims: '.claim-cards .claim',
  ats: '.profile-card',
  confirm: 'textarea.copy-pack',
  history: '.resume-history-block .item-block',
};
const output = path.join('output', 'playwright');

async function openReviewPages(browser, base, local) {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
    reducedMotion: 'reduce',
  });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.setDefaultTimeout(10000);

  if (!local) {
    await page.route('**/api/v1/demo/classroom', route => route.fulfill({
      status: 503,
      json: { error: { code: 'UNAVAILABLE', message: '示例加载暂时失败' } },
    }), { times: 1 });
    await page.goto(base + '/claims');
    await page.getByRole('button', { name: '重试载入' }).click();
    await page.locator(routes.claims).first().waitFor();
  }

  for (const [name, selector] of Object.entries(routes)) {
    await page.goto(base + '/' + name);
    await page.locator(selector).first().waitFor();
    if (['match', 'resume', 'confirm'].includes(name)) {
      await page.reload();
      await page.locator(selector).first().waitFor();
    }
    const response = await page.request.get(base + '/api/v1/workflow/draft');
    assert.ok(response.ok());
    const data = await response.json();
    assert.ok(data.workflow.resume_claims.length);
    assert.ok(data.workflow.evidence_match.matches.length);
    if (local && ['claims', 'match', 'interview'].includes(name)) {
      await page.screenshot({ path: path.join(output, 'checked-' + name + '.png') });
    }
    for (const width of [1180, 900, 760, 390]) {
      await page.setViewportSize({ width, height: 900 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      assert.ok(overflow <= 2, `${name} overflows by ${overflow}px at ${width}px`);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    console.log('PASS', local ? 'local' : 'fresh', name);
  }

  if (!local) await checkExports(page, base);
  assert.deepEqual(errors, []);
  await page.close();
}

async function checkExports(page, base) {
  await page.goto(base + '/interview');
  let download = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载面经 TXT' }).click();
  assert.match(await fs.readFile(await (await download).path(), 'utf8'), /代码维护助手/);

  await page.goto(base + '/history');
  download = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载 TXT', exact: true }).click();
  assert.match(await fs.readFile(await (await download).path(), 'utf8'), /华南理工大学/);

  await page.getByRole('link', { name: '导出个人草稿' }).click();
  await page.getByRole('checkbox', { name: /我确认最终正文/ }).check();
  download = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载个人草稿 TXT' }).click();
  assert.match((await download).suggestedFilename(), /\.txt$/);
  download = page.waitForEvent('download');
  await page.getByRole('button', { name: '下载审核记录' }).click();
  const audit = await fs.readFile(await (await download).path(), 'utf8');
  assert.doesNotThrow(() => JSON.parse(audit));

  await page.setViewportSize({ width: 390, height: 844 });
  const tools = page.locator('.review-tools');
  if (!await tools.evaluate(element => element.open)) await tools.locator('summary').first().click();
  const history = page.locator('.grounding-history');
  await history.locator('summary').first().click();
  await history.getByRole('button', { name: '保存当前版本' }).click();
  await history.locator('.grounding-history-version').first().waitFor();
  const bounds = await history.evaluate(element => ({
    padding: parseFloat(getComputedStyle(element).paddingLeft),
    width: element.clientWidth,
    scroll: element.scrollWidth,
    label: element.querySelector('summary').textContent,
  }));
  assert.ok(bounds.padding >= 12 && bounds.scroll <= bounds.width + 2, JSON.stringify(bounds));
  assert.match(bounds.label, /历史版本/);
  assert.match(bounds.label, /1 \/ 20/);
  await history.screenshot({ path: path.join(output, 'checked-history-mobile.png') });
  await page.reload();
  await tools.locator('summary').first().waitFor();
  if (!await tools.evaluate(element => element.open)) await tools.locator('summary').first().click();
  const title = history.locator('summary').first();
  assert.match(await title.textContent(), /1 \/ 20/);
  await title.click();
  await history.locator('.grounding-history-version summary').click();
  await history.getByRole('button', { name: '回滚至此版' }).click();
  assert.match(await title.textContent(), /2 \/ 20/);
  await history.getByText('回滚至：手动保存', { exact: false }).waitFor();
  console.log('PASS exports and mobile history card');
}

async function main() {
  await fs.mkdir(output, { recursive: true });
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'applyguard-review-'));
  const server = spawn(process.env.APPLYGUARD_TEST_PYTHON || 'python', ['-c', [
    'from backend.app import create_server',
    'server = create_server("127.0.0.1", 0)',
    'print(server.server_port, flush=True)',
    'server.serve_forever()',
  ].join('\n')], {
    env: {
      ...process.env,
      APPLYGUARD_LOCAL_DIR: path.join(temp, 'local'),
      APPLYGUARD_EVIDENCE_DIR: path.join(temp, 'evidence'),
    },
    stdio: ['ignore', 'pipe', 'inherit'],
  });
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      server.stdout.once('data', buffer => resolve(String(buffer).trim()));
      server.once('error', reject);
      server.once('exit', code => reject(new Error('Backend exited: ' + code)));
    });
    browser = await chromium.launch({ channel: process.env.APPLYGUARD_TEST_BROWSER || 'msedge', headless: true });
    await openReviewPages(browser, 'http://127.0.0.1:' + port, false);
    if (process.env.APPLYGUARD_TEST_URL) await openReviewPages(browser, process.env.APPLYGUARD_TEST_URL, true);
  } finally {
    if (browser) await browser.close();
    if (server.pid && server.exitCode === null && server.signalCode === null) {
      const exited = new Promise(resolve => server.once('exit', resolve));
      server.kill();
      await exited;
    }
    await fs.rm(temp, { recursive: true, force: true });
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
