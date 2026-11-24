import {ActionButton} from './ui/action-button'
import {useRef,useState} from 'react'
import {agentUi} from '../api/agent'

type Repository={repo:string;url:string;description:string;branch:string;updated_at?:string;archived:boolean}
type Account={login:string;url:string}
type Results={items:Repository[];accounts:Account[];page:number;has_more:boolean;notice:string;listing?:string}

export function GithubSources({value,onChange,onPending}:{value:string;onChange:(value:string)=>void;onPending:(pending:boolean)=>void}) {
  const [query,setQuery]=useState(''),[kind,setKind]=useState('auto')
  const [result,setResult]=useState<Results|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [email,setEmail]=useState('')
  const [pendingRepo,setPendingRepo]=useState('')
  const current=useRef({query:'',kind:'auto'})
  const specs=value.split('\n').map(row=>row.trim()).filter(Boolean)
  async function search(append=false,account?:string) {
    setBusy(true);setError('')
    const request=append?current.current:{query:account??query,kind:account?'username':kind,email:account?'':email}
    if(!append){current.current=request;setResult(null)}
    try {
      const data:Results=await agentUi({action:'github_discover',...request,listing:append?result?.listing:undefined,page:append?(result?.page??1)+1:1})
      setResult(previous=>append&&previous?{...data,items:[...previous.items,...data.items],accounts:[...previous.accounts,...data.accounts]}:data)
    } catch(reason){setError(reason instanceof Error?reason.message:'查找失败，请重试。')}
    finally{setBusy(false)}
  }
  async function choose(item:Repository) {
    const existing=specs.find(spec=>spec.split('@')[0].toLowerCase()===item.repo.toLowerCase())
    if(existing){onChange(specs.filter(spec=>spec!==existing).join('\n'));return}
    if(specs.length>=5){setError('最多选择五个仓库，请先移除一个。');return}
    setBusy(true);setPendingRepo(item.repo);onPending(true);setError('')
    try{const pinned=await agentUi({action:'github_pin',repo:item.repo});onChange([...specs,pinned.spec].join('\n'))}
    catch(reason){setError(reason instanceof Error?reason.message:'固定版本失败，请重试。')}
    finally{setBusy(false);setPendingRepo('');onPending(false)}
  }
  return <section aria-label="GitHub 仓库选择">
      <label>用户名、公开邮箱或关键词<input className="resume-input" value={query} disabled={busy} placeholder="用户名" onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();void search()}}} /></label>
      <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={()=>void search()}>{busy?'正在查询 GitHub…':'查找公开仓库'}</ActionButton>
      <details><summary>更多查找方式</summary>
      <label>查找方式<select className="resume-input" value={kind} disabled={busy} onChange={e=>setKind(e.target.value)}><option value="auto">自动识别用户名 / 邮箱 / 仓库</option><option value="username">GitHub 用户名</option><option value="email">公开邮箱</option><option value="keyword">仓库关键词</option></select></label>
      <label>公开邮箱（可选，可与用户名一起核对）<input value={email} type="email" disabled={busy} onChange={e=>setEmail(e.target.value)}/></label>
      </details>
      <p className="muted">公开查询无需登录。找到仓库后，选择要使用的材料来源。</p>
      {result&&<><p role="status">{result.notice}</p>
        <ul className="github-repository-list">{result.accounts.map(account=><li key={account.login}><a href={account.url} target="_blank" rel="noreferrer">{account.login} ↗</a><ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={()=>void search(false,account.login)}>查看该账号的公开仓库</ActionButton></li>)}
          {result.items.map(item=><li key={item.repo}><label><input type="checkbox" disabled={busy} checked={pendingRepo===item.repo||specs.some(spec=>spec.split('@')[0].toLowerCase()===item.repo.toLowerCase())} onChange={()=>void choose(item)} />{item.repo}{pendingRepo===item.repo?'（正在固定版本…）':''}{item.archived?'（已归档）':''}</label><p>{item.description||'暂无简介'}</p><a href={item.url} target="_blank" rel="noreferrer">核对仓库 ↗</a></li>)}</ul>
        {!result.accounts.length&&!result.items.length&&<p>未找到匹配的公开结果，可换用用户名或关键词。</p>}
        {result.has_more&&<ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={()=>void search(true)}>加载更多查询结果</ActionButton>}</>}
      {specs.length>0&&<div><h4>已选仓库（{specs.length} / 5）</h4><ul className="agent-folder-list">{specs.map(spec=><li key={spec}><span>{spec.split('@')[0]}</span><ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={()=>onChange(specs.filter(row=>row!==spec).join('\n'))}>移除 {spec.split('@')[0]}</ActionButton></li>)}</ul><p className="muted">已记录所选版本，确认后才读取仓库文件。</p></div>}
    {error&&<p role="alert" className="callout warn">{error}</p>}
  </section>
}
