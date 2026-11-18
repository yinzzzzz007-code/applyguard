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
    <div><h3 id="demo-start-title">先用样例走一遍流程</h3></div>
    <div className="btn-row">
      <button type="button" className="btn secondary" onClick={() => start('prerecorded_block')}>体验错改阻断</button>
      <button type="button" className="btn secondary" onClick={() => start('prerecorded_fallback')}>体验超时回退</button>
    </div>
  </section>
}
