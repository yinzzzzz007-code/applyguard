import { useEffect, useRef } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import type { DemoScenario } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { zhText } from '../i18n'
import { rememberMaxStep, stepFromPath } from '../flow'
import { NAV_GROUPS } from '../navigation'
import { Icon } from './Icon'
import { PageMotion } from './PageMotion'

const SCENARIOS: {id:DemoScenario;label:string}[] = [
  {id:'live',label:'连接本地后端'}, {id:'prerecorded_block',label:'预录 · 阻断样例'},
  {id:'prerecorded_fallback',label:'预录 · 回退样例'}, {id:'error',label:'错误重试样例'},
]

export function AppShell({children}:{children:React.ReactNode}) {
  const {scenario,setScenario,setStep,dataSourceLabel,workflow,restoredAt,reviewStorageError,reviewDrafts} = useDemo()
  const location = useLocation()
  const navigate = useNavigate()
  const drawer = useRef<HTMLDetailsElement>(null)
  const fromPath = stepFromPath(location.pathname)
  const title = location.pathname === '/help' ? '使用帮助' : NAV_GROUPS.flatMap(group => group.items).find(item => item.path === location.pathname)?.label ?? '申请工作台'
  useEffect(() => {
    const target = stepFromPath(location.pathname)
    if (target) {setStep(target);rememberMaxStep(target)}
    if (drawer.current) drawer.current.open = false
    window.scrollTo({top:0,left:0,behavior:'auto'})
  },[location.pathname,setStep])

  function navigation() {
    return <>
      <div className="workspace-scope"><span className="scope-mark">个</span><div><strong>个人工作台</strong><small>本地申请空间</small></div></div>
      {NAV_GROUPS.map(group => <nav className="workspace-nav grouped-nav" key={group.label} aria-label={group.label}>
        <p className="nav-group-label">{group.label}</p>
        {group.items.map(item => <NavLink key={item.path} end={item.path === '/'} to={item.path} className={({isActive}) => `workspace-nav-item${isActive ? ' is-current' : ''}`}>
          <Icon name={item.icon} /><span>{item.label}</span>{location.pathname === item.path && <span className="nav-current-dot" />}
        </NavLink>)}
      </nav>)}
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
        <NavLink className="workspace-help-link" to="/help" aria-label="使用帮助"><Icon name="file" /><span>使用帮助</span></NavLink>
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
        {fromPath && workflow?.mock_notice && !workflow._prerecorded && <details className="sample-data-note"><summary>演示与处理说明</summary><p>当前为本地实验版，网申使用模拟表单，最终提交由本人完成。</p><p>{zhText(workflow.mock_notice)}</p></details>}
        {restoredAt && workflow && <p className="workspace-notice" role="status">已恢复上次申请的文字与编辑进度（{new Date(restoredAt).toLocaleString('zh-CN')}）。材料状态需重新检查。<NavLink to="/resume">继续审核草稿</NavLink></p>}
        {reviewStorageError && <p className="danger-text" role="alert">{reviewStorageError}</p>}
        {!!Object.keys(reviewDrafts).length && location.pathname !== '/resume' && <p className="workspace-notice">审核页有 {Object.keys(reviewDrafts).length} 处暂存输入。<NavLink to="/resume">返回保存修改</NavLink></p>}
        <PageMotion>{children}</PageMotion>
      </main>
      <footer className="workspace-footer"><span>ApplyGuard · 让表达有据可依</span><details><summary>数据与模型说明</summary><p>数据来源：{dataSourceLabel}。{workflow?.mock_notice ? zhText(workflow.mock_notice) : ''} 岗位解析与 SAG 分别配置；SAG 启用时会向所配置的模型服务发送材料。</p></details></footer>
    </div>
  </div>
}
