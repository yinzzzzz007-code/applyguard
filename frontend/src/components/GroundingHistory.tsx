import { useState } from 'react'
import { useDemo } from '../context/DemoContext'
import { ZH_CLAIM, ZH_WORKFLOW, zhLookup } from '../i18n'
import { loadTextVersions, restoreTextVersion, saveTextVersion } from '../resume/groundingHistory'

const CHOICE_LABELS: Record<string, string> = { original: '用原句', edit: '自己改', accept: '确认采用' }

export function GroundingHistory() {
  const {workflow,patchWorkflow} = useDemo()
  const [notice,setNotice] = useState('')
  if (!workflow) return null
  const versions = loadTextVersions(workflow.candidate_id).filter(v => v.applicationId === workflow.application_id)
  return <details className="grounding-history"><summary>历史版本与状态回滚（本浏览器最近20版）</summary>
    <p>保存正文、删改记录及当时的核验状态。回滚创建新版本，历史通过状态只供查阅，恢复后须重新核验。清除浏览器存储会失去历史。</p>
    <button className="btn secondary" type="button" onClick={() => {
      try {saveTextVersion(workflow,'手动保存');setNotice(`当前版本已保存 · ${new Date().toLocaleTimeString()}`)}
      catch {setNotice('保存失败，尚未更改当前内容。')}
    }}>保存当前版本</button>
    {!versions.length && <p className="muted">尚无历史版本，可先保存当前版本。</p>}
    {versions.map(version => <details className="item-block grounding-history-version" key={version.id}>
      <summary>{version.label} · {new Date(version.createdAt).toLocaleString()} · {version.claims.length} 条草稿</summary>
      {version.stateSnapshot && <p className="muted">当时状态：{zhLookup(ZH_WORKFLOW, version.stateSnapshot.workflowStatus)}
        {version.stateSnapshot.requiresReverification && ' · 当时待重新核验'}</p>}
      {version.claims.length > 0 && <ol className="grounding-history-claims">
        {version.claims.map(claim => {
          const state = version.stateSnapshot?.claimStates?.find(row => row.claim_id === claim.claim_id)?.state
          const choice = version.stateSnapshot?.userChoices?.find(row => row.claim_id === claim.claim_id)
          const proposal = version.stateSnapshot?.proposals?.find(row => row.claim_id === claim.claim_id)
          return <li key={claim.claim_id}>
            <p className="grounding-history-text">{claim.text}</p>
            {state && <p className="muted">材料检查：{zhLookup(ZH_CLAIM, state)}</p>}
            {choice && <p className="muted">当时选择：{zhLookup(CHOICE_LABELS, choice.action)}{choice.text !== claim.text && ` · ${choice.text}`}</p>}
            {proposal && <p className="grounding-history-text">历史建议{proposal.rejected ? '（未采用）' : ''}：{proposal.text}</p>}
          </li>
        })}
      </ol>}
      <button className="btn secondary" type="button" onClick={() => {
        try {
          const restored = restoreTextVersion(workflow,version)
          saveTextVersion(workflow,'回滚前自动备份')
          saveTextVersion(restored,`回滚至：${version.label}`,localStorage,version.id)
          patchWorkflow(restored)
          setNotice('已回滚并保存新版本；可选择“回滚前自动备份”撤销本次回滚。请重新核验。')
        } catch {setNotice('回滚或历史保存失败，当前正文未变。')}
      }}>回滚至此版</button>
    </details>)}
    {notice && <p role="status">{notice}</p>}
  </details>
}
