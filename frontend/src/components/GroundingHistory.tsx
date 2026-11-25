import { useState } from 'react'
import {useNavigate} from 'react-router-dom'
import { useDemo } from '../context/DemoContext'
import { ZH_CLAIM, ZH_WORKFLOW, zhLookup } from '../i18n'
import { classroomInitialVersion, classroomReplayVersions } from '../resume/classroomSample'
import { loadTextVersions, replayTextVersion, restoreTextVersion, saveTextVersion } from '../resume/groundingHistory'
import {historyVersionLabel} from '../resume/review'
import {AtomicEvidence} from './AtomicEvidence'
import {diffSpans} from '../resume/review'

const CHOICE_LABELS: Record<string, string> = { original: '用原句', edit: '自己改', accept: '确认采用' }

export function GroundingHistory() {
  const {workflow,restoreHistoryWorkflow,reviewDrafts} = useDemo()
  const navigate = useNavigate()
  const [notice,setNotice] = useState('')
  if (!workflow) return null
  const versions = loadTextVersions(workflow.candidate_id).filter(v => v.applicationId === workflow.application_id)
  const hasClassroomDraft = workflow.application_id === classroomInitialVersion.applicationId
    && workflow.candidate_id === classroomInitialVersion.candidateId
  const visibleVersions = hasClassroomDraft ? [...versions, ...classroomReplayVersions, classroomInitialVersion] : versions
  return <details className="grounding-history"><summary><span>历史版本</span><small>本地 {versions.length} / 20 版</small></summary>
    <p>查看历史无需等待模型。历史事实和引用仅供回看；回滚恢复正文并清除当前处理选择，须重新核验。</p>
    <button className="btn secondary" type="button" onClick={() => {
      try {saveTextVersion(workflow,'手动保存');setNotice(`当前版本已保存 · ${new Date().toLocaleTimeString()}`)}
      catch {setNotice('保存失败，尚未更改当前内容。')}
    }}>保存当前版本</button>
    {!visibleVersions.length && <p className="muted">尚无历史版本，可先保存当前版本。</p>}
    {visibleVersions.map(version => <details className="item-block grounding-history-version" key={version.id}>
      <summary>{historyVersionLabel(version.label,Array.isArray(version.stateSnapshot?.proposals)?version.stateSnapshot.proposals.length:null)} · {version.claims.length} 条
        <small>{version.createdAt ? new Date(version.createdAt).toLocaleString() : '课堂示例'}</small>
      </summary>
      {version.stateSnapshot && <p className="muted">当时状态：{zhLookup(ZH_WORKFLOW, version.stateSnapshot.workflowStatus)}
        {version.stateSnapshot.requiresReverification && ' · 当时待重新核验'}</p>}
      {version.claims.length > 0 && <ol className="grounding-history-claims">
        {version.claims.map(claim => {
          const state = version.stateSnapshot?.claimStates?.find(row => row.claim_id === claim.claim_id)?.state
          const choice = version.stateSnapshot?.userChoices?.find(row => row.claim_id === claim.claim_id)
          const proposal = version.stateSnapshot?.proposals?.find(row => row.claim_id === claim.claim_id)
          const result = version.stateSnapshot?.historicalResults?.[claim.claim_id]
          const original = result?.original_text ?? claim.text
          const suggested = result?.proposed_text ?? proposal?.text
          const parts = suggested && suggested !== original ? diffSpans(original,suggested) : null
          return <li key={claim.claim_id}>
            {parts ? <div className="history-comparison"><div><strong>润色前</strong><p className="grounding-history-text">{parts.original.map((part,index) => part.changed ? <mark key={index}>{part.text}</mark> : part.text)}</p></div>
              <div><strong>历史润色建议{proposal?.rejected ? '（未采用）' : ''}</strong><p className="grounding-history-text">{parts.proposal.map((part,index) => part.changed ? <mark key={index}>{part.text}</mark> : part.text)}</p></div></div>
              : <p className="grounding-history-text">{claim.text}</p>}
            {state && <p className="muted">材料检查：{zhLookup(ZH_CLAIM, state)}</p>}
            {choice && <p className="muted">当时选择：{zhLookup(CHOICE_LABELS, choice.action)}{choice.text !== claim.text && ` · ${choice.text}`}</p>}
            {!parts && proposal && <p className="grounding-history-text">历史建议{proposal.rejected ? '（未采用）' : ''}：{proposal.text}</p>}
            {result && <details><summary>查看当时的原子核验与引用</summary><p className="muted">这是历史记录，可能不再适用于当前正文或材料；仅保存当时引用，完整检索记录保存在本机后端。</p><AtomicEvidence result={result} historical /></details>}
          </li>
        })}
      </ol>}
      {Boolean(version.stateSnapshot && (Object.keys(version.stateSnapshot.historicalResults ?? {}).length || version.stateSnapshot.proposals?.length || version.stateSnapshot.claimStates?.length)) && <button className="btn primary" type="button" onClick={() => {
        try {
          if (Object.keys(reviewDrafts).length) {setNotice('请先保存或取消正在编辑的正文，再打开回放。');return}
          const replayed = replayTextVersion(workflow,version)
          saveTextVersion(workflow,'回放前自动备份')
          restoreHistoryWorkflow(replayed)
          setNotice('已打开历史回放；原子结论是旧记录，当前正文仍需重新核验。')
          navigate(version.stateSnapshot?.operation === 'verify' ? '/claims' : '/resume')
        } catch (error) {setNotice(error instanceof Error ? error.message : '无法打开历史回放。')}
      }}>回放当时页面</button>}
      <button className="btn secondary" type="button" onClick={() => {
        try {
          if (Object.keys(reviewDrafts).length) {setNotice('请先保存或取消正在编辑的正文，再回滚。');return}
          const restored = restoreTextVersion(workflow,version)
          saveTextVersion(workflow,'回滚前自动备份')
          saveTextVersion(restored,`回滚至：${version.label}`,localStorage,version.id)
          restoreHistoryWorkflow(restored)
          setNotice('已回滚并保存新版本；可选择“回滚前自动备份”撤销本次回滚。请重新核验。')
        } catch {setNotice('回滚或历史保存失败，当前正文未变。')}
      }}>回滚至此版</button>
    </details>)}
    {notice && <p role="status">{notice}</p>}
  </details>
}
