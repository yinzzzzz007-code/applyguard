import { useEffect, useRef, useState } from 'react'
import { jobsRequest, type JobAlert, type JobSource, type Opportunity, type RefreshStatus } from '../api/jobs'
import { Button } from './ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from './ui/card'

const STATES = { waiting: '等待刷新', running: '正在刷新', success: '刷新成功', partial: '部分来源失败',
  failed: '全部来源失败', interrupted: '刷新中断' }
const ALERTS: Record<string, string> = { new: '新增', updated: '要求更新', high: '高匹配',
  closing: '即将关闭', closed: '已下线', source_failed: '来源异常' }
const localTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '暂无'

export function OfficialJobRadar({ jobs, onReload, onSelect }: {
  jobs: Opportunity[]
  onReload: () => Promise<void>
  onSelect: (id: string) => void
}) {
  const [sources, setSources] = useState<JobSource[]>([])
  const [status, setStatus] = useState<RefreshStatus>()
  const [alerts, setAlerts] = useState<JobAlert[]>([])
  const [unread, setUnread] = useState(0)
  const [selected, setSelected] = useState('')
  const [force, setForce] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [pollError, setPollError] = useState('')
  const [note, setNote] = useState('')
  const last = useRef<string | null>(null)
  const notify = useRef(onReload)
  useEffect(() => { notify.current = onReload }, [onReload])

  useEffect(() => {
    let disposed = false
    let generation = 0
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      const requestId = ++generation
      let delay = 30000
      try {
        const [config, state, inbox] = await Promise.all([
          jobsRequest<{ items: JobSource[] }>('/sources'), jobsRequest<RefreshStatus>('/refresh/status'),
          jobsRequest<{ items: JobAlert[]; unread: number }>('/alerts?unread=true'),
        ])
        if (disposed || generation !== requestId) return
        setPollError('')
        setSources(config.items); setStatus(state); setAlerts(inbox.items); setUnread(inbox.unread)
        const latest = state.last?.id ?? ''
        if (last.current !== null && latest !== last.current) await notify.current()
        last.current = latest
        if (state.state === 'running') delay = 2000
      } catch (reason) {
        if (!disposed && generation === requestId) setPollError((reason as Error).message)
      }
      if (!disposed && generation === requestId) timer = setTimeout(poll, delay)
    }
    const refresh = () => { clearTimeout(timer); void poll() }
    void poll()
    window.addEventListener('applyguard:official-jobs-updated', refresh)
    return () => { disposed = true; clearTimeout(timer); window.removeEventListener('applyguard:official-jobs-updated', refresh) }
  }, [])

  async function action(request: () => Promise<unknown>) {
    setPending(true); setError(''); setNote('')
    try {
      await request()
      window.dispatchEvent(new Event('applyguard:official-jobs-updated'))
    } catch (reason) { setError((reason as Error).message) }
    finally { setPending(false) }
  }

  function refresh(source?: string) {
    return action(async () => {
      const result = await jobsRequest<{ message?: string; joined?: boolean }>('/refresh',
        { ...(source ? { source_ids: [source] } : {}), force })
      setNote(result.message ?? (result.joined ? '正在查看已有刷新任务。' : '刷新任务已启动。'))
    })
  }
  const recent = Object.values(status?.last?.result ?? {})

  return <Card asChild><section className="official-job-radar" aria-labelledby="official-jobs-title">
    <CardHeader className="official-radar-heading">
      <div>
        <CardTitle asChild><h3 id="official-jobs-title">官网动态</h3></CardTitle>
        <CardDescription asChild><p>由本机后端刷新。时间按北京时间显示。</p></CardDescription>
      </div>
      <Button disabled={pending || status?.state === 'running' || !sources.some(s => s.enabled)} onClick={() => void refresh()}>刷新全部官网</Button>
    </CardHeader>
    <div className="radar-metrics" aria-label="岗位提醒摘要">
      <span>新增岗位<strong>{jobs.filter(job => job.is_new).length}</strong></span>
      <span>未读提醒<strong>{unread}</strong></span>
      <span>在招高匹配<strong>{jobs.filter(job => job.match_level === 'high' && job.status === 'open' && job.stage !== 'archived').length}</strong></span>
      <span>来源异常<strong>{sources.filter(source => source.consecutive_failures > 0).length}</strong></span>
    </div>
    <p role="status">{status ? STATES[status.state] : '正在读取刷新状态'} · 最近完成 {localTime(status?.last?.finished_at)} · 下次计划 {localTime(status?.next_refresh_at)}</p>
    {status?.current && <p className="muted">已完成 {Object.keys(status.current.result).length} / {status.current.sources.length} 个来源</p>}
    {!status?.current && recent.length > 0 && <p className="muted">
      新增 {recent.reduce((sum, r) => sum + r.created, 0)} · 更新 {recent.reduce((sum, r) => sum + r.updated, 0)}
      {' · '}下线 {recent.reduce((sum, r) => sum + r.closed, 0)} · 跳过 {recent.reduce((sum, r) => sum + r.skipped, 0)}
    </p>}
    {note && <p role="status">{note}</p>}
    {error && <p className="callout warn" role="alert">{error}</p>}
    {pollError && <p className="callout warn" role="status">官网动态暂不可用：{pollError}</p>}
    <div className="btn-row official-radar-actions">
      <label>指定来源 <select aria-label="选择刷新来源" value={selected} onChange={event => setSelected(event.target.value)}>
        <option value="">请选择</option>{sources.filter(s => s.enabled).map(s => <option key={s.source_id} value={s.source_id}>{s.company}</option>)}
      </select></label>
      <Button variant="secondary" disabled={pending || !selected || status?.state === 'running'} onClick={() => void refresh(selected)}>刷新选中来源</Button>
      <label><input type="checkbox" checked={force} onChange={event => setForce(event.target.checked)} /> 强制刷新</label>
    </div>
    <details className="radar-import">
      <summary>来源状态与计划</summary>
      <ul className="official-radar-list">{sources.map(source => <li key={source.source_id}>
        <strong><a href={source.url} target="_blank" rel="noreferrer">{source.name} ↗</a></strong>
        <p>{source.enabled ? '已启用' : '已停用'} · {source.job_count} 条有效岗位（{source.details_count} 条已有详情） · 最近成功 {localTime(source.last_success_at)}</p>
        <p className="muted">下次计划 {source.enabled ? localTime(source.next_refresh_at) : '已暂停'}{source.last_error ? ' · ' + source.last_error : ''}</p>
        <div className="btn-row">
          <Button variant="secondary" disabled={!source.enabled || pending || status?.state === 'running'} onClick={() => void refresh(source.source_id)}>刷新{source.company}</Button>
          <label><input type="checkbox" checked={source.enabled} disabled={pending} onChange={event => void action(() => jobsRequest('/sources/' + source.source_id, { enabled: event.target.checked }, 'PATCH'))} />启用</label>
          <label>间隔 <select aria-label={source.company + '刷新间隔'} value={source.interval_hours} disabled={pending} onChange={event => void action(() => jobsRequest('/sources/' + source.source_id, { interval_hours: Number(event.target.value) }, 'PATCH'))}>
            {[6, 12, 24, 48, 72, 168].map(hours => <option key={hours} value={hours}>{hours} 小时</option>)}
          </select></label>
        </div>
      </li>)}</ul>
    </details>
    <details className="radar-import">
      <summary>站内提醒（{unread} 条未读）</summary>
      <Button variant="secondary" disabled={!unread || pending} onClick={() => void action(async () => { await jobsRequest('/alerts/read-all', {}); await onReload() })}>全部标记已读</Button>
      <ul className="official-radar-list">{alerts.map(alert => <li key={alert.event_key}>
        <strong>{ALERTS[alert.kind] ?? alert.kind} · {alert.title || sources.find(s => s.source_id === alert.source_id)?.company || alert.source_id}</strong>
        <p>{alert.reason} · {localTime(alert.created_at)}</p>
        <div className="btn-row">
          {alert.job_id && <Button variant="secondary" onClick={() => onSelect(alert.job_id!)}>查看岗位</Button>}
          <Button variant="secondary" disabled={pending} onClick={() => void action(async () => { await jobsRequest('/alerts/read', { ids: [alert.event_key] }); await onReload() })}>标记已读</Button>
        </div>
      </li>)}</ul>
      {!alerts.length && <p className="muted">没有未读提醒。</p>}
    </details>
  </section></Card>
}
