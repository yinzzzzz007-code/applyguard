import {useState} from 'react'
import {GithubSources} from './GithubSources'
import {PrivateGithub} from './PrivateGithub'
import {agentUi} from '../api/agent'

export function GithubImport({ensureWorkspace,onImported}:{ensureWorkspace:()=>Promise<string|null>;onImported:(id:string)=>Promise<void>}) {
  const [scope,setScope]=useState<'public'|'private'>('public'),[specs,setSpecs]=useState('')
  const [handle,setHandle]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[pinning,setPinning]=useState(false)
  async function change(value:'public'|'private') {
    setBusy(true)
    try {if(handle)await agentUi({action:'github_app_revoke',handle});setHandle('');setScope(value);setSpecs('');setMessage('')}
    catch{setMessage('断开未完成，请重试。')}finally{setBusy(false)}
  }
  async function read(spec:string){
    if(busy)return
    setBusy(true);setMessage('')
    try{
      const ws=await ensureWorkspace()
      if(!ws)throw Error('请先建立材料库。')
      await agentUi({action:'github_import_readme',workspace_id:ws,spec,handle:scope==='private'?handle:undefined,confirm:true})
      await onImported(ws);setMessage('README 已导入。请在材料库核对原文并关联对应经历。')
    }catch(e){setMessage(e instanceof Error?e.message:'读取失败。')}finally{setBusy(false)}
  }
  return <details className="profile-card"><summary>从 GitHub 选择材料</summary>
    <p>输入用户名、公开邮箱或关键词即可查找公开仓库。</p>
    <fieldset disabled={busy||pinning}><label>访问范围<select value={scope} onChange={e=>void change(e.target.value as typeof scope)}>
      <option value="public">查找公开仓库</option><option value="private">使用私有仓库（需要授权）</option></select></label>
    {scope==='public'?<GithubSources value={specs} onChange={setSpecs} onPending={setPinning}/>:
      <PrivateGithub onPending={setPinning} onGrant={h=>{setHandle(h);if(!h)setSpecs('')}} onPin={setSpecs}/>}
    {specs.split('\n').filter(Boolean).map(spec=><div key={spec}><code>{spec}</code> <button className="btn secondary" onClick={()=>void read(spec)}>确认读取此版本 README</button></div>)}</fieldset>
    <p role="status">{busy?'正在读取所选文件…':message}</p></details>
}
