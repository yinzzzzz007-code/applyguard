import { useState } from 'react'
import { useDemo } from '../context/DemoContext'
import { loadTextVersions, restoreTextVersion, saveTextVersion } from '../resume/groundingHistory'

export function GroundingHistory() {
  const {workflow,patchWorkflow} = useDemo()
  const [notice,setNotice] = useState('')
  if (!workflow) return null
  const versions = loadTextVersions(workflow.candidate_id)
  return <details className="grounding-history"><summary>历史版本与状态回滚（本浏览器最近20版）</summary>
    <p>保存正文、删改记录及当时的核验状态。回滚创建新版本，历史通过状态只供查阅，恢复后须重新核验。清除浏览器存储会失去历史。</p>
    <button className="btn secondary" type="button" onClick={() => {
      try {saveTextVersion(workflow,'手动保存');setNotice(`当前版本已保存 · ${new Date().toLocaleTimeString()}`)}
      catch {setNotice('保存失败，尚未更改当前内容。')}
    }}>保存当前版本</button>
    {!versions.length && <p className="muted">尚无历史版本，可先保存当前版本。</p>}
    {versions.map(version => <div className="item-block" key={version.id}>
      <p>{version.label} · {new Date(version.createdAt).toLocaleString()}</p>
      <p>{version.claims.map(c => c.text).join('\n')}</p>
      {version.stateSnapshot && <p className="muted">当时状态：{version.stateSnapshot.workflowStatus} ·
        {version.stateSnapshot.claimStates.map(c => `${c.claim_id}: ${c.state}`).join('；')}
        {version.stateSnapshot.requiresReverification && ' · 当时待重新核验'}</p>}
      {version.stateSnapshot?.proposals?.map(p => <p className="muted" key={p.claim_id}>历史建议{p.rejected ? '（未采用）' : ''}：{p.text}</p>)}
      <button className="btn secondary" type="button" onClick={() => {
        try {
          const restored = restoreTextVersion(workflow,version)
          saveTextVersion(workflow,'回滚前自动备份')
          saveTextVersion(restored,`回滚至：${version.label}`,localStorage,version.id)
          patchWorkflow(restored)
          setNotice('已回滚并保存新版本；可选择“回滚前自动备份”撤销本次回滚。请重新核验。')
        } catch {setNotice('回滚或历史保存失败，当前正文未变。')}
      }}>回滚至此版</button>
    </div>)}
    {notice && <p role="status">{notice}</p>}
  </details>
}
