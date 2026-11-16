const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');

(async()=>{
 const out=path.resolve('output/test-reports',new Date().toISOString().replace(/[:.]/g,'-')+'_agent-browser');
 fs.mkdirSync(out,{recursive:true});
 const fixtures=path.join(out,'synthetic');fs.mkdirSync(fixtures);
 fs.writeFileSync(path.join(fixtures,'atlas.md'),'Atlas project: Lin used SQL to evaluate 100 examples; 84 were correct. Zhou was project lead. Lin did not train the model.');
 const base=process.env.APPLYGUARD_TEST_URL || 'http://127.0.0.1:5173';
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--no-proxy-server']});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 const errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
 const entry=()=>page.getByRole('button',{name:'连接 DeepSeek Harness / 其他 Agent',exact:true});
 let connection, live=false;
 try{
  await page.goto(base+'/evidence');await entry().click();
  await page.getByText('已检测到本机安装',{exact:true}).waitFor();
  checks.push('real-environment-detected-through-proxy');
  const authorize=()=>page.getByRole('button',{name:'授权连接并生成配置（30 分钟有效）',exact:true});
  assert.ok(await authorize().isDisabled());
  await page.getByText('首次使用：安装位置与完整准备步骤',{exact:true}).click();
  await page.locator('.harness-setup').screenshot({path:path.join(out,'harness-installation.png')});
  await page.getByText('首次使用：安装位置与完整准备步骤',{exact:true}).click();
  await page.getByLabel('查找需求').fill('Find Atlas evidence about Lin role, SQL technology and evaluation results.');
  await page.getByLabel('允许访问的文件夹（绝对路径，每行一个）').fill(fixtures);
  await page.getByLabel('允许片段进入我配置的云端模型上下文').check();
  await authorize().click();
  await page.getByText('等待 Agent 连接',{exact:true}).waitFor();
  const config=JSON.parse(await page.getByTestId('agent-mcp-config').textContent()).mcpServers.applyguard;
  connection=config.env;
  assert.ok(path.isAbsolute(config.command));assert.ok(fs.existsSync(config.args[0]));
  const command=await page.locator('.harness-launch pre').textContent();
  assert.ok(!command.includes(connection.APPLYGUARD_AGENT_TOKEN));
  checks.push('consent-required','actual-paths','authorization-not-pairing','launch-command-without-secrets');
  await page.locator('.agent-connector-body').screenshot({path:path.join(out,'harness-waiting.png')});
  if(process.env.APPLYGUARD_AI_API_KEY){
   const launcher=path.resolve('scripts/connect_harness.py');
   const child=spawn(config.command,[launcher,'--url',base,'--id',connection.APPLYGUARD_AGENT_ID],{
    env:{...process.env,...connection,PYTHONUTF8:'1'},windowsHide:true,stdio:['ignore','pipe','pipe'],timeout:240000,
   });
   let logs='';child.stdout.on('data',x=>logs+=x);child.stderr.on('data',x=>logs+=x);
   const finished=new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',(code,signal)=>resolve({code,signal}));});
   const result=await finished;
   for(const secret of [process.env.APPLYGUARD_AI_API_KEY,connection.APPLYGUARD_AGENT_TOKEN])logs=logs.split(secret).join('<REDACTED>');
   fs.writeFileSync(path.join(out,'harness.log'),logs);
   assert.equal(result.code,0,'Real Harness launcher failed; see sanitized harness.log');
   await page.getByText('已配对，可让 Agent 搜索材料',{exact:true}).waitFor({timeout:15000});
   await page.locator('.agent-evidence').first().waitFor();
   live=true;checks.push('real-harness-cli','automatic-pair-status','real-candidate-return');
  }else{
   const paired=await page.request.post(base+'/api/v1/agent/call',{headers:{Authorization:'Bearer '+connection.APPLYGUARD_AGENT_TOKEN},data:{id:connection.APPLYGUARD_AGENT_ID,action:'task'}});
   assert.ok(paired.ok());
   await page.getByText('已配对，可让 Agent 搜索材料',{exact:true}).waitFor({timeout:10000});
   checks.push('synthetic-pair-status-only');
  }
  await page.locator('.agent-connector-body').screenshot({path:path.join(out,'harness-connected.png')});
  const denied=await page.request.post(base+'/api/v1/agent/ui',{headers:{Origin:'https://untrusted.test','X-ApplyGuard-UI':'1'},data:{action:'setup'}});
  assert.equal(denied.status(),422);checks.push('foreign-origin-denied');
  let releaseStatus,receivedStatus,finishedStatus;
  const held=new Promise(r=>releaseStatus=r),received=new Promise(r=>receivedStatus=r),finished=new Promise(r=>finishedStatus=r);
  await page.route('**/api/v1/agent/ui',async route=>{
   if(route.request().postDataJSON().action!=='status'){await route.continue();return}
   const response=await route.fetch();receivedStatus();await held;await route.fulfill({response});finishedStatus();
  });
  await page.getByRole('button',{name:'刷新配对与候选证据',exact:true}).click();await received;
  assert.ok(await page.getByRole('button',{name:'撤销连接',exact:true}).isEnabled());
  await page.getByRole('button',{name:'撤销连接',exact:true}).click();
  await page.getByText('连接已撤销；重新授权后才能继续读取。',{exact:true}).waitFor();
  releaseStatus();await finished;await page.unroute('**/api/v1/agent/ui');
  assert.equal(await page.getByText('已配对，可让 Agent 搜索材料',{exact:true}).count(),0);
  const revoked=await page.request.post(base+'/api/v1/agent/call',{headers:{Authorization:'Bearer '+connection.APPLYGUARD_AGENT_TOKEN},data:{id:connection.APPLYGUARD_AGENT_ID,action:'task'}});
  assert.equal(revoked.status(),422);checks.push('revoke-during-refresh','stale-response-ignored','revoked-token-denied');
  await authorize().click();await page.getByText('等待 Agent 连接',{exact:true}).waitFor();
  const leaving=page.waitForResponse(r=>r.url().endsWith('/api/v1/agent/ui')&&r.request().postData()?.includes('revoke'));
  await page.getByRole('link',{name:'去经历库编辑',exact:true}).click();await leaving;
  checks.push('leave-page-revokes');
  await page.goto(base+'/evidence');await entry().click();
  await page.route('**/api/v1/agent/ui',async route=>{
   if(route.request().postDataJSON().action!=='setup'){await route.continue();return}
   const response=await route.fetch();const info=await response.json();
   await route.fulfill({response,json:{...info,mcp_installed:false,harness_command:null}});
  });
  await page.getByRole('button',{name:'重新检测环境',exact:true}).click();
  await page.getByText('未检测到 · 查看安装步骤',{exact:true}).waitFor();
  assert.ok(await authorize().isDisabled());
  assert.ok(await page.getByText('在 ApplyGuard 的 Python 环境安装 MCP 依赖。',{exact:true}).isVisible());
  checks.push('missing-dependencies-have-installation-steps');
  await page.setViewportSize({width:390,height:844});
  await page.locator('.harness-setup').screenshot({path:path.join(out,'mobile-missing-dependencies-simulated.png')});
  assert.ok(!await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth));
  checks.push('mobile-no-overflow');assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({date:new Date().toISOString(),base,status:'PASS',liveHarness:live,checks,errors},null,2));
  console.log('PASS '+out);
 }catch(e){
  await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({date:new Date().toISOString(),status:'FAIL',liveHarness:live,checks,error:String(e),errors},null,2));
  console.error('FAIL '+out);throw e;
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
