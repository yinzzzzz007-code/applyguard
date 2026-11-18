import { BackendStatus } from './BackendStatus'
import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import type { DemoScenario } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { zhText } from '../i18n'
import { rememberMaxStep, stepFromPath } from '../flow'
import { NAV_GROUPS } from '../navigation'
import { applyTheme, readStoredTheme, toggleTheme, type ThemeMode } from '../theme'
import { Icon } from './Icon'
import { PageMotion } from './PageMotion'

const RESTORE_NOTICE_KEY = 'applyguard.restore-notice.dismissed'

const SCENARIOS: {id:DemoScenario;label:string}[] = [
  {id:'live',label:'连接本地后端'}, {id:'prerecorded_block',label:'预录 · 阻断样例'},
  {id:'prerecorded_fallback',label:'预录 · 回退样例'}, {id:'error',label:'错误重试样例'},
]

export function AppShell({children}:{children:React.ReactNode}) {
  const {scenario,setScenario,setStep,workflow,restoredAt,reviewStorageError,reviewDrafts,resumeForm} = useDemo()
  const location = useLocation()
  const navigate = useNavigate()
  const drawer = useRef<HTMLDetailsElement>(null)
  const [restoreDismissed, setRestoreDismissed] = useState(() => {
    try { return sessionStorage.getItem(RESTORE_NOTICE_KEY) === restoredAt } catch { return false }
  })
  const [theme, setTheme] = useState<ThemeMode>(() => readStoredTheme())
  const title = location.pathname === '/help' ? '使用帮助' : NAV_GROUPS.flatMap(group => group.items).find(item => item.path === location.pathname)?.label ?? '申请工作台'
  useEffect(() => {
    applyTheme(theme)
  }, [theme])
  useEffect(() => {
    const target = stepFromPath(location.pathname)
    if (target) {setStep(target);rememberMaxStep(target)}
    if (drawer.current) drawer.current.open = false
    window.scrollTo({top:0,left:0,behavior:'auto'})
  },[location.pathname,setStep])
  useEffect(() => {
    try {
      setRestoreDismissed(sessionStorage.getItem(RESTORE_NOTICE_KEY) === restoredAt)
    } catch {
      setRestoreDismissed(false)
    }
  }, [restoredAt])

  function navigation() {
    return <>
      <div className="workspace-scope"><span className="scope-mark">个</span><div><strong>个人工作台</strong></div></div>
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
      <NavLink to="/" className="workspace-brand" aria-label="ApplyGuard 申请护栏首页">
        <Icon name="brand" />
        <span>ApplyGuard</span>
      </NavLink>
      {navigation()}
      <div className="sidebar-bottom"><span className="scope-mark small">我</span><div><strong>我的申请空间</strong></div><Icon name="lock" /></div>
    </aside>
    <div className="workspace-body">
      <header className="workspace-topbar">
        <div className="workspace-breadcrumb"><span>申请工作台</span><Icon name="chevron" /><h1>{title}</h1></div>
        <NavLink className="workspace-help-link" to="/help" aria-label="使用帮助"><Icon name="file" /><span>使用帮助</span></NavLink>
        <button
          type="button"
          className="theme-toggle"
          aria-label={theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'}
          title={theme === 'dark' ? '浅色' : '深色'}
          onClick={() => setTheme(current => toggleTheme(current))}
        >
          <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          <span>{theme === 'dark' ? '浅色' : '深色'}</span>
        </button>
        <details className="workspace-scenario"><summary><BackendStatus key={scenario} live={scenario === 'live'} /><Icon name="down" /></summary>
          <div className="scenario-popover"><label htmlFor="demo-scenario">演示场景</label><select id="demo-scenario" value={scenario} onChange={event => {
            if ((workflow || resumeForm?.dirty || Object.keys(reviewDrafts).length) && !window.confirm('切换演示场景会清空当前工作流与未保存编辑。已保存的经历和材料不受影响。是否继续？')) return
            setScenario(event.target.value as DemoScenario);event.currentTarget.closest('details')?.removeAttribute('open');navigate(event.target.value === 'live' ? '/' : '/jd')
          }}>{SCENARIOS.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></div>
        </details>
        <details className="mobile-navigation" ref={drawer} onKeyDown={event => {
          if(event.key === 'Escape' && drawer.current) {drawer.current.open=false;drawer.current.querySelector('summary')?.focus()}
        }}><summary aria-label="展开导航"><Icon name="menu" /></summary><div className="mobile-nav-sheet">{navigation()}</div></details>
      </header>
      <main id="workspace-main" className="workspace-main" tabIndex={-1}>
        {workflow?._prerecorded && <p className="workspace-notice">{zhText(workflow._prerecorded.notice)}</p>}
        {restoredAt && workflow && !restoreDismissed && (
          <p className="workspace-notice" role="status">
            已恢复本机上次进度（{new Date(restoredAt).toLocaleString('zh-CN')}）。
            {' '}<NavLink to="/resume">打开简历审查</NavLink>
            {' · '}
            <button
              type="button"
              className="text-action"
              onClick={() => {
                try { sessionStorage.setItem(RESTORE_NOTICE_KEY, restoredAt) } catch { /* ignore */ }
                setRestoreDismissed(true)
              }}
            >
              知道了
            </button>
          </p>
        )}
        {reviewStorageError && <p className="danger-text" role="alert">{reviewStorageError}</p>}
        {!!Object.keys(reviewDrafts).length && location.pathname !== '/resume' && <p className="workspace-notice">审核页有 {Object.keys(reviewDrafts).length} 处暂存输入。<NavLink to="/resume">返回保存修改</NavLink></p>}
        <PageMotion>{children}</PageMotion>
      </main>
      <footer className="workspace-footer"><span>ApplyGuard</span></footer>
    </div>
  </div>
}
