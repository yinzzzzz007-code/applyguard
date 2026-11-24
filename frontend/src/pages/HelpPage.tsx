import { DemoQuickStart } from '../components/DemoQuickStart'
import { lazy, Suspense, useState } from 'react'
import { Link } from 'react-router-dom'
import { ONBOARDING_STEPS } from '../motion/onboarding'

const ProjectReel = lazy(() => import('../components/ProjectReel').then(module => ({default:module.ProjectReel})))
const destinations = ['/', '/evidence', '/jd', '/resume']

export function HelpPage() {
  const [animationOpen,setAnimationOpen] = useState(false)
  return <section className="panel help-page">
    <header className="panel-head"><h2>准备一份有依据的申请</h2><p>第一次从一个岗位、一条经历和几份相关材料开始。随时从顶部“使用帮助”回到这里。</p></header>
      <DemoQuickStart />
    <div className="help-steps">{ONBOARDING_STEPS.map((step,index) => <article key={step.id}>
      <span className="help-step-number">{index+1}</span><div><h3>{step.title}</h3><p>{step.original}</p><p className="help-completion">完成标志：{step.completion}</p>
        <Link className="text-action" to={destinations[index]}>前往{['简历导入','证明材料','岗位说明','简历审查'][index]}</Link></div>
    </article>)}</div>
    <section className="help-export"><h3>看懂核验页的正文标色</h3><p>蓝色标出待核对的词句；红色标出有原文依据的冲突。点击彩色词句可查看原因。展开“材料与核验明细”查看出处，有候选证书时可直接打开核对。只需编辑或排除有问题的条目；下一步统一保留其余陈述。</p><p>如果按钮暂不可用，点“查看原因与补全引导”。云朵会带你到当前要操作的位置；保存或取消一条后，再处理下一条。</p><Link to="/claims">打开陈述核验</Link></section>
    <section className="help-export"><h3>两种完成方式</h3><p><strong>导出个人草稿：</strong>在简历审查页预览并确认正文，下载 TXT 或可编辑的 LaTeX 源文件。未获材料支持的内容仍保留记录。</p><p><strong>准备网申：</strong>继续完成材料核验，再进入模拟填写和最终确认。整个系统不会向招聘网站自动提交。</p></section>
    <details className="help-animation" open={animationOpen} onToggle={event => setAnimationOpen(event.currentTarget.open)}><summary>观看 24 秒操作介绍（可选）</summary>
      {animationOpen && <Suspense fallback={<p role="status">正在加载介绍…</p>}><ProjectReel /></Suspense>}
    </details>
  </section>
}
