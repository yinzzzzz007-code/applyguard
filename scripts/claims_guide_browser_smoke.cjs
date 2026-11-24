const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fixture = require('../frontend/public/prerecorded/normal.json');

async function main() {
  const base = process.env.APPLYGUARD_TEST_URL || 'http://127.0.0.1:8020';
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:850},reducedMotion:'reduce'});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const texts = ['清洗训练数据并整理样本。','参与网站设计，载入时间缩短一半。','为团队维护测试脚本。'];
    const claims = texts.map((text,i)=>({...fixture.resume_claims[0],claim_id:'claim_project_'+i,text,evidence_ids:[]}));
    const checks = claims.map(c=>({...fixture.claim_verification[0],claim_id:c.claim_id,state:'NEEDS_REVIEW',explanation:'材料无法支持效果幅度。',unsupported_fragments:[]}));
    const results = Object.fromEntries(claims.map(c=>[c.claim_id,{state:'NEEDS_REVIEW',complete:true,final_text:c.text,atoms:[],retrieved_sources:[]}]));
    results.claim_project_1.atoms = [{atom_id:'a1',text:'项目减少了一半的网页加载时间。',claim_excerpt:'载入时间缩短一半',relation:'INSUFFICIENT',citations:[],reason:'材料没有给出前后用时。'}];
    const workflow = {...fixture,resume_claims:claims,claim_verification:checks,grounding:{mode:'sag_atomic',results,error:null}};
    const form = {candidateId:workflow.candidate_id,basic:{},education:[],projects:claims.map(c=>({id:c.claim_id})),internships:[],awards:[]};
    const snapshot = {exists:true,workflow,form,jd:workflow.parsed_jd.source_text,drafts:{}};
    let rechecks = 0;
    await page.route('**/api/v1/**',async route=>{
      const path=new URL(route.request().url()).pathname;
      if(path.endsWith('/workflow/draft'))return route.fulfill({json:route.request().method()==='GET'?snapshot:{ok:true}});
      if(path.endsWith('/workflow/reverify')){
        rechecks++;
        const sent = route.request().postDataJSON();
        assert.equal(sent.claims[1].text,'记录页面载入时间。');
        await new Promise(resolve=>setTimeout(resolve,250));
        return route.fulfill({json:{...workflow,resume_claims:sent.claims,grounding:{...workflow.grounding,error_code:'MODEL_TIMEOUT',failure_stage:'原子事实核验',error:'等待模型回复超时。'},requires_reverification:false}});
      }
      return route.fulfill({json:[]});
    });
    await page.goto(base+'/claims');
    const cards=page.locator('.claim-cards article');
    assert.equal(await page.locator('.claim-review-span').innerText(),'载入时间缩短一半');
    if(process.env.APPLYGUARD_FACT_SCREENSHOT)await cards.nth(1).screenshot({path:process.env.APPLYGUARD_FACT_SCREENSHOT});
    const action=(index,name)=>cards.nth(index).getByRole('button',{name,exact:true});
    await action(0,'编辑陈述').click();
    await action(1,'编辑陈述').click();
    await cards.nth(1).getByRole('textbox').fill('记录页面载入时间。');
    const supplement=action(2,'补充材料并自动核验');
    assert.ok(await supplement.isDisabled());
    await cards.nth(2).getByRole('button',{name:'查看原因与补全引导'}).click();
    const cloud=page.locator('.cloud-guide[data-guide-mode="requirement"]');
    await page.waitForSelector('#edit-claim_project_1.cloud-guide-target');
    assert.match(await cloud.innerText(),/第 2 条/);
    async function checkPlacement(){
      await page.waitForFunction(()=>{const target=document.querySelector('.cloud-guide-target'), cloud=document.querySelector('.cloud-guide-message');if(!target||!cloud)return false;
        const a=target.getBoundingClientRect(), b=cloud.getBoundingClientRect();
        return a.top>=0 && a.bottom<=innerHeight && (a.bottom<=b.top || a.top>=b.bottom || a.right<=b.left || a.left>=b.right)});
    }
    await checkPlacement();
    if(process.env.APPLYGUARD_GUIDE_SCREENSHOT)await page.screenshot({path:process.env.APPLYGUARD_GUIDE_SCREENSHOT});
    await page.setViewportSize({width:390,height:844});
    await checkPlacement();
    await action(1,'保存修改').click();
    await page.waitForSelector('#edit-claim_project_0.cloud-guide-target');
    assert.match(await cloud.innerText(),/第 1 条/);
    await action(0,'取消编辑').click();
    await cloud.waitFor({state:'hidden'});
    assert.ok(await supplement.isEnabled());
    await supplement.click();
    await page.getByRole('dialog').getByRole('button',{name:'取消'}).click();
    await page.locator('#claims-recheck').click();
    await page.getByRole('button',{name:'同意并开始核验'}).click();
    await page.getByRole('alert').filter({hasText:'等待模型回复超时'}).waitFor();
    assert.equal(await page.locator('.claim-review-span').count(),0);
    assert.equal(rechecks,1);
    assert.deepEqual(errors,[]);
    console.log('PASS: exact phrase, nearest editor, visible blue frame on desktop and mobile, save, cancel, supplement, model retry and failure without false highlights.');
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
