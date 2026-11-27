const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root=path.resolve(process.env.APPLYGUARD_PREVIEW_DIST || path.join(__dirname,'../frontend/dist'));
const types={'.js':'text/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'};
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://localhost');
  let file=path.join(root,decodeURIComponent(url.pathname));
  if(!file.startsWith(root)||!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');
  res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');
  fs.createReadStream(file).pipe(res);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({channel:'msedge',headless:true,args:['--no-proxy-server']});
  const page=await browser.newPage();let selection=null,created=null,preview=true;
  const card={id:'one',quote:'[候选人] 参与 Atlas。',state:'CANDIDATE',page:null,line:1,source:{path:'report.md',version:'v1'},interpretation:'',missing:[],numeric_confirmation_required:false,approved_for_agent:false};
  await page.route('**/api/**',async route=>{
    const req=route.request();let body={};try{body=req.postDataJSON()||{}}catch{}
    let data={};
    if(req.url().includes('/agent/ui')) {
      if(body.action==='setup') data={python:'python',install_python:'python',project_root:'D:/test',shell:'powershell',connector_path:'connector.py',launcher_path:'launcher.py',requirements_path:'requirements-agent.txt',mcp_installed:true,connector_exists:true,harness_command:'dsh',model:'test',base_url:'https://example.test',mcp_patch:'[]',session_timeout_seconds:180};
      else if(body.action==='create'){created=body;data={id:'id1',token:'agent',ui_token:'ui',expires:Date.now()/1000+1800}}
      else if(body.action==='status')data={connected:true,cards:[card],progress:{stage:preview?'awaiting_review':'searched',updated_at:Date.now()/1000,run_state:'started',candidates:1,submitted:0,search_rounds:1,workers:3,workers_finished:2,conflict_state:preview?'not_started':'finished'},conflicts:preview?[]:[{left_id:'a',right_id:'b',left_quote:'提升 20%',right_quote:'提升 10%',left_source:{path:'a.md'},right_source:{path:'b.md'},reason:'数字不同，待核对。'}],disclosure_preview:preview?{id:'preview1',cards:[card]}:null};
      else if(body.action==='review_disclosure'){selection=body.card_ids;preview=false;data={accepted:true}}
      else data={started:true};
    }
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
  });
  try {
    await page.goto(`http://127.0.0.1:${server.address().port}/evidence`);
    await page.getByRole('button',{name:'连接 DeepSeek Harness / 其他 Agent',exact:true}).click();
    await page.getByText('手动输入路径（备用）',{exact:true}).click();
    await page.getByLabel('允许访问的文件夹（绝对路径，每行一个）').fill('D:\\test');
    await page.getByLabel('允许片段进入我配置的云端模型上下文').check();
    await page.getByLabel('额外需要替换的姓名、公司或其他敏感词（每行一项，仅在本次连接中使用）').fill('张三');
    await page.getByRole('button',{name:'授权并开始查找'}).click();
    await page.getByRole('heading',{name:'选择本批允许发送给 Agent 的片段'}).waitFor({timeout:10000});
    const previewArea=page.getByRole('region',{name:'外发片段预览'});
    assert.equal(await previewArea.locator('input[type=checkbox]').count(),1);
    assert.equal(await previewArea.locator('input[type=checkbox]').isChecked(),false);
    await previewArea.locator('input[type=checkbox]').check();
    await previewArea.getByRole('button',{name:'确认本批选择'}).click();
    assert.deepEqual(selection,['one']);
    assert.deepEqual(created.private_terms,['张三']);
    assert.equal(created.review_disclosures,true);
    assert.equal(created.workers,3);
    assert.ok(created.plan.includes('个人职责'));
    await page.getByRole('heading',{name:'可能存在冲突 1，请核对原件'}).waitFor({timeout:10000});
    console.log('PASS: plan, parallel setting, privacy preview and conflict display');
  } finally {await browser.close();server.close()}
})().catch(err=>{console.error(err);server.close();process.exitCode=1});
