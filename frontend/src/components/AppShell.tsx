import { useEffect, useRef } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import type { DemoScenario } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { zhText } from '../i18n'
import { STEP_META, STEP_ORDER, loadMaxStep, rememberMaxStep, stepFromPath, stepIndex } from '../flow'
import { Icon, type IconName } from './Icon'

const STEP_ICONS: IconName[] = ['upload', 'folder', 'briefcase', 'layers', 'file', 'shield', 'window', 'check']
const TOOLS: { path:string; label:string; icon:IconName }[] = [
  {path:'/jobs',label:'岗位雷达',icon:'compass'},
  {path:'/evidence',label:'证据工作区',icon:'library'},
  {path:'/history',label:'申请历史',icon:'history'},
]
const SCENARIOS: {id:DemoScenario;label:string}[] = [
  {id:'live',label:'连接本地后端'}, {id:'prerecorded_block',label:'预录 · 阻断样例'},
  {id:'prerecorded_fallback',label:'预录 · 回退样例'}, {id:'error',label:'错误重试样例'},
]

export function AppShell({children}:{children:React.ReactNode}) {
  const {scenario,setScenario,step,setStep,dataSourceLabel,workflow} = useDemo()
  const location = useLocation()
  const navigate = useNavigate()
  const drawer = useRef<HTMLDetailsElement>(null)
  const fromPath = stepFromPath(location.pathname)
  const unlocked = Math.max(stepIndex(step),stepIndex(loadMaxStep()),fromPath ? stepIndex(fromPath) : 0,stepIndex('vault'))
  const title = fromPath ? STEP_META[fromPath].label : TOOLS.find(t => t.path === location.pathname)?.label ?? '申请工作台'
  useEffect(() => {
    const target = stepFromPath(location.pathname)
    if (target) {setStep(target);rememberMaxStep(target)}
    if (drawer.current) drawer.current.open = false
    window.scrollTo({top:0,left:0,behavior:'auto'})
  },[location.pathname,setStep])

  function navigation() {
    return <>
      <div className="workspace-scope"><span className="scope-mark">个</span><div><strong>个人工作台</strong><small>本地申请空间</small></div></div>
      <nav className="workspace-nav" aria-label="申请流程">
        <p className="nav-group-label">准备一份申请</p>
        <ol>{STEP_ORDER.map((key,index) => <li key={key}>
          {index <= unlocked ? <NavLink end={key === 'import'} to={STEP_META[key].path} className={({isActive}) => `workspace-nav-item${isActive ? ' is-current' : ''}`}>
            <Icon name={STEP_ICONS[index]} /><span>{STEP_META[key].label}</span>{fromPath === key && <span className="nav-current-dot" />}
          </NavLink> : <span className="workspace-nav-item is-locked" aria-disabled="true" title="完成前面的流程后解锁"><Icon name={STEP_ICONS[index]} /><span>{STEP_META[key].label}</span><Icon name="lock" /></span>}
        </li>)}</ol>
      </nav>
      <nav className="workspace-nav" aria-label="工作台工具"><p className="nav-group-label">资料与记录</p>
        {TOOLS.map(tool => <NavLink key={tool.path} to={tool.path} className={({isActive}) => `workspace-nav-item${isActive ? ' is-current' : ''}`}><Icon name={tool.icon} /><span>{tool.label}</span></NavLink>)}
      </nav>
    </>
  }
  return <div className="workspace-shell">
    <a className="skip-link" href="#workspace-main">跳到主要内容</a>
    <aside className="workspace-sidebar">
      <NavLink to="/" className="workspace-brand" aria-label="ApplyGuard 申请护栏首页"><Icon name="brand" /><span>ApplyGuard<small>申请护栏</small></span></NavLink>
      {navigation()}
      <div className="sidebar-note"><Icon name="shield" /><div><strong>每一条陈述，都有来处</strong><p>原始材料 · 事实核验 · 人工确认</p></div></div>
      <div className="sidebar-bottom"><span className="scope-mark small">我</span><div><strong>我的申请空间</strong><small>课程实验版</small></div><Icon name="lock" /></div>
    </aside>
    <div className="workspace-body">
      <header className="workspace-topbar">
        <div className="workspace-breadcrumb"><span>申请工作台</span><Icon name="chevron" /><h1>{title}</h1></div>
        <details className="workspace-scenario"><summary><span className="connection-dot" />{scenario === 'live' ? '本地后端' : '预录 / 模拟'}<Icon name="down" /></summary>
          <div className="scenario-popover"><label htmlFor="demo-scenario">演示场景</label><select id="demo-scenario" value={scenario} onChange={event => {
            if (workflow && !window.confirm('切换演示场景会清空本页工作流与未采用的建议。是否继续？')) return
            setScenario(event.target.value as DemoScenario);navigate('/')
          }}>{SCENARIOS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select><p>预录场景展示本地样例；在线模式由后端返回结果。</p></div>
        </details>
        <details className="mobile-navigation" ref={drawer} onKeyDown={event => {
          if(event.key === 'Escape' && drawer.current) {drawer.current.open=false;drawer.current.querySelector('summary')?.focus()}
        }}><summary aria-label="展开导航"><Icon name="menu" /></summary><div className="mobile-nav-sheet">{navigation()}</div></details>
      </header>
      <main id="workspace-main" className="workspace-main" tabIndex={-1}>
        {workflow?._prerecorded && <p className="workspace-notice">{zhText(workflow._prerecorded.notice)}</p>}
        {fromPath && workflow?.mock_notice && !workflow._prerecorded && <p className="sample-data-note">{zhText(workflow.mock_notice)}</p>}
        {children}
      </main>
      <footer className="workspace-footer"><span>ApplyGuard · 让表达有据可依</span><details><summary>数据与模型说明</summary><p>数据来源：{dataSourceLabel}。{workflow?.mock_notice ? zhText(workflow.mock_notice) : ''} 岗位解析与 SAG 分别配置；SAG 启用时会向所配置的模型服务发送材料。</p></details></footer>
    </div>
  </div>
}
