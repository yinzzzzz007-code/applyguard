import {ActionButton} from './ui/action-button'
// Gitvextor的原型：连接用户自己的 Agent，授权先于读取。
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useDemo } from '../context/DemoContext'
import {appendAllowedFolder, agentMcpConfig, connectionDetail, connectionStage, launchHarnessCommand} from '../agentConnection'
import type {AgentConnection, AgentProgress, HarnessSetup} from '../agentConnection'
import {PrivateGithub} from './PrivateGithub'
import {GithubSources} from './GithubSources'
import {agentUi as api} from '../api/agent'
import {authorizationIssues,authorizationRequirements} from '../githubGuide'
import {HarnessSetupGuide} from './HarnessSetupGuide'
import {GithubGuideTip} from './GithubGuideTip'
import {githubGuideSteps, githubGuideBlocker} from '../githubGuide'
import {addDiscoveredProject} from '../resume/draftSelection'
type Card = { id: string; quote: string; state: string; page: number | null; line: number; source: {path:string;version:string;commit_sha?:string}; interpretation:string; experience?:string; missing:string[]; numeric_confirmation_required:boolean; approved_for_agent?:boolean }
type DisclosurePreview={id:string;cards:Card[]}
type Conflict={left_id:string;right_id:string;left_quote:string;right_quote:string;left_source:{path:string};right_source:{path:string};reason:string}
type SavedConnection={connection:AgentConnection;task:string;purpose:string;disclosure:string;discoveryJob?:string;suggestions?:Record<string,{title:string;description:string;reason:string}>}
let savedConnection:SavedConnection|null=null
let closeListener:(()=>void)|null=null
function rememberConnection(saved:SavedConnection){
  if(savedConnection?.connection.id===saved.connection.id){savedConnection=saved;return}
  if(closeListener)window.removeEventListener('pagehide',closeListener)
  savedConnection=saved
  closeListener=()=>{const connection=saved.connection;void fetch('/api/v1/agent/ui',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-ApplyGuard-UI':'1'},body:JSON.stringify({...connection,action:'revoke'})}).catch(()=>{});savedConnection=null}
  window.addEventListener('pagehide',closeListener)
}
export function AgentConnector({ensureWorkspace,onImported,inlineDiscovery=false}:{ensureWorkspace:()=>Promise<string|null>;onImported:(id:string)=>Promise<void>;inlineDiscovery?:boolean}) {
  const restored=savedConnection&&savedConnection.connection.expires*1000>Date.now()?savedConnection:null
  const routeLocation = useLocation()
  const { jdRawInput, workflow, resumeForm, setResumeForm, patchWorkflow } = useDemo()
  const job = jdRawInput || workflow?.parsed_jd.source_text || ''
  const connectorRoot=useRef<HTMLElement|null>(null)
  const [githubStep,setGithubStep]=useState(-1)
  const [githubHandle,setGithubHandle]=useState('')
  const [sourceBusy,setSourceBusy]=useState(false)
  const [open,setOpen]=useState(inlineDiscovery||!!restored),[mode,setMode]=useState('local'),[roots,setRoots]=useState(()=>{try{return sessionStorage.getItem('applyguard.agent.lastFolders')||''}catch{return ''}}),[repos,setRepos]=useState('')
  const defaultTask='查找与简历经历和目标岗位有关的材料，重点寻找本人职责、技术和成果的依据。'
  const [task,setTask]=useState(restored?.task||defaultTask)
  const [plan,setPlan]=useState('查找相关项目及背景；查找个人职责；查找使用的方法；查找成果、测试和可能的更正。')
  const [workers,setWorkers]=useState(3)
  const [privateTerms,setPrivateTerms]=useState('')
  const [reviewDisclosures,setReviewDisclosures]=useState(true)
  const [disclosurePreview,setDisclosurePreview]=useState<DisclosurePreview|null>(null)
  const [conflicts,setConflicts]=useState<Conflict[]>([])
  const [approvedPreview,setApprovedPreview]=useState<Record<string,boolean>>({})
  const previewId=useRef<string|null>(null)
  const [purpose,setPurpose]=useState(restored?.purpose||'contribution'),[disclosure,setDisclosure]=useState(restored?.disclosure||''),[privateRepo,setPrivate]=useState(false)
  const [connection,setConnection]=useState<AgentConnection|null>(restored?.connection||null),[connected,setConnected]=useState(false),[cards,setCards]=useState<Card[]>([])
  const [setup,setSetup]=useState<HarnessSetup|null>(null),[setupBusy,setSetupBusy]=useState(false),[setupError,setSetupError]=useState('')
  const [clock,setClock]=useState(()=>Date.now())
  const [progress,setProgress]=useState<AgentProgress|null>(null)
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const [sourceConfirmed,setSourceConfirmed]=useState<Record<string,boolean>>({}),[numbers,setNumbers]=useState<Record<string,boolean>>({})
  const [discoveryJob,setDiscoveryJob]=useState(restored?.discoveryJob||'')
  const [experienceSuggestions, setExperienceSuggestions] = useState<Record<string,{title:string;description:string;reason:string}>>(restored?.discoveryJob===job?restored?.suggestions??{}:{})
  const [folderBusy,setFolderBusy]=useState(false),[folderError,setFolderError]=useState('')
  const pickingFolder=useRef(false), pickerId=useRef<string|null>(null)
  const folders=roots.split('\n').map(path=>path.trim()).filter(Boolean)
  const steps=githubGuideSteps(privateRepo)
  useEffect(()=>{
    if(!open || task!==defaultTask)return
    const titles=[...(resumeForm?.projects??[]).map(item=>item.title),...(resumeForm?.internships??[]).map(item=>item.organization)].filter(Boolean).slice(0,12).join('、')
    if(titles||job)setTask(`${defaultTask}${titles?'\n简历经历：'+titles.slice(0,600):''}${job?'\n目标岗位：'+job.slice(0,800):''}`)
  },[open,task,resumeForm,job])
  const guideTarget=steps[githubStep]?.target
  useEffect(()=>{
    if((!inlineDiscovery && new URLSearchParams(routeLocation.search).get('find_experiences') !== '1') || !job) return
    setOpen(true)
    const known = (resumeForm?.projects ?? []).map(project=>project.title.trim()).filter(Boolean).slice(0,20).join('、').slice(0,400)
    setTask(`根据以下目标岗位查找我可能参与但尚未整理进经历库的项目。返回原文、来源版本和待确认的个人分工。\n已有项目：${known||'无'}\n岗位：${job.slice(0, 1400)}`)
  },[routeLocation.search,job,inlineDiscovery])
  const guideBlocker=sourceBusy?'正在处理仓库请求，请稍候。':githubGuideBlocker(guideTarget,{repos,credentialConfigured:!!githubHandle,disclosure})
  const authorizedSetup=setup?{...setup,github_token_configured:!!githubHandle}:setup
  const issues=authorizationIssues({mode,folders:folders.length,repos,task,disclosure,setup:authorizedSetup,privateRepo})
  const requirements=authorizationRequirements({mode,folders:folders.length,repos,task,disclosure,setup:authorizedSetup,privateRepo})
  function targetProps(target:string) {
    return {'data-github-target':target,tabIndex:-1,className:'github-guide-target'+(guideTarget===target?' is-guided':'')}
  }
  function guideTip(target:string) {
    return <GithubGuideTip privateRepo={privateRepo} step={githubStep} target={target} blocker={guideBlocker}
      onBack={()=>setGithubStep(step=>Math.max(0,step-1))} onNext={()=>setGithubStep(step=>Math.min(steps.length-1,step+1))} onClose={()=>setGithubStep(-1)} />
  }
  useEffect(()=>{
    const target=guideTarget
    if(!target||!open)return
    const frame=requestAnimationFrame(()=>{
      const item=connectorRoot.current?.querySelector<HTMLElement>(`[data-github-target="${target}"]`)
      item?.scrollIntoView({block:'center',behavior:'auto'});item?.focus({preventScroll:true})
    })
    return ()=>cancelAnimationFrame(frame)
  },[guideTarget,open])
  useEffect(()=>()=>{
    const id=pickerId.current
    pickerId.current=null
    if(id)void fetch('/api/v1/agent/ui',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-ApplyGuard-UI':'1'},body:JSON.stringify({action:'cancel_folder',picker_id:id})}).catch(()=>{})
  },[])
  async function selectFolder() {
    if(pickingFolder.current)return
    pickingFolder.current=true;setFolderBusy(true);setFolderError('')
    let id:string|null=null
    try {
      const started=await api({action:'pick_folder'})
      if(typeof started.picker_id!=='string')throw new Error('目录选择接口尚未更新，请重启后端。')
      id=started.picker_id;pickerId.current=id
      while(pickerId.current===id) {
        const selected=await api({action:'folder_status',picker_id:id})
        if(selected.state==='selected' && typeof selected.path==='string') {
          setRoots(current=>appendAllowedFolder(current,selected.path));break
        }
        if(selected.state==='cancelled')break
        if(selected.state==='error')throw new Error(selected.message||'选择失败，请重试。')
        await new Promise(resolve=>setTimeout(resolve,500))
      }
    } catch(e) {
      setFolderError(e instanceof DOMException && e.name==='TimeoutError'?'本机服务未响应，请取消后重试。':e instanceof Error?e.message:'未能选择文件夹，请重试。')
      if(id)void api({action:'cancel_folder',picker_id:id}).catch(()=>{})
    } finally {pickerId.current=null;pickingFolder.current=false;setFolderBusy(false)}
  }
  async function cancelFolder() {
    if(!pickerId.current)return
    try {await api({action:'cancel_folder',picker_id:pickerId.current})}
    catch {setFolderError('取消未完成，请关闭系统选择窗口后重试。')}
  }
  const activeConnection=useRef<string|null>(connection?.id||null)
  function updateDisclosurePreview(preview:DisclosurePreview|null) {
    if(preview?.id!==previewId.current) { previewId.current=preview?.id||null; setApprovedPreview({}) }
    setDisclosurePreview(preview)
  }
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
        if (!cancelled && activeConnection.current===connection.id) {setCards(status.cards);setConnected(status.connected);setProgress(status.progress??null);setConflicts(status.conflicts??[]);updateDisclosurePreview(status.disclosure_preview??null)}
      } catch(e) {
        if (!cancelled && activeConnection.current===connection.id) {setConnected(false);setError(e instanceof Error?e.message:'连接状态更新失败')}
      } finally {pending=false}
    }
    void poll()
    const interval=window.setInterval(()=>void poll(),3000)
    return ()=>{cancelled=true;window.clearInterval(interval)}
  },[connection])
  useEffect(()=>{
    if(connection)rememberConnection({connection,task,purpose,disclosure,discoveryJob,suggestions:experienceSuggestions})
  },[connection,task,purpose,disclosure,discoveryJob,experienceSuggestions])

  const autoSummarized=useRef(new Set<string>())
  const mounted=useRef(true)
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[])
  const cardSignature=cards.map(card=>`${card.id}:${card.state}`).join('|')
  useEffect(()=>{
    if(!inlineDiscovery||!connection||!connected||!job||discoveryJob!==job||disclosure!=='cloud_allowed'||progress?.run_state!=='finished')return
    const selected:Card[]=[]
    for(const card of [...cards.filter(item=>item.state==='NEEDS_REVIEW'),...cards.filter(item=>item.state==='CANDIDATE')]) {
      if(card.approved_for_agent===false)continue
      if(autoSummarized.current.has(card.source.path))continue
      autoSummarized.current.add(card.source.path);selected.push(card)
      if(selected.length===3)break
    }
    if(!selected.length)return
    setNotice('正在根据候选原文生成可编辑概括，最多处理三个来源。')
    void (async()=>{
      for(const card of selected){
        if(!mounted.current)break
        try {
          const value=await api({...connection,action:'suggest_experience',card_id:card.id,job},120000)
          if(mounted.current&&activeConnection.current===connection.id)setExperienceSuggestions(prev=>({...prev,[card.id]:{title:value.title,description:value.description,reason:value.reason}}))
        } catch(e) {autoSummarized.current.delete(card.source.path);if(mounted.current)setError(e instanceof Error?`自动概括未完成：${e.message}`:'自动概括未完成，可手动重试。')}
      }
      if(mounted.current)setNotice('候选概括已处理；请核对来源和个人分工，再决定是否加入草稿。')
    })()
  },[inlineDiscovery,connection,connected,job,discoveryJob,disclosure,progress?.run_state,cardSignature])
  async function discoverAgain() {
    if(!connection)return
    await api({...connection,action:'discover_experiences',job,
      known_projects:(resumeForm?.projects??[]).map(project=>project.title)})
    autoSummarized.current.clear();setDiscoveryJob(job);setExperienceSuggestions({});setCards([])
    setSourceConfirmed({});setNumbers({});setProgress({stage:'waiting',updated_at:Date.now()/1000,run_state:'started',candidates:0,submitted:0})
    setNotice('已按当前岗位重新查找；沿用本次授权范围，完成后会在这里生成概括。')
  }
  function addExperience(card:Card) {
    try {
      if(!resumeForm)throw Error('请先导入简历建立个人经历资料。')
      const suggestion=experienceSuggestions[card.id]
      const next=addDiscoveredProject(workflow,resumeForm,`agent-${card.id}`,suggestion.title,suggestion.description,inlineDiscovery)
      setResumeForm(next.form)
      if(inlineDiscovery&&next.workflow)patchWorkflow(next.workflow)
      setExperienceSuggestions(prev=>{const value={...prev};delete value[card.id];return value})
      setError('');setNotice(inlineDiscovery?'已加入本次简历草稿；当前页无需重新分析或跳转，后续可继续编辑和核验。':'已加入经历草稿，后续可编辑并保存。')
    } catch(e) {setError(e instanceof Error?e.message:'加入草稿失败，请重试。')}
  }
  async function run(fn:()=>Promise<void>) {setBusy(true);setError('');try{await fn()}catch(e){setError(e instanceof Error?e.message:'操作失败')}finally{setBusy(false)}}
  async function changeGithubScope(nextPrivate:boolean) {
    if(nextPrivate===privateRepo)return
    if(githubHandle)await api({action:'github_app_revoke',handle:githubHandle})
    setGithubHandle('');setRepos('');setDisclosure('');setPrivate(nextPrivate)
    setGithubStep(step=>step<0?-1:0)
  }
  async function revoke() {
    if(!connection)return
    try{await api({...connection,action:'revoke'});activeConnection.current=null;savedConnection=null;if(closeListener)window.removeEventListener('pagehide',closeListener);closeListener=null;setConnection(null);setConnected(false);setCards([]);setProgress(null);updateDisclosurePreview(null);setGithubStep(-1);setSourceConfirmed({});setNumbers({});setNotice('连接已撤销；重新授权后才能继续读取。');setError('')}
    catch(e){setError(e instanceof Error?e.message:'撤销未成功，请重试')}
  }
  async function copyText(text:string, label:string) {
    try {await navigator.clipboard.writeText(text);setNotice(`${label}已复制。`)}
    catch {setError('无法访问剪贴板，请展开配置后手动复制。')}
  }
  const config=connection&&setup?agentMcpConfig(setup,connection,location.origin):null
  const expired=!!connection&&clock>=connection.expires*1000
  const launch=connection&&setup?launchHarnessCommand(setup,connection,location.origin):''
  const shell=setup?.shell==='posix'?'终端':'PowerShell'
  return <section className="agent-connector" ref={connectorRoot}>
    <button type="button" className="btn secondary" aria-expanded={open} onClick={()=>setOpen(!open)}>连接 DeepSeek Harness / 其他 Agent</button>
    {connection&&!open&&<button className="btn secondary" onClick={()=>void revoke()}>撤销 Agent 连接</button>}
    {(open || privateRepo) && <div className="agent-connector-body" hidden={!open}>
      <div className="harness-setup-target"><HarnessSetupGuide setup={setup} loading={setupBusy} error={setupError} onRefresh={()=>void detectSetup()} /></div>
      <h3 className="agent-section-heading">授权查找材料</h3><p>连接须由你授权，可随时撤销，最多30分钟有效。站内切页会保留本次会话；关闭窗口或主动撤销后停止。候选依据由你核对后导入。</p>
      {!connection ? <>
        <div className="github-guide-entry"><ActionButton type="button" className="btn secondary" disabledReason="请等待当前操作完成。" disabled={busy||folderBusy||sourceBusy} onClick={()=>void run(async()=>{await changeGithubScope(false);setMode('github');setGithubStep(0)})}>从 GitHub 查找公开仓库</ActionButton><p>支持用户名、公开邮箱或项目关键词。</p></div>
        <label className="agent-task">查找需求<textarea className="resume-input" value={task} onChange={e=>setTask(e.target.value)} /></label>
        <label>查找计划（可修改）<textarea className="resume-input" maxLength={1200} value={plan} onChange={e=>setPlan(e.target.value)} /></label>
        <label>并行查找任务<select className="resume-input" value={workers} onChange={e=>setWorkers(Number(e.target.value))}><option value={1}>1 个任务</option><option value={3}>3 个任务：职责、方法、结果</option></select></label>
        <p className="muted">并行任务会增加模型调用和费用，共享授权范围、外发预览和最多 12 次搜索。</p>
        <label>搜索范围<select className="resume-input" value={mode} disabled={busy||folderBusy||sourceBusy} onChange={e=>{const next=e.target.value;void run(async()=>{if(next==='local'){await changeGithubScope(false);setGithubStep(-1)}setMode(next);setDisclosure('')})}}><option value="local">本地材料</option><option value="github">GitHub</option><option value="auto">自动选择已授权来源</option></select></label>
        {mode!=='github' && <fieldset className="agent-folder-picker"><legend>允许访问的文件夹</legend>
          <ActionButton type="button" className="btn secondary" disabledReason={folderBusy?'请先完成或取消文件夹选择。':busy?'正在处理，请稍候。':'已选满五个文件夹；移除一个后可继续添加。'} disabled={folderBusy||busy||folders.length>=5} onClick={()=>void selectFolder()}>
            {folderBusy?'正在选择文件夹…':folders.length?'继续添加文件夹':'选择文件夹'}
          </ActionButton>
          {folderBusy&&<><button type="button" className="btn secondary" onClick={()=>void cancelFolder()}>取消选择</button><p role="status">系统选择窗口将打开；如果没有看到窗口，可以取消后重新选择。</p></>}
          <p className="muted">可连续选择，最多 5 个。请选择具体子文件夹，不能选择整个磁盘；选择后仍需点击下方按钮授权。 支持 PDF、Word、文本和代码；压缩包先解压，超过 40 页的 PDF 先拆出相关页。图片证书请上传材料库做本地 OCR。</p>
          {folders.length ? <ul className="agent-folder-list">{folders.map((path,index)=><li key={`${path}:${index}`}><code>{path}</code>
            <ActionButton type="button" className="btn secondary" disabledReason={folderBusy?'请先完成或取消文件夹选择。':'正在处理，请稍候。'} disabled={folderBusy||busy} aria-label={`移除文件夹 ${path}`} onClick={()=>setRoots(folders.filter((_,i)=>i!==index).join('\n'))}>移除</ActionButton>
          </li>)}</ul>:<p className="muted">尚未选择文件夹。</p>}
          {folderError&&<p className="callout warn" role="alert">{folderError}</p>}
          <details><summary>手动输入路径（备用）</summary><label>允许访问的文件夹（绝对路径，每行一个）
            <textarea className="resume-input" disabled={folderBusy||busy} value={roots} onChange={e=>{setRoots(e.target.value);setFolderError('')}} placeholder="例如 E:\项目材料\数据分析" />
          </label></details>
        </fieldset>}
        {mode!=='local' && <>
          <label>仓库范围<select className="resume-input" value={privateRepo?'private':'public'} disabled={busy||sourceBusy} onChange={e=>{const wantsPrivate=e.target.value==='private';void run(()=>changeGithubScope(wantsPrivate))}}>
            <option value="public">查找公开仓库</option><option value="private">使用私有仓库（需要授权）</option></select></label>
          {privateRepo ? <div {...targetProps('private')}>
            <PrivateGithub onPending={setSourceBusy} onGrant={h=>{setGithubHandle(h);if(!h){setRepos('');setDisclosure('')}}} onPin={spec=>{setDisclosure('');setRepos(prev=>[...new Set([...prev.split('\n').filter(Boolean),spec])].slice(0,5).join('\n'))}}/>
            {repos && <p>本次已指定：{repos.split('\n').map(spec=>spec.split('@')[0]).join('、')}</p>}
            {guideTip('private')}</div> : <div {...targetProps('repositories')}>
            <GithubSources onPending={setSourceBusy} value={repos} onChange={value=>{setRepos(value);setDisclosure('')}}/>{guideTip('repositories')}</div>}
        </>}
        <label>查找目的<select className="resume-input" value={purpose} onChange={e=>setPurpose(e.target.value)}><option value="contribution">寻找本人贡献依据</option><option value="background">查技术背景（不可导入为个人经历）</option></select></label>
        <div {...targetProps('disclosure')}><fieldset><legend>读取前确定材料外发规则</legend><label><input type="radio" name="agent-disclosure" value="cloud_allowed" checked={disclosure==='cloud_allowed'} onChange={e=>setDisclosure(e.target.value)} />允许片段进入我配置的云端模型上下文</label><label><input type="radio" name="agent-disclosure" value="isolated_local" checked={disclosure==='isolated_local'} onChange={e=>setDisclosure(e.target.value)} />我已配置隔离的本地模型，禁止外发</label></fieldset><p className="muted">连接器会尝试在本机替换常见手机号、邮箱和 18 位身份证号；姓名、公司及其他隐私仍可能发送，请核对授权范围。</p>{guideTip('disclosure')}</div>
        <label>额外需要替换的姓名、公司或其他敏感词（每行一项，仅在本次连接中使用）<textarea className="resume-input" value={privateTerms} onChange={e=>setPrivateTerms(e.target.value)} /></label>
        {setup?.privacy_ner&&<p className="muted">{setup.privacy_ner.notice}</p>}
        <p className="muted">敏感词按原文精确匹配，无法自动识别别名或所有个人信息。</p>
        <label><input type="checkbox" checked={reviewDisclosures} onChange={e=>setReviewDisclosures(e.target.checked)} />发送每批检索片段前由我选择允许发送的内容</label>
        <p className="muted">查找需求和计划将在启动后发送给 Agent，检索片段可逐批预览；其他功能的模型调用不由此预览控制。</p>
        <p>本接口只能约束自己的工具。请使用仅启用此连接器的检索配置；Agent 自带的 shell 等其他工具不受这里的目录授权限制。</p>
        <div {...targetProps('authorize')}><ActionButton className="btn primary" disabledReason={folderBusy?'请先完成或取消文件夹选择。':sourceBusy?'正在处理仓库请求，请稍候。':issues.length?issues.join('；'):'正在处理，请稍候。'} guideRequirements={busy||folderBusy||sourceBusy?[]:requirements} disabled={busy||folderBusy||(mode!=='local'&&sourceBusy)||issues.length>0} aria-describedby="agent-authorization-issues" onClick={()=>void run(async()=>{if(sourceBusy&&mode!=='local')throw new Error('正在固定 GitHub 仓库版本，请稍候。');if(issues.length){throw new Error(issues.join('；'))}const c=await api({action:'create',mode,task,plan,workers,private_terms:privateTerms.split('\n').map(s=>s.trim()).filter(Boolean),review_disclosures:reviewDisclosures,purpose,disclosure,private:mode!=='local'&&privateRepo,github_handle:mode!=='local'&&privateRepo?githubHandle:undefined,roots:mode==='github'?[]:roots.split('\n').map(s=>s.trim()).filter(Boolean),repos:mode==='local'?[]:repos.split('\n').map(s=>s.trim()).filter(Boolean)});try{if(mode!=='github')sessionStorage.setItem('applyguard.agent.lastFolders',roots)}catch{/* Optional convenience only. */}activeConnection.current=c.id;setConnection(c);if(inlineDiscovery)setDiscoveryJob(job);setGithubStep(step=>step<0?-1:steps.length-1);setClock(Date.now());setCards([]);setConnected(false);setProgress(null);setNotice('');setSourceConfirmed({});setNumbers({});if(disclosure==='cloud_allowed'){await api({...c,action:'start_harness'});setNotice('已启动 Harness，正在查找已授权范围内的材料。')}})}>{disclosure==='isolated_local'?'授权并生成手动配置':'授权并开始查找'}</ActionButton><div id="agent-authorization-issues" role="status">{issues.length>0&&<><p>继续前请完成：</p><ul>{issues.map(issue=><li key={issue}>{issue}</li>)}</ul></>}{folderBusy&&<p>请先完成或取消文件夹选择。</p>}{busy&&<p>正在处理，请稍候…</p>}</div>{guideTip('authorize')}</div>
      </> : <>
        <div className={`harness-status ${connected&&progress?.run_state!=='failed'&&progress?.run_state!=='timed_out'?'paired':''}`} role="status"><strong>{connectionStage(connection,connected,clock,progress)}</strong><span>{new Date(connection.expires*1000).toLocaleTimeString()} 到期 · 每 3 秒自动刷新</span></div>
        {expired?<p className="harness-warning">本次授权已过期。请撤销后重新授权，并使用新的命令与令牌。</p>:<div className="harness-launch">
          <h4>本机 Harness 检索</h4><p className="muted">会话最多 {setup?.session_timeout_seconds??180} 秒。站内切页后可返回查看；候选原文需要你核对后导入。</p>
          {disclosure==='cloud_allowed'?<>
            <div className="button-row"><ActionButton className="btn primary" disabled={busy||progress?.run_state==='started'} disabledReason="Harness 正在检索，请稍候。" onClick={()=>void run(inlineDiscovery?discoverAgain:async()=>{await api({...connection,action:'start_harness'});setNotice('已重新启动 Harness，请稍候。')})}>{inlineDiscovery?'按当前岗位再次查找并生成概括':'重新开始查找'}</ActionButton></div>
            <details><summary>手动连接（备用）</summary><ol><li>复制启动命令，在本机 {shell} 中执行。它会启动独立的 Harness 检索会话。</li>
              <li>终端询问时，粘贴“临时连接令牌”，然后输入模型 API Key。两次输入都隐藏，不写入配置文件。</li>
              <li>Harness 调用 <code>get_task → search_materials → submit_evidence</code> 后，这里会自动更新配对状态与候选证据。</li></ol>
            <div {...targetProps('launch')}><div className="button-row"><ActionButton className="btn primary" disabledReason={'请先完成 Harness 安装并重新检测环境。'} disabled={!setup?.harness_command||!launch} onClick={()=>void copyText(launch,'启动命令')}>复制 {shell} 启动命令</ActionButton>
              <button className="btn secondary" onClick={()=>void copyText(connection.token,'临时连接令牌')}>复制临时连接令牌</button></div>{guideTip('launch')}</div>
            {!setup?.harness_command&&<p className="harness-warning">请先完成上方 Harness 安装步骤，或用下方手动配置接入现有 MCP 客户端。</p>}
            <details><summary>查看启动命令（不含密钥）</summary><pre>{launch}</pre></details></details>
          </>:<p>你选择了隔离本地模型。请使用下方手动 MCP 配置接入已隔离的 Harness profile；云端 Gemini 快捷启动不适用于本次授权。</p>}
        </div>}
        <div {...(disclosure==='isolated_local'?targetProps('launch'):{})}><details className="harness-manual"><summary>手动配置 / 其他 MCP 客户端（含临时凭据）</summary>
          <p>Python 与脚本已填入本机实际路径。通用 JSON 可用于支持 mcpServers 的客户端；Harness 使用 YAML patch，并通过进程环境提供临时 URL、ID 和 TOKEN。重新授权后需更新这些值。</p>
          <h4>通用 MCP JSON</h4><pre data-testid="agent-mcp-config">{JSON.stringify(config,null,2)}</pre>
          <h4>Harness MCP YAML patch</h4><pre>{setup?.mcp_patch}</pre><p>此片段只接入 MCP，不替你配置隔离模型或禁用其他工具。快捷启动使用的是专门的检索配置。</p>
        </details>{disclosure==='isolated_local'&&guideTip('launch')}</div>
        <div className="button-row"><ActionButton className="btn secondary" disabledReason={expired?'授权已过期，请撤销后重新授权。':'正在刷新，请稍候。'} disabled={busy||expired} onClick={()=>void run(async()=>{const s=await api({...connection,action:'status'});if(activeConnection.current!==connection.id)return;setCards(s.cards);setConnected(s.connected);setProgress(s.progress??null)})}>刷新配对与候选证据</ActionButton><button className="btn secondary" onClick={()=>void revoke()}>撤销连接</button></div>
      </>}
      {connection&&connectionDetail(progress,clock)&&<p role="status" className={progress?.run_state==='failed'||progress?.run_state==='timed_out'?'harness-warning':'muted'}>{connectionDetail(progress,clock)}</p>}
      {connection&&!!progress?.search_rounds&&<p className="muted">本次已发起 {progress.search_rounds} 轮材料搜索（最多 12 轮）。结果仍需核对来源和归属。</p>}
      {connection&&!!progress?.workers&&<p className="muted">并行查找已结束 {progress.workers_finished??0} / {progress.workers} 个任务。</p>}
      {connection&&progress?.conflict_state==='running'&&<p className="muted">正在对已允许外发的候选材料进行冲突复核。</p>}
      {connection&&progress?.conflict_state==='insufficient'&&<p className="muted">没有足够可用的候选材料，未执行冲突复核。</p>}
      {connection&&progress?.conflict_state==='failed'&&<p className="harness-warning">冲突复核未完成，请手动核对候选原文。</p>}
      {connection&&progress?.conflict_state==='stale'&&<p className="harness-warning">材料在冲突复核期间发生变化，请重新查找。</p>}
      {connection&&progress?.conflict_state==='finished'&&!conflicts.length&&<p className="muted">最多复核 6 条已允许外发的候选；没有可定位的冲突提示，不代表材料一定没有冲突。</p>}
      {connection&&conflicts.map((item,index)=><section className="callout" key={`${item.left_id}-${item.right_id}`}><h4>可能存在冲突 {index+1}，请核对原件</h4><p>{item.left_source.path}</p><blockquote>{item.left_quote}</blockquote><p>{item.right_source.path}</p><blockquote>{item.right_quote}</blockquote><p>{item.reason}</p></section>)}
      {connection&&disclosurePreview&&<section className="callout" aria-label="外发片段预览">
        <h4>选择本批允许发送给 Agent 的片段</h4>
        <p>以下是本机替换后的内容，未勾选的不发送；可能仍有未识别隐私。请在约 55 秒内确认，超时则不发送本批。</p>
        {disclosurePreview.cards.map(card=><label key={card.id}><input type="checkbox" checked={!!approvedPreview[card.id]} onChange={e=>setApprovedPreview({...approvedPreview,[card.id]:e.target.checked})} />{card.source.path}<blockquote>{card.quote}</blockquote></label>)}
        <ActionButton className="btn primary" disabled={busy} disabledReason="正在处理，请稍候。" onClick={()=>void run(async()=>{await api({...connection,action:'review_disclosure',preview_id:disclosurePreview.id,card_ids:disclosurePreview.cards.filter(card=>approvedPreview[card.id]).map(card=>card.id)});updateDisclosurePreview(null);setNotice('已提交本批选择，未选片段不会发送。')})}>确认本批选择</ActionButton>
      </section>}
      {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
      {connected&&!cards.length&&<p>尚无候选证据。请让 Agent 调用搜索并回传引用，再刷新。</p>}
      {cards.map(c=><article className="agent-evidence" key={c.id}><h4>{c.source.path} · {c.state==='IMPORTED'?'已导入，待陈述核验':'待确认草稿'}</h4><p>{c.page?`第 ${c.page} 页`:`第 ${c.line} 行/段`} · 版本 {c.source.commit_sha||c.source.version}</p><blockquote>{c.quote}</blockquote><p>关联经历：{c.experience||'待指定'}</p><p>Agent 候选解释：{c.interpretation||'尚未回传解释'}</p><p>仍缺信息：{c.missing.join('；')||'仍需核对本人归属及支持关系'}</p>
        {job && purpose==='contribution' && (['CANDIDATE','NEEDS_REVIEW','IMPORTED'].includes(c.state)) && <div className="callout">
          <h4>按当前岗位整理遗漏经历</h4>
          <p>依据上方原文生成项目描述，个人分工和事实仍由你核对。生成时将岗位与这段材料发送给已配置的云端模型。</p>
          <ActionButton className="btn secondary" disabled={busy||disclosure!=='cloud_allowed'||c.approved_for_agent===false} disabledReason={c.approved_for_agent===false?'该片段未通过本次外发预览。':'请先允许材料片段进入云端模型。'} onClick={()=>void run(async()=>{
            const value=await api({...connection,action:'suggest_experience',card_id:c.id,job},120000)
            setExperienceSuggestions(prev=>({...prev,[c.id]:{title:value.title,description:value.description,reason:value.reason}}))
          })}>生成可编辑的经历建议</ActionButton>
          {experienceSuggestions[c.id] && <>
            <p>关联原因：{experienceSuggestions[c.id].reason}</p>
            <label>项目名称<input className="resume-input" value={experienceSuggestions[c.id].title} onChange={e=>setExperienceSuggestions(prev=>({...prev,[c.id]:{...prev[c.id],title:e.target.value}}))}/></label>
            <label>项目描述<textarea className="resume-input" value={experienceSuggestions[c.id].description} onChange={e=>setExperienceSuggestions(prev=>({...prev,[c.id]:{...prev[c.id],description:e.target.value}}))}/></label>
            <button className="btn secondary" onClick={()=>addExperience(c)}>{inlineDiscovery?'加入本次简历草稿':'加入经历库草稿'}</button>{' '}
            <button className="btn secondary" onClick={()=>setExperienceSuggestions(prev=>{const next={...prev};delete next[c.id];return next})}>不要这条</button>{' '}{!inlineDiscovery&&<Link to="/vault">前往经历库</Link>}
          </>}
        </div>}
        <label><input type="checkbox" checked={!!sourceConfirmed[c.id]} onChange={e=>setSourceConfirmed({...sourceConfirmed,[c.id]:e.target.checked})} />我已核对原文及本人归属</label>
        {c.numeric_confirmation_required&&<label><input type="checkbox" checked={!!numbers[c.id]} onChange={e=>setNumbers({...numbers,[c.id]:e.target.checked})} />我已逐项核对数字、单位及适用范围</label>}
        <p className="muted">{c.state==='IMPORTED'?'此片段已导入。':purpose==='background'?'技术背景不能导入为个人经历。':!['CANDIDATE','NEEDS_REVIEW'].includes(c.state)?'当前片段暂不可导入。':!sourceConfirmed[c.id]?'请先核对原文及本人归属。':c.numeric_confirmation_required&&!numbers[c.id]?'请逐项核对数字、单位与范围。':''}</p><ActionButton className="btn secondary" disabledReason={busy?'正在处理，请稍候。':c.state==='IMPORTED'?'此片段已导入。':purpose==='background'?'技术背景不能导入为个人经历。':!['CANDIDATE','NEEDS_REVIEW'].includes(c.state)?'当前片段暂不可导入。':!sourceConfirmed[c.id]?'请先核对原文和本人归属。':'请先核对数字、单位和范围。'} disabled={busy||!['CANDIDATE','NEEDS_REVIEW'].includes(c.state)||!sourceConfirmed[c.id]||(c.numeric_confirmation_required&&!numbers[c.id])||purpose==='background'} onClick={()=>void run(async()=>{const id=connection?.id;const ws=await ensureWorkspace();if(activeConnection.current!==id)return;if(!ws)throw new Error('请先建立材料工作区');await api({...connection,action:'accept',card_id:c.id,workspace_id:ws,confirm_source:sourceConfirmed[c.id],confirm_numbers:!!numbers[c.id]});await onImported(ws);if(activeConnection.current!==id)return;const s=await api({...connection,action:'status'});if(activeConnection.current!==id)return;setCards(s.cards);setNotice('原文片段已导入，陈述仍须经过事实核验；未自动改写简历。')})}>确认来源并导入片段</ActionButton>
      </article>)}
    </div>}
  </section>
}
