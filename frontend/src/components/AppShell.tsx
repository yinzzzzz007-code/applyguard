import { useEffect } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import type { DemoScenario } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { zhText } from '../i18n'
import { STEP_META, STEP_ORDER, stepFromPath, stepIndex } from '../flow'

const SCENARIOS: { id: DemoScenario; label: string; hint: string }[] = [
  { id: 'live', label: '正常·在线', hint: '调用运行中的后端，默认离线规则解析' },
  { id: 'prerecorded_block', label: '预录·阻断', hint: '预录：不支持内容被阻断' },
  {
    id: 'prerecorded_fallback',
    label: '预录·回退',
    hint: '预录：模型超时后规则回退',
  },
  { id: 'error', label: '错误重试', hint: '模拟后端不可用，或配合空岗位说明' },
]

export function AppShell({ children }: { children: React.ReactNode }) {
  const { scenario, setScenario, step, setStep, dataSourceLabel, workflow } = useDemo()
  const location = useLocation()
  const navigate = useNavigate()
  const current = stepIndex(step)

  useEffect(() => {
    setStep(stepFromPath(location.pathname))
  }, [location.pathname, setStep])

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <p className="eyebrow">课程演示界面</p>
          <h1 className="brand">申请护栏</h1>
          <p className="tagline">
            把可核查的经历变成可解释的简历建议，并在模拟网申前停下来让你确认。
          </p>
          <p className="muted data-source">数据来源：{dataSourceLabel}</p>
          {workflow?.mock_notice ? (
            <p className="muted tip-inline">{zhText(workflow.mock_notice)}</p>
          ) : null}
          {workflow?._prerecorded ? (
            <p className="warn-text tip-inline">{zhText(workflow._prerecorded.notice)}</p>
          ) : null}
        </div>
        <div className="scenario-switch" aria-label="演示场景">
          <span className="scenario-label">演示场景</span>
          <div className="scenario-buttons">
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                type="button"
                className={scenario === s.id ? 'chip active' : 'chip'}
                title={s.hint}
                onClick={() => {
                  setScenario(s.id)
                  navigate('/')
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
        <NavLink to="/history" className="btn secondary">申请历史</NavLink>
      </header>

      <nav className="step-nav" aria-label="流程步骤">
        <ol>
          {STEP_ORDER.map((key, idx) => {
            const meta = STEP_META[key]
            const reachable = idx <= current
            return (
              <li key={key} className={idx === current ? 'current' : reachable ? 'done' : ''}>
                {reachable ? (
                  <NavLink to={meta.path}>{meta.label}</NavLink>
                ) : (
                  <span>{meta.label}</span>
                )}
              </li>
            )
          })}
        </ol>
      </nav>

      <main className="page">{children}</main>

      <footer className="footer">
        <p>
          在线演示默认走离线规则解析（不调模型）。预录场景加载本地样例，不冒充本次实时计算。
        </p>
      </footer>
    </div>
  )
}
