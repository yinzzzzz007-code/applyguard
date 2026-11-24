import { useEffect, useRef, useState } from 'react'
import { jobsRequest, type JobAlert, type JobSource, type Opportunity, type RefreshStatus } from '../api/jobs'
import { RadarDialog } from './RadarDialog'
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
  const [panel,setPanel]=useState<'new'|'alerts'|'high'|'sources'|null>(null)
  const [alertDetail,setAlertDetail]=useState<JobAlert|null>(null)
  const [moreAlerts,setMoreAlerts]=useState(false)
  const alertLimit=useRef(200)
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
          jobsRequest<{ items: JobAlert[]; unread: number; has_more:boolean }>('/alerts?order=relevance&unread=true&limit=200'),
        ])
        if (disposed || generation !== requestId) return
        setPollError('')
        setSources(config.items); setStatus(state); setAlerts(inbox.items); setUnread(inbox.unread);setMoreAlerts(inbox.has_more);alertLimit.current=200
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

  async function action(request: () => Promise<unknown>, refreshInbox=true) {
    setPending(true); setError(''); setNote('')
    try {
      await request()
      if(refreshInbox)window.dispatchEvent(new Event('applyguard:official-jobs-updated'))
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
  async function loadMoreAlerts() {
    await action(async()=>{
      const inbox=await jobsRequest<{items:JobAlert[];has_more:boolean}>('/alerts?order=relevance&unread=true&limit=200&offset='+alertLimit.current)
      setAlerts(previous=>Array.from(new Map([...previous,...inbox.items].map(item=>[item.event_key,item])).values()))
      alertLimit.current+=inbox.items.length;setMoreAlerts(inbox.has_more)
    },false)
  }
  function openPanel(value:NonNullable<typeof panel>){setAlertDetail(null);setPanel(value)}
  function selectJob(id:string){setPanel(null);onSelect(id)}
  const recommended=[...jobs].sort((a,b)=>(a.recommendation_rank??99999)-(b.recommendation_rank??99999))
  const newJobs=recommended.filter(job=>job.is_new)
  const highJobs=recommended.filter(job=>job.match_level==='high'&&job.status==='open'&&job.stage!=='archived')
  const failedSources=sources.filter(source=>source.consecutive_failures>0)
  const refreshReason=!status?(pollError?'官网状态读取失败，请稍后重试。':'正在读取官网状态，请稍候。'):pending?'正在提交操作，请稍候。':status?.state==='running'?'官网刷新正在进行，完成后可再次刷新。':!sources.some(s=>s.enabled)?'请在“来源状态与计划”中启用至少一个来源。':''
  const recent = Object.values(status?.last?.result ?? {})

  return <Card asChild><section className="official-job-radar" aria-labelledby="official-jobs-title">
    <CardHeader className="official-radar-heading">
      <div>
        <CardTitle asChild><h3 id="official-jobs-title">官网动态</h3></CardTitle>
        <CardDescription asChild><p>由本机后端刷新。时间按北京时间显示。</p></CardDescription>
      </div>
      <Button disabledReason={refreshReason} disabled={pending || status?.state === 'running' || !sources.some(s => s.enabled)} onClick={() => void refresh()}>刷新全部官网</Button>
    </CardHeader>
    <div className="radar-metrics" aria-label="岗位提醒摘要">
      <button type="button" aria-haspopup="dialog" onClick={()=>openPanel('new')}>新增岗位<strong>{newJobs.length}</strong><small>点击查看岗位</small></button>
      <button type="button" aria-haspopup="dialog" onClick={()=>openPanel('alerts')}>未读提醒<strong>{unread}</strong><small>点击逐条查看</small></button>
      <button type="button" aria-haspopup="dialog" onClick={()=>openPanel('high')}>在招高匹配<strong>{highJobs.length}</strong><small>点击查看岗位</small></button>
      <button type="button" aria-haspopup="dialog" onClick={()=>openPanel('sources')}>来源异常<strong>{failedSources.length}</strong><small>点击查看来源</small></button>
    </div>
    {refreshReason&&<p role="status">{refreshReason}</p>}
    <p role="status">{status ? STATES[status.state] : '正在读取刷新状态'} · 最近完成 {localTime(status?.last?.finished_at)} · 下次计划 {localTime(status?.next_refresh_at)}</p>
    {status?.current && <p className="muted">已完成 {Object.keys(status.current.result).length} / {status.current.sources.length} 个来源</p>}
    {!status?.current && recent.length > 0 && <p className="muted">
      新增 {recent.reduce((sum, r) => sum + r.created, 0)} · 更新 {recent.reduce((sum, r) => sum + r.updated, 0)}
      {' · '}未变化 {recent.reduce((sum, r) => sum + (r.unchanged ?? 0), 0)} · 下线 {recent.reduce((sum, r) => sum + r.closed, 0)} · 跳过 {recent.reduce((sum, r) => sum + r.skipped, 0)}
    </p>}
    {!status?.current && Object.entries(status?.last?.result ?? {}).filter(([, result]) => result.notice).map(([id, result]) =>
      <p className="muted" key={id}>{sources.find(source => source.source_id === id)?.company ?? id}：{result.notice}</p>)}
    {note && <p role="status">{note}</p>}
    {error && <p className="callout warn" role="alert">{error}</p>}
    {pollError && <p className="callout warn" role="status">官网动态暂不可用：{pollError}</p>}
    <div className="btn-row official-radar-actions">
      <label>指定来源 <select data-guide="refresh-source" aria-label="选择刷新来源" value={selected} onChange={event => setSelected(event.target.value)}>
        <option value="">请选择</option>{sources.filter(s => s.enabled).map(s => <option key={s.source_id} value={s.source_id}>{s.company}</option>)}
      </select></label>
      <Button variant="secondary" guideRequirements={!selected?[{id:"source",label:"先在这里选择要刷新的官网来源。",selector:'[data-guide="refresh-source"]'}]:[]} disabledReason={pending?'正在提交，请稍候。':!selected?'请先选择一个官网来源。':'官网刷新正在进行。'} disabled={pending || !selected || status?.state === 'running'} onClick={() => void refresh(selected)}>刷新选中来源</Button>
      <label><input type="checkbox" checked={force} onChange={event => setForce(event.target.checked)} /> 强制刷新</label>
    </div>
    <details className="radar-import">
      <summary>来源状态与计划</summary>
      <ul className="official-radar-list">{sources.map(source => <li key={source.source_id}>
        <strong><a href={source.url} target="_blank" rel="noreferrer">{source.name} ↗</a></strong>
        <p>{source.enabled ? '已启用' : '已停用'} · {source.job_count} 条有效岗位（{source.details_count} 条已有详情） · 最近成功 {localTime(source.last_success_at)}</p>
        <p className="muted">下次计划 {source.enabled ? localTime(source.next_refresh_at) : '已暂停'}{source.last_error ? ' · ' + source.last_error : ''}</p>
        <div className="btn-row">
          <Button variant="secondary" disabledReason={!source.enabled?'请先启用这个来源。':pending?'正在提交，请稍候。':'官网刷新正在进行。'} disabled={!source.enabled || pending || status?.state === 'running'} onClick={() => void refresh(source.source_id)}>刷新{source.company}</Button>
          <label><input type="checkbox" checked={source.enabled} disabled={pending} onChange={event => void action(() => jobsRequest('/sources/' + source.source_id, { enabled: event.target.checked }, 'PATCH'))} />启用</label>
          <label>间隔 <select aria-label={source.company + '刷新间隔'} value={source.interval_hours} disabled={pending} onChange={event => void action(() => jobsRequest('/sources/' + source.source_id, { interval_hours: Number(event.target.value) }, 'PATCH'))}>
            {[6, 12, 24, 48, 72, 168].map(hours => <option key={hours} value={hours}>{hours} 小时</option>)}
          </select></label>
        </div>
      </li>)}</ul>
    </details>
    <details className="radar-import">
      <summary>站内提醒（{unread} 条未读）</summary>
      <Button variant="secondary" disabledReason={pending?'正在更新提醒，请稍候。':'没有未读提醒。'} disabled={!unread || pending} onClick={() => void action(async () => { await jobsRequest('/alerts/read-all', {}); await onReload() })}>全部标记已读</Button>
      <ul className="official-radar-list">{alerts.map(alert => <li key={alert.event_key}>
        <button type="button" className="text-action" onClick={()=>{openPanel('alerts');setAlertDetail(alert)}}>{ALERTS[alert.kind] ?? alert.kind} · {alert.title || sources.find(s => s.source_id === alert.source_id)?.company || alert.source_id}</button>
        <p>{alert.reason} · {localTime(alert.created_at)}</p>
        <div className="btn-row">
          {alert.job_id && <Button variant="secondary" onClick={() => onSelect(alert.job_id!)}>查看岗位</Button>}
          <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={pending} onClick={() => void action(async () => { await jobsRequest('/alerts/read', { ids: [alert.event_key] }); await onReload() })}>标记已读</Button>
        </div>
      </li>)}</ul>
      {moreAlerts&&<Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={pending} onClick={()=>void loadMoreAlerts()}>加载更多提醒</Button>}{!alerts.length && <p className="muted">没有未读提醒。</p>}
    </details>
    {panel&&<RadarDialog title={panel==='alerts'?`未读提醒（${unread}）`:panel==='new'?`新增岗位（${newJobs.length}）`:panel==='high'?`在招高匹配（${highJobs.length}）`:`来源异常（${failedSources.length}）`} onClose={()=>{setPanel(null);setAlertDetail(null)}}>
      {panel==='alerts'?<>
        {alertDetail?<article className="radar-alert-detail"><Button variant="ghost" onClick={()=>setAlertDetail(null)}>返回提醒列表</Button><h4>{ALERTS[alertDetail.kind]??alertDetail.kind} · {alertDetail.title||sources.find(s=>s.source_id===alertDetail.source_id)?.company||alertDetail.source_id}</h4><p>{alertDetail.reason}</p><p>时间：{localTime(alertDetail.created_at)}</p><p>来源：{sources.find(s=>s.source_id===alertDetail.source_id)?.name||alertDetail.source_id}</p><div className="btn-row">{alertDetail.job_id&&<Button onClick={()=>selectJob(alertDetail.job_id!)}>查看岗位详情</Button>}<Button variant="secondary" disabledReason={pending?'正在更新提醒，请稍候。':'这条提醒已经标记已读。'} disabled={pending||!alerts.some(item=>item.event_key===alertDetail.event_key)} onClick={()=>void action(async()=>{await jobsRequest('/alerts/read',{ids:[alertDetail.event_key]});setAlertDetail(null);await onReload()})}>标记已读</Button></div>{!alerts.some(item=>item.event_key===alertDetail.event_key)&&<p>这条提醒已标记已读。</p>}</article>:<>
          <p>点击一条提醒查看完整消息；打开列表不会自动标记已读。</p><Button variant="secondary" disabledReason={pending?'正在更新提醒，请稍候。':'没有未读提醒。'} disabled={pending||!unread} onClick={()=>void action(async()=>{await jobsRequest('/alerts/read-all',{});await onReload()})}>全部标记已读</Button>
          <ul className="radar-summary-list">{alerts.map(alert=><li key={alert.event_key}><button type="button" className="text-action" onClick={()=>setAlertDetail(alert)}>{ALERTS[alert.kind]??alert.kind} · {alert.title||sources.find(s=>s.source_id===alert.source_id)?.company||alert.source_id}</button><p>{alert.reason}</p><small>{localTime(alert.created_at)}</small></li>)}</ul>
          {moreAlerts&&<Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={pending} onClick={()=>void loadMoreAlerts()}>加载更多提醒</Button>}{!alerts.length&&<p>没有未读提醒。</p>}</>}
      </>:panel==='sources'?<><p>异常来源保留已有岗位，刷新恢复后会更新状态。</p><ul className="radar-summary-list">{failedSources.map(source=><li key={source.source_id}><h4>{source.company}</h4><p>{source.last_error||'近期刷新失败，请重试。'}</p><Button variant="secondary" disabledReason={refreshReason||'请先启用这个来源。'} disabled={!!refreshReason||!source.enabled} onClick={()=>void refresh(source.source_id)}>重新刷新{source.company}</Button>{!source.enabled&&<p>此来源已暂停，可在下方“来源状态与计划”启用。</p>}</li>)}</ul>{!failedSources.length&&<p>暂无异常来源。</p>}</>:<>
        <p>点击岗位查看完整职责、要求及版本，下方岗位列表仍可继续浏览。</p><ul className="radar-summary-list">{(panel==='new'?newJobs:highJobs).map(job=><li key={job.id}><button type="button" className="text-action" onClick={()=>selectJob(job.id)}>{job.title}</button><p>{job.company} · {job.location||'地点待确认'}</p><small>{job.status==='open'?'在招':job.status==='closed'?'已关闭':'状态待确认'}</small></li>)}</ul>{!(panel==='new'?newJobs:highJobs).length&&<p>暂时没有此类岗位。</p>}
      </>}
    </RadarDialog>}
  </section></Card>
}
