import {useEffect,useRef,useState} from 'react'
import {agentUi} from '../api/agent'

export function PrivateGithub({onGrant,onPin,onPending}:{onPending:(busy:boolean)=>void;onGrant:(handle:string)=>void;onPin:(spec:string)=>void}) {
  const [device,setDevice]=useState<{handle:string;user_code:string;url:string}|null>(null)
  const [repos,setRepos]=useState<string[]|null>(null),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
  const active=useRef(true), pendingDevice=useRef('')
  useEffect(()=>{
    active.current=true
    return ()=>{
      active.current=false
      if(pendingDevice.current)void agentUi({action:'github_app_revoke',handle:pendingDevice.current}).catch(()=>{})
    }
  },[])
  async function run(action:string,repo?:string) {
    setBusy(true);onPending(true);setMessage('')
    try {
      const data=await agentUi({action,handle:device?.handle,repo})
      if(!active.current) {
        if(action==='github_app_start')void agentUi({action:'github_app_revoke',handle:data.handle}).catch(()=>{})
        return
      }
      if(action==='github_app_start'){pendingDevice.current=data.handle;setDevice(data);setRepos(null)}
      if(action==='github_app_poll') {
        if(data.authorized){pendingDevice.current='';setRepos(data.repos);onGrant(device!.handle);setMessage(data.repos.length?'请从已授权列表中指定本次使用的私有仓库。':'没有可用私库。请在 GitHub 安装设置里选择仓库并授予 Contents 只读权限。')}
        else setMessage('等待你在 GitHub 确认，完成后再检查。')
      }
      if(action==='github_app_pin')onPin(data.spec)
      if(action==='github_app_revoke'){pendingDevice.current='';onGrant('');setDevice(null);setRepos(null);setMessage('已断开本次 GitHub 连接。')}
    } catch(e){setMessage(e instanceof Error?e.message:'GitHub 请求未完成。')} finally{if(active.current){setBusy(false);onPending(false)}}
  }
  return <div><p>私有仓库需要你在 GitHub 官方页面亲自授权。请为 GitHub App 选择指定仓库并授予内容只读权限。回到此处检查授权后，再指定本次使用的仓库。</p>
    {!device?<button className="btn secondary" disabled={busy} onClick={()=>void run('github_app_start')}>在 GitHub 授权私有仓库</button>:<>
      {repos===null&&<p><a href={device.url} target="_blank" rel="noreferrer">打开 GitHub 官方授权页 ↗</a>，输入 <strong>{device.user_code}</strong>。 <button className="btn secondary" disabled={busy} onClick={()=>void run('github_app_poll')}>我已确认，检查授权</button></p>}
      {repos?.map(repo=><button key={repo} className="btn secondary" disabled={busy} onClick={()=>void run('github_app_pin',repo)}>指定 {repo}</button>)}
      <button className="text-action" disabled={busy} onClick={()=>void run('github_app_revoke')}>断开本次授权</button></>}
    <p aria-live="polite">{message}</p></div>
}
