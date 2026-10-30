const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const out=path.resolve('output/test-reports',new Date().toISOString().replace(/[:.]/g,'-')+'_agent-browser');fs.mkdirSync(out,{recursive:true});
 const base=process.env.APPLYGUARD_TEST_URL || 'http://127.0.0.1:8872';
 const channel=process.env.APPLYGUARD_TEST_BROWSER || 'msedge';
 const browser=await chromium.launch({channel,headless:true,args:['--no-proxy-server']}); const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.on('requestfailed',r=>errors.push(r.url()+': '+r.failure()?.errorText));
 try{
  await page.goto(base+'/evidence');await page.waitForFunction(()=>getComputedStyle(document.body).fontFamily.includes('Segoe'));
  await page.getByRole('button',{name:'连接我的 Agent',exact:true}).click();
  if(!await page.getByRole('button',{name:'授权连接并生成配置（30 分钟有效）',exact:true}).isDisabled())throw new Error('Authorization enabled before disclosure choice');
  await page.getByLabel('允许访问的文件夹（绝对路径，每行一个）').fill(path.resolve('eval'));
  await page.getByLabel('允许片段进入我配置的云端模型上下文').check();
  await page.getByRole('button',{name:'授权连接并生成配置（30 分钟有效）',exact:true}).click();
  await page.getByText('等待 Agent 连接',{exact:false}).waitFor();
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  const config=JSON.parse(await page.locator('.agent-connector pre').textContent()).mcpServers.applyguard.env;
  const paired=await page.request.post(base+'/api/v1/agent/call',{headers:{Authorization:'Bearer '+config.APPLYGUARD_AGENT_TOKEN},data:{id:config.APPLYGUARD_AGENT_ID,action:'task'}});
  if(!paired.ok())throw new Error('Synthetic agent pairing failed');
  let releaseStatus,receivedStatus,finishedStatus;
  const held=new Promise(resolve=>{releaseStatus=resolve}),received=new Promise(resolve=>{receivedStatus=resolve}),finished=new Promise(resolve=>{finishedStatus=resolve});
  await page.route('**/api/v1/agent/ui',async route=>{
    if(route.request().postDataJSON().action!=='status'){await route.continue();return}
    const response=await route.fetch();receivedStatus();await held;await route.fulfill({response});finishedStatus();
  });
  await page.getByRole('button',{name:'刷新配对与候选证据',exact:true}).click();await received;
  if(!await page.getByRole('button',{name:'撤销连接',exact:true}).isEnabled())throw new Error('Revoke blocked by pending refresh');
  await page.getByRole('button',{name:'撤销连接',exact:true}).click();await page.getByText('连接已撤销；重新授权后才能继续读取。').waitFor();
  releaseStatus();await finished;await page.unroute('**/api/v1/agent/ui');
  await page.getByRole('button',{name:'授权连接并生成配置（30 分钟有效）',exact:true}).waitFor();
  if(await page.getByText('已配对，可让 Agent 搜索材料',{exact:false}).count())throw new Error('Stale response resurrected revoked connection');
  const denied=await page.request.post(base+'/api/v1/agent/call',{headers:{Authorization:'Bearer '+config.APPLYGUARD_AGENT_TOKEN},data:{id:config.APPLYGUARD_AGENT_ID,action:'task'}});
  if(denied.ok())throw new Error('Revoked agent credential remains usable');
  await page.getByRole('button',{name:'授权连接并生成配置（30 分钟有效）',exact:true}).click();
  await page.getByText('等待 Agent 连接',{exact:false}).waitFor();
  const revoked=page.waitForResponse(r=>r.url().endsWith('/api/v1/agent/ui')&&r.request().postData()?.includes('revoke'));
  await page.getByRole('link',{name:'去经历库编辑',exact:true}).click();await revoked;
  await page.goto(base+'/evidence');await page.getByRole('button',{name:'连接我的 Agent',exact:true}).click();
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  if(overflow||errors.length)throw new Error(JSON.stringify({overflow,errors}));
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({date:new Date().toISOString(),timezone:'UTC (Asia/Shanghai +08)',base,channel,status:'PASS',checks:['entry','consent-required','create','waiting-not-fake-connected','revoke-during-pending-refresh','stale-response-ignored','revoked-token-denied','route-leave-revocation','mobile-no-overflow'],errors},null,2));
  console.log('PASS',out);
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});console.log((await page.locator('body').innerText()).slice(0,1800));fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({date:new Date().toISOString(),status:'FAIL',error:String(e),errors},null,2));throw e}finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
