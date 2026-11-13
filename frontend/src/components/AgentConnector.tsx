// Gitvextor的原型：连接用户自己的 Agent，授权先于读取。
import { useEffect, useRef, useState } from 'react'
import {agentMcpConfig, connectionStage, launchHarnessCommand} from '../agentConnection'
import type {AgentConnection, HarnessSetup} from '../agentConnection'
import {HarnessSetupGuide} from './HarnessSetupGuide'
type Card = { id: string; quote: string; state: string; page: number | null; line: number; source: {path:string;version:string;commit_sha?:string}; interpretation:string; experience?:string; missing:string[]; numeric_confirmation_required:boolean }
async function api(body:object) {
  const r=await fetch('/api/v1/agent/ui',{method:'POST',headers:{'Content-Type':'application/json','X-ApplyGuard-UI':'1'},body:JSON.stringify(body)})
  let data
  try {data=await r.json()} catch {throw new Error('后端返回了无效响应，请确认 ApplyGuard 服务正在运行。')}
  if(!r.ok) throw new Error(data.error?.message || '连接失败')
  return data
}
export function AgentConnector({ensureWorkspace,onImported}:{ensureWorkspace:()=>Promise<string|null>;onImported:(id:string)=>Promise<void>}) {
  const [open,setOpen]=useState(false),[mode,setMode]=useState('local'),[roots,setRoots]=useState(''),[repos,setRepos]=useState('')
  const [task,setTask]=useState('找出我参与的数据分析项目，重点寻找本人职责、使用的技术和成果数字的依据。')
  const [purpose,setPurpose]=useState('contribution'),[disclosure,setDisclosure]=useState(''),[privateRepo,setPrivate]=useState(false)
  const [connection,setConnection]=useState<AgentConnection|null>(null),[connected,setConnected]=useState(false),[cards,setCards]=useState<Card[]>([])
  const [setup,setSetup]=useState<HarnessSetup|null>(null),[setupBusy,setSetupBusy]=useState(false),[setupError,setSetupError]=useState('')
  const [clock,setClock]=useState(()=>Date.now())
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const [sourceConfirmed,setSourceConfirmed]=useState<Record<string,boolean>>({}),[numbers,setNumbers]=useState<Record<string,boolean>>({})
  const activeConnection=useRef<string|null>(null)
  async function detectSetup() {
    setSetupBusy(true);setSetupError('')
    try {setSetup(await api({action:'setup'}))} catch(e) {setSetupError(e instanceof Error?e.message:'无法检测本机环境')}
    finally {setSetupBusy(false)}
  }
  useEffect(()=>{
    if (!open) return
    let cancelled=false
    void api({action:'setup'}).then(data=>{if(!cancelled)setSetup(data)})
      .catch(e=>{if(!cancelled)setSetupError(e instanceof Error?e.message:'无法检测本机环境')})
    return ()=>{cancelled=true}
  },[open])
  useEffect(()=>{
    if (!connection) return
    let cancelled=false, pending=false
    const poll=async()=>{
      if (pending) return
      setClock(Date.now())
      if (Date.now() >= connection.expires*1000) {setConnected(false);return}
      pending=true
      try {
        const status=await api({...connection,action:'status'})
        if (!cancelled && activeConnection.current===connection.id) {setCards(status.cards);setConnected(status.connected)}
      } catch(e) {
        if (!cancelled && activeConnection.current===connection.id) {setConnected(false);setError(e instanceof Error?e.message:'连接状态更新失败')}
      } finally {pending=false}
    }
    const interval=window.setInterval(()=>void poll(),3000)
    return ()=>{cancelled=true;window.clearInterval(interval)}
  },[connection])
  useEffect(()=>{
    if(!connection)return
    const revoke=()=>{void fetch('/api/v1/agent/ui',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-ApplyGuard-UI':'1'},body:JSON.stringify({...connection,action:'revoke'})}).catch(()=>{})}
    window.addEventListener('pagehide',revoke)
    return ()=>{window.removeEventListener('pagehide',revoke);revoke()}
  },[connection])
  async function run(fn:()=>Promise<void>) {setBusy(true);setError('');try{await fn()}catch(e){setError(e instanceof Error?e.message:'操作失败')}finally{setBusy(false)}}
  async function revoke() {
    if(!connection)return
    try{await api({...connection,action:'revoke'});activeConnection.current=null;setConnection(null);setConnected(false);setCards([]);setSourceConfirmed({});setNumbers({});setNotice('连接已撤销；重新授权后才能继续读取。');setError('')}
    catch(e){setError(e instanceof Error?e.message:'撤销未成功，请重试')}
  }
  async function copyText(text:string, label:string) {
    try {await navigator.clipboard.writeText(text);setNotice(`${label}已复制。`)}
    catch {setError('无法访问剪贴板，请展开配置后手动复制。')}
  }
  const config=connection&&setup?agentMcpConfig(setup,connection,location.origin):null
  const expired=!!connection&&clock>=connection.expires*1000
  const launch=connection&&setup?launchHarnessCommand(setup,connection,location.origin):''
  return <section className="agent-connector">
    <button type="button" className="btn secondary" aria-expanded={open} onClick={()=>setOpen(!open)}>连接 DeepSeek Harness / 其他 Agent</button>
    {connection&&!open&&<button className="btn secondary" onClick={()=>void revoke()}>撤销 Agent 连接</button>}
    {open && <div className="agent-connector-body">
      <HarnessSetupGuide setup={setup} loading={setupBusy} error={setupError} onRefresh={()=>void detectSetup()} />
      <h3 className="agent-section-heading">授权查找材料</h3><p>连接须由你授权，可随时撤销，最多30分钟有效。请保持当前页面开启；离开页面会尝试撤销。候选依据由你核对后导入。</p>
      {!connection ? <>
        <label>查找需求<textarea className="resume-input" value={task} onChange={e=>setTask(e.target.value)} /></label>
        <label>搜索范围<select className="resume-input" value={mode} onChange={e=>setMode(e.target.value)}><option value="local">本地材料</option><option value="github">GitHub</option><option value="auto">自动选择已授权来源</option></select></label>
        {mode!=='github' && <label>允许访问的文件夹（绝对路径，每行一个）<textarea className="resume-input" value={roots} onChange={e=>setRoots(e.target.value)} placeholder="例如 D:\\项目材料\\数据分析" /></label>}
        {mode!=='local' && <><label>指定仓库与版本（每行 owner/repo@完整提交 SHA）<textarea className="resume-input" value={repos} onChange={e=>setRepos(e.target.value)} /></label><label><input type="checkbox" checked={privateRepo} onChange={e=>setPrivate(e.target.checked)} />另行授权私有仓库（须在本机配置独立 GitHub 凭据）</label></>}
        <label>查找目的<select className="resume-input" value={purpose} onChange={e=>setPurpose(e.target.value)}><option value="contribution">寻找本人贡献依据</option><option value="background">查技术背景（不可导入为个人经历）</option></select></label>
        <fieldset><legend>读取前确定材料外发规则</legend><label><input type="radio" name="agent-disclosure" value="cloud_allowed" checked={disclosure==='cloud_allowed'} onChange={e=>setDisclosure(e.target.value)} />允许片段进入我配置的云端模型上下文</label><label><input type="radio" name="agent-disclosure" value="isolated_local" checked={disclosure==='isolated_local'} onChange={e=>setDisclosure(e.target.value)} />我已配置隔离的本地模型，禁止外发</label></fieldset>
        <p>本接口只能约束自己的工具。请使用仅启用此连接器的检索配置；Agent 自带的 shell 等其他工具不受这里的目录授权限制。</p>
        <button className="btn primary" disabled={busy||!disclosure||!setup?.mcp_installed||!setup.connector_exists} onClick={()=>void run(async()=>{const c=await api({action:'create',mode,task,purpose,disclosure,private:privateRepo,roots:mode==='github'?[]:roots.split('\n').map(s=>s.trim()).filter(Boolean),repos:mode==='local'?[]:repos.split('\n').map(s=>s.trim()).filter(Boolean)});activeConnection.current=c.id;setConnection(c);setClock(Date.now());setCards([]);setConnected(false);setNotice('');setSourceConfirmed({});setNumbers({})})}>授权连接并生成配置（30 分钟有效）</button>
      </> : <>
        <div className={`harness-status ${connected?'paired':''}`} role="status"><strong>{connectionStage(connection,connected,clock)}</strong><span>{new Date(connection.expires*1000).toLocaleTimeString()} 到期 · 每 3 秒自动刷新</span></div>
        {expired?<p className="harness-warning">本次授权已过期。请撤销后重新授权，并使用新的命令与令牌。</p>:<div className="harness-launch">
          <h4>在本机 Harness 完成连接</h4>
          {disclosure==='cloud_allowed'?<>
            <ol><li>复制启动命令，在本机 PowerShell 中执行；它会启动独立的 Harness 检索会话。</li>
              <li>终端询问时，粘贴“临时连接令牌”，然后输入模型 API Key。两次输入都隐藏，不写入配置文件。</li>
              <li>Harness 调用 <code>get_task → search_materials → submit_evidence</code> 后，这里会自动更新配对状态与候选证据。</li></ol>
            <div className="button-row"><button className="btn primary" disabled={!setup?.harness_command||!launch} onClick={()=>void copyText(launch,'启动命令')}>复制 PowerShell 启动命令</button>
              <button className="btn secondary" onClick={()=>void copyText(connection.token,'临时连接令牌')}>复制临时连接令牌</button></div>
            {!setup?.harness_command&&<p className="harness-warning">请先完成上方 Harness 安装步骤，或用下方手动配置接入现有 MCP 客户端。</p>}
            <details><summary>查看启动命令（不含密钥）</summary><pre>{launch}</pre></details>
          </>:<p>你选择了隔离本地模型。请使用下方手动 MCP 配置接入已隔离的 Harness profile；云端 Gemini 快捷启动不适用于本次授权。</p>}
        </div>}
        <details className="harness-manual"><summary>手动配置 / 其他 MCP 客户端（含临时凭据）</summary>
          <p>Python 与脚本已填入本机实际路径。通用 JSON 可用于支持 mcpServers 的客户端；Harness 使用 YAML patch，并通过进程环境提供临时 URL、ID 和 TOKEN。重新授权后需更新这些值。</p>
          <h4>通用 MCP JSON</h4><pre data-testid="agent-mcp-config">{JSON.stringify(config,null,2)}</pre>
          <h4>Harness MCP YAML patch</h4><pre>{setup?.mcp_patch}</pre><p>此片段只接入 MCP，不替你配置隔离模型或禁用其他工具。快捷启动使用的是专门的检索配置。</p>
        </details>
        <div className="button-row"><button className="btn secondary" disabled={busy||expired} onClick={()=>void run(async()=>{const s=await api({...connection,action:'status'});if(activeConnection.current!==connection.id)return;setCards(s.cards);setConnected(s.connected)})}>刷新配对与候选证据</button><button className="btn secondary" onClick={()=>void revoke()}>撤销连接</button></div>
      </>}
      {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
      {connected&&!cards.length&&<p>尚无候选证据。请让 Agent 调用搜索并回传引用，再刷新。</p>}
      {cards.map(c=><article className="agent-evidence" key={c.id}><h4>{c.source.path} · {c.state==='IMPORTED'?'已导入，待陈述核验':'待确认草稿'}</h4><p>{c.page?`第 ${c.page} 页`:`第 ${c.line} 行/段`} · 版本 {c.source.commit_sha||c.source.version}</p><blockquote>{c.quote}</blockquote><p>关联经历：{c.experience||'待指定'}</p><p>Agent 候选解释：{c.interpretation||'尚未回传解释'}</p><p>仍缺信息：{c.missing.join('；')||'仍需核对本人归属及支持关系'}</p>
        <label><input type="checkbox" checked={!!sourceConfirmed[c.id]} onChange={e=>setSourceConfirmed({...sourceConfirmed,[c.id]:e.target.checked})} />我已核对原文及本人归属</label>
        {c.numeric_confirmation_required&&<label><input type="checkbox" checked={!!numbers[c.id]} onChange={e=>setNumbers({...numbers,[c.id]:e.target.checked})} />我已逐项核对数字、单位及适用范围</label>}
        <button className="btn secondary" disabled={busy||c.state!=='NEEDS_REVIEW'||!sourceConfirmed[c.id]||(c.numeric_confirmation_required&&!numbers[c.id])||purpose==='background'} onClick={()=>void run(async()=>{const id=connection?.id;const ws=await ensureWorkspace();if(activeConnection.current!==id)return;if(!ws)throw new Error('请先建立材料工作区');await api({...connection,action:'accept',card_id:c.id,workspace_id:ws,confirm_source:sourceConfirmed[c.id],confirm_numbers:!!numbers[c.id]});await onImported(ws);if(activeConnection.current!==id)return;const s=await api({...connection,action:'status'});if(activeConnection.current!==id)return;setCards(s.cards);setNotice('原文片段已导入，陈述仍须经过事实核验；未自动改写简历。')})}>确认来源并导入片段</button>
      </article>)}
    </div>}
  </section>
}
