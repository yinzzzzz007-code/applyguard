const { chromium } = require('playwright')
const fs = require('node:fs')
async function run(){
  const origin = new URL(process.argv[2])
  if (origin.hostname !== '127.0.0.1') throw Error('Use a local disposable classroom test workspace.')
  const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge'})
  try {
    const page=await browser.newPage()
    await page.goto(origin.origin)
    const sample=page.getByRole('button',{name:'载入完整示例'})
    if(!await sample.isVisible()) await page.getByText('课堂演示',{exact:true}).first().click()
    await sample.click()
    await page.waitForURL('**/match')
    const steps=[]
    for(const route of ['resume','claims']){
      await page.goto(origin.origin+'/'+route)
      const quick=page.getByRole('region',{name:'快速完成'})
      await quick.getByRole('button',{name:'跳过核验，导出个人稿'}).click()
      await quick.getByRole('checkbox').check()
      const [download]=await Promise.all([page.waitForEvent('download'),quick.getByRole('button',{name:'下载个人草稿 TXT'}).click()])
      const text=fs.readFileSync(await download.path(),'utf8').trim()
      if (!text) throw Error('Empty download.')
      await quick.getByRole('link',{name:'用当前正文准备面试'}).click()
      await page.waitForURL('**/interview')
      await page.waitForFunction(expected => {
        const s=JSON.parse(sessionStorage.getItem('applyguard.interview.v1') || 'null')
        return s?.resume.projects.length>0 && s.resume.projects.every(p=>'material_status' in p) &&
          s.resume.projects.map(p=>p.description.trim()).join('\n')===expected
      },text,{timeout:10000})
      if (await page.getByText('课堂面经示例',{exact:true}).isVisible()) throw Error('Selected text was replaced by a demo.')
      steps.push({route,download:download.suggestedFilename(),matches:true})
    }
    fs.writeFileSync(process.argv[3],JSON.stringify(steps,null,2))
    console.log('PASS. Both downloads and interview handoffs use the selected body.')
  } finally {await browser.close()}
}
run().catch(e=>{console.error(e.message);process.exitCode=1})
