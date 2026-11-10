import { lazy, Suspense, useState } from 'react'
import { Link } from 'react-router-dom'
import { ONBOARDING_STEPS } from '../motion/onboarding'

const ProjectReel = lazy(() => import('../components/ProjectReel').then(module => ({default:module.ProjectReel})))
const destinations = ['/', '/evidence', '/jd', '/resume']

export function HelpPage() {
  const [animationOpen,setAnimationOpen] = useState(false)
  return <section className="panel help-page">
    <header className="panel-head"><h2>准备一份有依据的申请</h2><p>第一次从一个岗位、一条经历和几份相关材料开始。随时从顶部“使用帮助”回到这里。</p></header>
    <div className="help-steps">{ONBOARDING_STEPS.map((step,index) => <article key={step.id}>
      <span className="help-step-number">{index+1}</span><div><h3>{step.title}</h3><p>{step.original}</p><p className="help-completion">完成标志：{step.completion}</p>
        <Link className="text-action" to={destinations[index]}>前往{['简历导入','证明材料','岗位说明','简历审查'][index]}</Link></div>
    </article>)}</div>
    <section className="help-export"><h3>两种完成方式</h3><p><strong>导出个人草稿：</strong>在简历审查页预览并确认正文，下载 TXT。未获材料支持的内容仍保留记录。</p><p><strong>准备网申：</strong>继续完成材料核验，再进入模拟填写和最终确认。整个系统不会向招聘网站自动提交。</p></section>
    <details className="help-animation" open={animationOpen} onToggle={event => setAnimationOpen(event.currentTarget.open)}><summary>观看 24 秒操作介绍（可选）</summary>
      {animationOpen && <Suspense fallback={<p role="status">正在加载介绍…</p>}><ProjectReel /></Suspense>}
    </details>
  </section>
}
