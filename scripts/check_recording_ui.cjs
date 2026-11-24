const { chromium } = require('playwright')
const fs = require('node:fs')
const path = require('node:path')
async function main() {
  const url = new URL(process.argv[2])
  if (url.hostname !== '127.0.0.1') throw Error('请指定独立的本机录制端口。')
  const output = path.resolve(process.argv[3])
  fs.mkdirSync(output, {recursive:true})
  const browser = await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge'})
  try {
    const page = await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:1})
    const backgroundReads = []
    page.on('request', r => {
      if (r.url().endsWith('/agent/ui')) {
        const body=r.postDataJSON()
        if (['github_import_readme','github_discover','github_app_start','create','pair'].includes(body.action)) backgroundReads.push(body.action)
      }
    })
    await page.goto(url.origin)
    await page.getByText(/GitHub 私库未连接.*DeepSeek Harness 未连接/).waitFor()
    await page.screenshot({path:path.join(output,'01-start.png')})
    await page.goto(url.origin+'/evidence')
    const picker=page.locator('details').filter({has:page.locator('summary',{hasText:'从 GitHub 选择材料'})})
    await picker.locator('summary').click()
    const save = async (locator,name) => {
      await locator.scrollIntoViewIfNeeded()
      await locator.screenshot({path:path.join(output,name)})
    }
    await save(picker,'02-public-github.png')
    await picker.getByLabel('访问范围').selectOption('private')
    if (backgroundReads.length) throw Error('用户授权前发生了材料查找或读取。')
    await save(picker,'03-private-github.png')
    await picker.locator('summary').click()
    await page.getByRole('button',{name:'连接 DeepSeek Harness / 其他 Agent',exact:true}).click()
    const form=page.locator('.agent-folder-picker')
    await form.waitFor()
    await form.scrollIntoViewIfNeeded()
    await page.screenshot({path:path.join(output,'04-harness.png')})
    if (backgroundReads.length) throw Error('打开连接设置时发生了材料查找或读取。')
    console.log('PASS. Both connections start empty. Opening either picker triggered zero searches, reads or grants.')
  } finally {await browser.close()}
}
main().catch(e=>{console.error(e.message);process.exitCode=1})
