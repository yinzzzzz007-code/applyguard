import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { EmptyState, RiskBadge } from '../components/States'
import { loadApplicationHistory, removeApplicationHistory } from '../history'

export function ApplicationHistoryPage() {
  const navigate = useNavigate()
  const [records, setRecords] = useState(loadApplicationHistory)
  const [error, setError] = useState('')

  function remove(id: string) {
    if (!removeApplicationHistory(id)) {
      setError('无法删除这条本地记录，请检查浏览器存储权限。')
      return
    }
    setRecords(loadApplicationHistory())
    setError('')
  }

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>申请历史</h2>
        <p>这里只保存本浏览器的模拟结果摘要。没有真实投递、后端同步或跨设备历史；不会保存姓名、联系方式、证件号、JD 原文和简历正文。</p>
      </header>
      {error && <div className="callout danger">{error}</div>}
      {!records.length ? (
        <EmptyState
          title="还没有模拟记录"
          detail="完成一次人工确认或阻断回顾后，这里会出现记录。"
          actionLabel="回到经历库"
          onAction={() => navigate('/')}
        />
      ) : (
        <div className="stack">
          {records.map((record) => (
            <article className="item-block" key={record.id}>
              <div className="item-head">
                <h3>{record.title === 'UNKNOWN' ? '未知岗位' : record.title} · {record.company === 'UNKNOWN' ? '未知公司' : record.company}</h3>
                <RiskBadge level={record.riskLevel} />
              </div>
              <p><strong>结果：</strong>{record.outcome === 'BLOCKED_REVIEWED' ? '已知悉阻断，未投递' : '本地模拟确认，未投递'}</p>
              <p className="muted">记录时间：{new Date(record.recordedAt).toLocaleString()} · 来源：{record.source}</p>
              <p className="muted">申请编号：{record.applicationId} · 追踪编号：{record.traceId}</p>
              {record.targetJobId && <p className="muted">关联收藏岗位：{record.targetJobId} · 当次版本 v{record.targetJobVersion}</p>}
              <button type="button" className="btn secondary" onClick={() => remove(record.id)}>删除本地记录</button>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
