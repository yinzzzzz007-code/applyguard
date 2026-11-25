import {useDemo} from '../context/DemoContext'
import {exitHistoryReplay} from '../resume/reviewSession'

export function HistoryReplayNotice() {
  const {workflow,setWorkflow} = useDemo()
  if (!workflow?._historyReplay) return null
  return <section className="callout warn" role="status" aria-label="历史回放模式">
    <p><strong>当前是历史回放：</strong>{workflow._historyReplay.label}。可以查看、采用建议或编辑；当时的核验结果仅供参考。</p>
    <button type="button" className="btn primary" data-guide="exit-history" onClick={()=>setWorkflow(exitHistoryReplay(workflow))}>结束回放，保留当前正文</button>
    <p>结束后可继续正常润色和核验。若想恢复进入回放前的正文，可在历史版本中选择「回放前自动备份」。</p>
  </section>
}
