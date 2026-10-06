const {chromium}=require('C:/Users/16X/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');
const out=path.join(__dirname,'interaction-run-01');fs.mkdirSync(out,{recursive:true});fs.copyFileSync(__filename,path.join(out,'interaction-audit.cjs'));
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const ctx=await browser.newContext({viewport:{width:1280,height:800},locale:'zh-CN'});
 await ctx.tracing.start({screenshots:true,snapshots:true,sources:true});
 const page=await ctx.newPage(),results=[],dialogs=[];
 page.on('dialog',async d=>{dialogs.push({type:d.type(),message:d.message()});await d.accept();});
 try{
  await page.goto('http://127.0.0.1:5173/');
  await page.getByRole('button',{name:'保存简历',exact:true}).waitFor();
  const name=page.locator('#resume-basic input').first();
  await name.fill('交互甲已保存（虚构）');await page.getByRole('button',{name:'保存简历',exact:true}).click();
  await page.reload();await page.getByRole('button',{name:'保存简历',exact:true}).waitFor();
  results.push({id:'I01',expected:'同标签刷新恢复已保存内容',actual:await name.inputValue()});
  await name.fill('交互乙未保存（虚构）');const before=dialogs.length;
  await page.reload();await page.getByRole('button',{name:'保存简历',exact:true}).waitFor();
  results.push({id:'I02',expected:'未保存刷新前有提醒或恢复草稿',actual:{value:await name.inputValue(),newDialogs:dialogs.slice(before)}});
  await page.getByRole('button',{name:'从种子重载',exact:true}).click();
  const resetState={value:await name.inputValue(),state:await page.locator('.resume-tip').innerText()};
  await page.reload();await page.getByRole('button',{name:'保存简历',exact:true}).waitFor();
  results.push({id:'I03',expected:'重载与dirty/持久化语义明确',actual:{afterReset:resetState,afterRefresh:await name.inputValue()}});
  await page.getByRole('button',{name:'下一步：输入 JD',exact:true}).click();
  const custom='测试交互岗位。任职要求：熟悉数据质量治理和 SQL 自动化分析。';
  await page.getByLabel('岗位说明',{exact:true}).fill(custom);const beforeSwitch=dialogs.length;
  await page.getByRole('button',{name:'正常·在线',exact:true}).click();
  await page.getByRole('button',{name:'下一步：输入 JD',exact:true}).click();
  results.push({id:'I04',expected:'重复点击当前场景不无提示重置输入',actual:{jd:await page.getByLabel('岗位说明',{exact:true}).inputValue(),newDialogs:dialogs.slice(beforeSwitch)}});
  await page.getByRole('link',{name:'经历库',exact:true}).click();
  const missingLabels=await page.locator('main input,main select,main textarea').evaluateAll(nodes=>nodes.filter(n=>!n.getAttribute('aria-label')&&!n.getAttribute('aria-labelledby')&&!(n.labels?.length)).map(n=>({tag:n.tagName,id:n.id,nearLabel:n.closest('.resume-field')?.querySelector('label')?.textContent})));
  results.push({id:'I05',expected:'表单输入有可访问名称',actual:{count:missingLabels.length,fields:missingLabels}});
  await page.setViewportSize({width:375,height:812});await page.screenshot({path:path.join(out,'vault-mobile.png'),fullPage:true});
  results.push({id:'I06',expected:'375px经历库无整页溢出',actual:await page.evaluate(()=>({innerWidth,scrollWidth:document.documentElement.scrollWidth}))});
 }catch(e){results.push({id:'SCRIPT_ERROR',actual:e.stack});}
 finally{fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({results,dialogs},null,2));await ctx.tracing.stop({path:path.join(out,'trace.zip')});await browser.close();console.log(JSON.stringify(results,null,2));}
})();
