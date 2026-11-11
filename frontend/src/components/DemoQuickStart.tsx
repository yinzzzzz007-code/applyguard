import { useNavigate } from 'react-router-dom'
import type { DemoScenario } from '../api/types'
import { useDemo } from '../context/DemoContext'

export function DemoQuickStart() {
  const navigate = useNavigate()
  const { setScenario, workflow, resumeForm, reviewDrafts } = useDemo()
  function start(scenario: DemoScenario) {
    if ((workflow || resumeForm?.dirty || Object.keys(reviewDrafts).length) &&
        !window.confirm('进入预录演示会替换当前工作流并清空未保存编辑。已保存的经历和材料不受影响。继续？')) return
    setScenario(scenario)
    navigate('/jd')
  }
  return <section className="demo-quick-start" aria-labelledby="demo-start-title">
    <div><span className="demo-eyebrow">课堂演示</span><h3 id="demo-start-title">先用样例，走一遍审核流程</h3>
      <p>无需上传简历或连接模型。选择样例后，点击“加载演示结果”继续。</p></div>
    <div className="btn-row">
      <button type="button" className="btn secondary" onClick={() => start('prerecorded_block')}>体验错改阻断</button>
      <button type="button" className="btn secondary" onClick={() => start('prerecorded_fallback')}>体验超时回退</button>
    </div>
    <small>预录数据仅用于演示流程，不代表本次实时核验。可从顶部场景菜单返回本地后端。</small>
  </section>
}
