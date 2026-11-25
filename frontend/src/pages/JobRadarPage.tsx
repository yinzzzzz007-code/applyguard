import {ActionButton} from '../components/ui/action-button'
import { ProfileCheckList } from '../components/ProfileCheckList'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiClient } from '../api/client'
import { analyzeOpportunity, jobsRequest, MATCH_LABELS, OFFICIAL_SOURCES, type ImportResult, type JobAnalysis, type JobLibrary, type JobMatch, type RadarPage } from '../api/jobs'
import { ErrorState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { canPrepareJob, importMessage, JOB_STAGE, JOB_STATUS, parseJobImport } from '../jobs'
import { zhText, ZH_REQ_TYPE, zhLookup } from '../i18n'
import { Icon } from '../components/Icon'
import { Tabs } from '../components/Tabs'
import { OfficialJobRadar } from '../components/OfficialJobRadar'
import { filterJobs, type JobScope, type JobSort } from '../jobs'

function savedView():Record<string,string> {
  try {
    const raw = JSON.parse(sessionStorage.getItem('applyguard.jobs.view') || '{}')
    return raw && typeof raw === 'object' ? {query:typeof raw.query === 'string' ? raw.query.slice(0,500) : '',scope:typeof raw.scope === 'string' ? raw.scope : ''} : {}
  } catch {return {}}
}

const initialForm = { title: '', company: '', location: '', url: '', status: 'unknown', description: '' }

function formatJobTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })
}

export function JobRadarPage() {
  const navigate = useNavigate()
  const { resumeForm, setWorkflow, scenario, workflow, activeJobId, setActiveJobId, reviewDrafts } = useDemo()
  const [library, setLibrary] = useState<JobLibrary | null>(null)
  const [selectedId, setSelectedId] = useState(activeJobId ?? '')
  const [query, setQuery] = useState(() => savedView().query || '')
  const [statusFilter, setStatusFilter] = useState<JobScope>(() => {
    const value = savedView().scope
    return ['active','preparing','archived','all'].includes(value) ? value as JobScope : 'active'
  })
  const [sourceFilter,setSourceFilter] = useState('all')
  const [officialSource, setOfficialSource] = useState('')
  const [inboxFilter, setInboxFilter] = useState('')
  const [matchLevel, setMatchLevel] = useState('')
  const [recruitmentType, setRecruitmentType] = useState('')
  const [semantic, setSemantic] = useState<{id: string; hash: string; result: JobMatch}>()
  const [sort,setSort] = useState<JobSort>('match')
  const [detailOpen,setDetailOpen] = useState(false)
  const [detailTab,setDetailTab] = useState('description')
  const [coverageFilter,setCoverageFilter] = useState('all')
  const detailHeading = useRef<HTMLHeadingElement>(null)
  const [form, setForm] = useState(initialForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const formPanel = useRef<HTMLDetailsElement>(null)
  const [analysis, setAnalysis] = useState<(JobAnalysis & { resumeSignature: string }) | null>(null)
  const resumeSignature = JSON.stringify(resumeForm)
  const [versions, setVersions] = useState<Array<{ version: number; imported_at: string; job: { description: string; status: string } }> | null>(null)
  const [versionsFor,setVersionsFor] = useState('')
  const [radar, setRadar] = useState<RadarPage | null>(null)
  const [radarQuery, setRadarQuery] = useState('')
  const [radarIds, setRadarIds] = useState<number[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const revision = useRef(0)
  const fileInput = useRef<HTMLInputElement>(null)
  useEffect(() => {
    try {sessionStorage.setItem('applyguard.jobs.view',JSON.stringify({query,scope:statusFilter}))} catch { /* optional UI preference */ }
  },[query,statusFilter])

  function openForm() {
    if (!formPanel.current) return
    formPanel.current.open = true
    formPanel.current.scrollIntoView({block:'start',behavior:'auto'})
    formPanel.current.querySelector<HTMLInputElement>('input')?.focus()
  }
  function resetFilters() {
    setQuery(''); setStatusFilter('active'); setSourceFilter('all'); setDetailOpen(false)
    setOfficialSource(''); setInboxFilter(''); setMatchLevel(''); setRecruitmentType('')
  }

  function selectAlertJob(id: string) {
    resetFilters()
    setStatusFilter('all')
    setSelectedId(id); setDetailOpen(true); setDetailTab('description')
    requestAnimationFrame(() => detailHeading.current?.focus())
  }

  async function reload(preferId?: string) {
    const data = await jobsRequest<JobLibrary>()
    setLibrary(data)
    setSelectedId((prev) => preferId ?? (data.items.some(job => job.id === prev) ? prev : ''))
    revision.current += 1
    setAnalysis(null)
    setVersions(null)
  }
  useEffect(() => {
    let cancelled = false
    void jobsRequest<JobLibrary>().then((data) => {
      if (!cancelled) {
        setLibrary(data)
      }
    }).catch((e) => { if (!cancelled) setError(String(e.message)) })
    return () => { cancelled = true }
  }, [])
  useEffect(()=>{
    if(library?.ranking?.state!=='loading')return
    const timer=window.setTimeout(()=>void jobsRequest<JobLibrary>().then(setLibrary).catch(e=>setError(e.message)),2000)
    return ()=>window.clearTimeout(timer)
  },[library])
  useEffect(() => {
    revision.current += 1
    const invalidate = () => { revision.current += 1; setAnalysis(null) }
    window.addEventListener('applyguard:evidence-changed', invalidate)
    window.addEventListener('storage', invalidate)
    return () => { window.removeEventListener('applyguard:evidence-changed', invalidate); window.removeEventListener('storage', invalidate) }
  }, [resumeForm, selectedId, query, statusFilter, sourceFilter, sort])

  async function perform(task: () => Promise<void>) {
    setBusy(true); setError(''); setMessage('')
    try { await task() } catch (e) { setError(e instanceof Error ? e.message : '操作失败，请重试。') }
    finally { setBusy(false) }
  }
  async function importRows(rows: unknown[]) {
    const result = await jobsRequest<ImportResult>('/import', { jobs: rows })
    await reload(result.items[0]?.id)
    setMessage(importMessage(result))
  }
  async function loadExampleJobs() {
    const response = await fetch(`${import.meta.env.BASE_URL}data/job-opportunities.example.json`)
    if (!response.ok) throw new Error('无法读取岗位示例，请重试。')
    await importRows(parseJobImport(await response.text()))
  }

  async function browseRadar(offset = 0) {
    const params = new URLSearchParams({ search: radarQuery, offset: String(offset) })
    const result = await jobsRequest<RadarPage>(`/radar?${params}`)
    setRadar(result); setRadarIds([])
  }
  async function analyze() {
    if (!selected) return
    const version = ++revision.current
    let resume = resumeForm
    if (!resume) {
      const result = await getApiClient().getResumeDraft()
      if (result.error) throw new Error(result.error.message)
      resume = result.data ?? null
    }
    if (version !== revision.current) return
    const report = await analyzeOpportunity(selected.id, resume)
    if (version === revision.current) {setAnalysis({ ...report, resumeSignature });setDetailTab('analysis');setCoverageFilter('all')}
    else setMessage('经历或证据已变化，请重新预检查。')
  }
  const allJobs = library?.items ?? []
  const filtered = filterJobs(allJobs,query,statusFilter,sourceFilter,sort).filter(job =>
    (!officialSource || job.source_id === officialSource) && (!matchLevel || job.match_level === matchLevel)
    && (!recruitmentType || job.recruitment_type === recruitmentType)
    && (inboxFilter !== 'new' || job.is_new) && (inboxFilter !== 'unread' || job.unread))
  const selected = filtered.find(job => job.id === selectedId) ?? filtered[0]
  const match = selected?.match_reasons
  const excerpts = new Map<string, string[]>()
  for (const factor of selected?.factors ?? []) {
    for (const evidence of factor.evidence) {
      const labels = excerpts.get(evidence.text) ?? []
      if (!labels.includes(factor.label)) excerpts.set(evidence.text, [...labels, factor.label])
    }
  }
  const freshAnalysis = analysis && analysis.resumeSignature === resumeSignature && analysis.job_id === selected?.id && analysis.content_hash === selected?.content_hash
  const visibleRequirements = analysis?.requirements.filter(req => coverageFilter === 'all' || (coverageFilter === 'supported' ? req.coverage === 'SUPPORTED' : req.coverage !== 'SUPPORTED')) ?? []

  return <section className={'panel radar-page radar-workbench'+(detailOpen ? ' has-detail' : '')}>
    <header className="panel-head radar-page-heading">
      <div><h2>岗位雷达</h2></div>
      <button type="button" className={'btn '+(library?.items.length ? 'secondary' : 'primary')} onClick={openForm}><Icon name="plus" />{editingId ? '继续编辑岗位' : '添加岗位'}</button>
    </header>
    {scenario !== 'live' && <p className="callout warn">当前是预录演示场景。岗位库仍显示本机数据；准备真实岗位时请先在顶部切换「正常·在线」。</p>}
    {error && <ErrorState message={error} />}
    {message && <p className="radar-feedback" role="status"><Icon name="check" />{message}<button type="button" aria-label="关闭操作提示" onClick={() => setMessage('')}><Icon name="close" /></button></p>}
    {busy && <p className="radar-busy" role="status">正在处理，请稍候…</p>}
    {library?.ranking&&<p role="status">{library.ranking.notice} <Link to="/vault">修改经历与偏好</Link></p>}
    <OfficialJobRadar jobs={allJobs} onReload={reload} onSelect={selectAlertJob} />

    <div className="radar-tools-row">
    <details className="radar-import" ref={formPanel}>
      <summary>{editingId ? '编辑岗位（保存为新版本）' : '添加岗位 / 导入 JSON、JSONL'}</summary>
      <form className="radar-form" onSubmit={(e) => { e.preventDefault(); void perform(async () => {
        if (editingId) {
          const result = await jobsRequest<{ job: { id: string } }>(`/${editingId}/edit`, { job: form })
          await reload(result.job.id); setMessage('岗位已保存为新版本，旧工作流已失效。')
        } else await importRows([form])
        setForm(initialForm); setEditingId(null);if(formPanel.current) formPanel.current.open = false
      }) }}>
        <label>岗位名称<input required maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        <label>公司<input required maxLength={200} value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} /></label>
        <label>城市<input maxLength={200} value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} /></label>
        <label>来源链接<input type="url" maxLength={2000} placeholder="https://招聘官网/岗位" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} /></label>
        <label>来源状态<select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
          <option value="unknown">状态待核对</option><option value="open">来源标记在招</option><option value="closed">已关闭</option><option value="reference">参考快照</option>
        </select></label>
        <label className="radar-wide">JD 原文<textarea required minLength={20} maxLength={18000} rows={6} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
        <div className="btn-row radar-wide">
          <ActionButton className="btn primary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy}>{editingId ? '保存新版本' : '保存岗位'}</ActionButton>
          {editingId && <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => { setEditingId(null); setForm(initialForm) }}>取消编辑</ActionButton>}
          <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => fileInput.current?.click()}>导入 JSON / JSONL</ActionButton>
          <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(loadExampleJobs)}>载入岗位示例</ActionButton>
          <a className="btn secondary" href="/data/job-opportunities.example.json" download>下载岗位模板</a>
          <input ref={fileInput} type="file" accept=".json,.jsonl,application/json" hidden aria-label="选择岗位数据文件" onChange={(e) => {
            const file = e.target.files?.[0]; e.target.value = ''
            if (file) void perform(async () => {
              if (file.size > 1_900_000) throw new Error('文件超过 1.9MB，请分批导入。')
              await importRows(parseJobImport(await file.text()))
            })
          }} />
        </div>
      </form>
      <p className="muted">请导入包含完整 JD 的 JSON 或 JSONL。</p>
    </details>

    <details className="radar-import">
      <summary>连接本机 AI Career Radar</summary>
      <p>先独立启动 AI Career Radar（默认本机 8787 端口），再读取岗位。此处只读它已保存的数据，刷新官网数据请在雷达中操作。</p>
      <div className="btn-row">
        <input aria-label="搜索雷达岗位" placeholder="公司、岗位或技术关键词" value={radarQuery} onChange={(e) => setRadarQuery(e.target.value)} />
        <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(() => browseRadar())}>读取雷达岗位</ActionButton>
      </div>
      {radar && <>
        <p className="muted">{radar.notice}</p>
        {!radar.items.length && <p>当前筛选没有岗位；这不代表市场上没有岗位。</p>}
        <ul className="radar-upstream">{radar.items.map((job) => <li key={job.id}>
          <label><input type="checkbox" checked={radarIds.includes(job.id)} disabled={busy} onChange={(e) => setRadarIds(e.target.checked ? [...radarIds, job.id] : radarIds.filter((id) => id !== job.id))} />
            <span><strong>{job.title}</strong> · {job.company} · {job.location || '地点未知'}<small>上次来源观察：{job.last_seen_at || '未知'}</small></span>
          </label>
        </li>)}</ul>
        <div className="btn-row">
          <ActionButton type="button" className="btn primary" disabledReason={busy?'正在导入，请稍候。':!radarIds.length?'请先选择要导入的岗位。':'一次最多导入 20 个岗位。'} disabled={busy || !radarIds.length || radarIds.length > 20} onClick={() => void perform(async () => {
            const result = await jobsRequest<ImportResult>('/radar/import', { ids: radarIds })
            await reload(result.items[0]?.id); setRadarIds([]); setMessage(importMessage(result))
          })}>导入选中岗位（{radarIds.length}/20）</ActionButton>
          <ActionButton type="button" className="btn secondary" disabledReason={busy?'正在读取，请稍候。':'已经是第一页。'} disabled={busy || radar.offset === 0} onClick={() => void perform(() => browseRadar(Math.max(0, radar.offset - 50)))}>上一页</ActionButton>
          <ActionButton type="button" className="btn secondary" disabledReason={busy?'正在读取，请稍候。':'已经是最后一页。'} disabled={busy || radar.offset + 50 >= radar.total} onClick={() => void perform(() => browseRadar(radar.offset + 50))}>下一页</ActionButton>
          <span>第 {Math.floor(radar.offset / 50) + 1} 页 · 共 {radar.total} 条</span>
        </div>
      </>}
    </details>

    </div>
    {library && <>
      <div className="radar-overview" aria-label="全部收藏的来源状态">
        <div><strong>{library.total}</strong><span>个收藏岗位</span></div>
        {(['open','unknown','reference','closed'] as const).map(state => <button type="button" key={state} aria-pressed={sourceFilter === state}
          onClick={() => {setSourceFilter(sourceFilter === state ? 'all' : state);setStatusFilter('all');setDetailOpen(false)}}>
          <span className={'status-dot '+state} />{JOB_STATUS[state]}<strong>{library.stats[state]}</strong>
        </button>)}
      </div>

    </>}
    <div className="radar-findbar">
      <label className="work-search"><Icon name="search" /><input aria-label="筛选收藏岗位" placeholder="搜索岗位、公司、城市或技能" value={query} onChange={e => {setQuery(e.target.value);setDetailOpen(false)}}
        onKeyDown={e => {if(e.key === 'Escape') setQuery('')}} />
        {query && <button type="button" aria-label="清除岗位搜索" onClick={() => setQuery('')}><Icon name="close" /></button>}
      </label>
      <label className="radar-sort"><span>排序</span><select aria-label="岗位排序" value={sort} onChange={e => setSort(e.target.value as JobSort)}><option value="match">为你推荐（语义与兴趣）</option><option value="newest">最近导入</option><option value="company">公司名称</option></select></label>
      <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(() => reload())}><Icon name="refresh" />重读本地列表</ActionButton>
    </div>
    <div className="official-radar-filters">
      <label>官网来源<select aria-label="官网来源" value={officialSource} onChange={e => { setOfficialSource(e.target.value); setDetailOpen(false) }}>
        <option value="">全部来源</option>{Object.entries(OFFICIAL_SOURCES).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select></label>
      <label>提醒<select aria-label="提醒" value={inboxFilter} onChange={e => { setInboxFilter(e.target.value); setDetailOpen(false) }}>
        <option value="">全部岗位</option><option value="new">新增岗位</option><option value="unread">未读岗位</option>
      </select></label>
      <label>匹配等级<select aria-label="匹配等级" value={matchLevel} onChange={e => { setMatchLevel(e.target.value); setDetailOpen(false) }}>
        <option value="">全部等级</option>{Object.entries(MATCH_LABELS).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select></label>
      <label>招聘类型<select aria-label="招聘类型" value={recruitmentType} onChange={e => { setRecruitmentType(e.target.value); setDetailOpen(false) }}>
        <option value="">全部类型</option>{Array.from(new Set(allJobs.map(job => job.recruitment_type).filter(Boolean))).sort().map(type => <option key={type}>{type}</option>)}
      </select></label>
    </div>
    <div className="radar-scope-row">
      <div className="scope-switch" aria-label="收藏范围">{([
        ['active','未归档'],['preparing','准备中'],['archived','已归档'],['all','全部']
      ] as const).map(([id,label]) => <button type="button" key={id} aria-pressed={statusFilter === id} onClick={() => {setStatusFilter(id);setDetailOpen(false)}}>{label}</button>)}</div>
      <span className="radar-result-count" role="status">{filtered.length} 个结果{sourceFilter !== 'all' && ' · '+JOB_STATUS[sourceFilter]}</span>
      {(query || statusFilter !== 'active' || sourceFilter !== 'all' || officialSource || inboxFilter || matchLevel || recruitmentType) && <button type="button" className="text-action" onClick={resetFilters}>重置筛选</button>}
    </div>
    <div className="radar-layout">
      <nav className="radar-job-list" aria-label="收藏岗位">
        {!library && !error && <p>正在读取收藏…</p>}
        {library && !filtered.length && <div className="radar-empty"><Icon name="compass" /><h3>{library.items.length ? '没有匹配的岗位' : '把想投的岗位，放在这里。'}</h3>
          <p>{library.items.length ? '试试减少关键词，或重置筛选条件。' : '粘贴招聘原文即可收藏，再对照经历与证据。'}</p>
          <button type="button" className="btn secondary" onClick={library.items.length ? resetFilters : openForm}>{library.items.length ? '重置筛选' : '添加第一个岗位'}</button>
          {!library.items.length && <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(loadExampleJobs)}>载入岗位示例</ActionButton>}
        </div>}
        {filtered.map((job) => <ActionButton type="button" key={job.id} disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} aria-current={selected?.id === job.id ? 'true' : undefined} className={'radar-job '+(selected?.id === job.id ? 'selected' : '')} onClick={() => {
          revision.current += 1; setSelectedId(job.id); setAnalysis(null); setVersions(null);setDetailTab('description');setDetailOpen(true)
          requestAnimationFrame(() => detailHeading.current?.focus({preventScroll:true}))
        }}>
          <span className="radar-job-company">{job.company}<span className={'job-state '+job.status}>{job.stage === 'preparing' ? '准备中' : JOB_STATUS[job.status]}</span></span>
          <strong>{job.title}</strong><span className="radar-job-location"><Icon name="pin" />{job.location || '地点未知'}</span>
          <span className="radar-job-meta">
            {job.recommendation_score!==undefined&&<span className="job-match-label">推荐相关度 {job.recommendation_score.toFixed(0)}</span>}
            {job.match_level && <span className={'job-match-label ' + job.match_level}>
              {MATCH_LABELS[job.match_level]}{job.match_score != null && ` · ${job.match_score} 分`}
            </span>}
            {job.is_new && <span>新增</span>}{job.unread && <span>未读</span>}
            {job.published_at && <time dateTime={job.published_at}>{job.published_at.slice(0, 10)}</time>}
          </span>
          <span className="radar-job-foot"><span>{job.factors.slice(0,3).map(f => f.label).join(' / ') || '查看岗位详情'}</span><span>v{job.version}<Icon name="chevron" /></span></span>
        </ActionButton>)}
      </nav>
      {library && !filtered.length && <div className="radar-next-guide"><h3>从岗位到申请，一步一步来。</h3><ol>
        <li><strong>收藏目标岗位</strong><p>保留完整原文和来源，之后随时回看。</p></li>
        <li><strong>先看证据缺口</strong><p>对照自己的经历，找到需要补充的材料。</p></li>
        <li><strong>准备有依据的表达</strong><p>整理草稿，润色后逐项核验，再由你确认。</p></li>
      </ol><Link to="/vault" className="text-action">整理我的经历<Icon name="arrow" /></Link></div>}
      {selected && <article className="radar-detail">
        <button type="button" className="radar-mobile-back text-action" onClick={() => {setDetailOpen(false);requestAnimationFrame(() => document.querySelector<HTMLButtonElement>('.radar-job.selected')?.focus())}}><Icon name="back" />返回岗位列表</button>
        <div className="radar-detail-heading"><span className="company-monogram" aria-hidden="true">{selected.company.slice(0,1)}</span><div><h3 ref={detailHeading} tabIndex={-1}>{selected.title}</h3><p>{selected.company} · {selected.location || '地点未知'}</p></div></div>
        <div className="radar-tags"><span className="badge muted">{JOB_STATUS[selected.status]}</span><span className="badge muted">{JOB_STAGE[selected.stage]}</span><span className="badge muted">版本 {selected.version}</span></div>
        {(selected.salary || selected.internship_schedule || selected.graduation_window) && <dl className="job-structured-facts">
          {selected.salary && <div><dt>薪资</dt><dd>{selected.salary.min}–{selected.salary.max}
            {' '}{selected.salary.currency === 'CNY' ? '元' : selected.salary.currency}
            /{({hour:'小时',day:'天',week:'周',month:'月',year:'年'} as Record<string,string>)[selected.salary.unit]}</dd></div>}
          {selected.internship_schedule && <div><dt>实习安排</dt><dd>{selected.internship_schedule.days_per_week} 天/周 · {selected.internship_schedule.duration_months} 个月</dd></div>}
          {selected.graduation_window && <div><dt>毕业窗口</dt><dd>{selected.graduation_window.class_year ? selected.graduation_window.class_year + ' 届 · ' : ''}
            {selected.graduation_window.start_date} 至 {selected.graduation_window.end_date}</dd></div>}
        </dl>}
        <div className="radar-provenance">
          <span>来源：{({manual:'手动收藏',local_edit:'本地编辑',radar:'本机雷达',peer_benchmark:'参考样例',official:'公司官网',fictional_example:'课程示例'} as Record<string,string>)[selected.source_kind] || '来源记录'}</span>
          <span>最近更新：{formatJobTime(selected.last_changed_at || selected.imported_at)}</span>
          {selected.source_observed_at && <span>官网观察：{formatJobTime(selected.source_observed_at)}</span>}
          {selected.url && <a className="radar-source" href={selected.url} target="_blank" rel="noreferrer">查看招聘原文 ↗</a>}
        </div>
        {match && <section className="radar-job-match" aria-label="岗位匹配">
          <header><h4>经历匹配</h4>
            <span className={'job-match-label ' + match.level}>{MATCH_LABELS[match.level]}{match.score != null && ` · ${match.score} / 100`}</span>
          </header>
          <p>按已保存的经历和技能评分。</p>
          <div className="radar-match-reasons">
            {match.reasons.length > 0 && <div><h5>有相关记录</h5><ul>{match.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div>}
            {match.missing.length > 0 && <div><h5>需要核对</h5><ul>{match.missing.slice(0, 3).map(reason => <li key={reason}>{reason}</li>)}</ul>
              {match.missing.length > 3 && <details><summary>其余 {match.missing.length - 3} 项</summary>
                <ul>{match.missing.slice(3).map(reason => <li key={reason}>{reason}</li>)}</ul>
              </details>}
            </div>}
          </div>
          <div className="btn-row">
            {match.missing.includes('缺少已保存的简历或经历') && <Link to="/" className="btn secondary">导入简历或载入模板</Link>}
            {selected.source_id && <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(async () => {
              await jobsRequest('/alerts/read', { job_id: selected.id, unread: !selected.unread })
              await reload(selected.id)
              window.dispatchEvent(new Event('applyguard:official-jobs-updated'))
            })}>{selected.unread ? '标记岗位已读' : '重新提醒'}</ActionButton>}
            {library?.ai_matching && (selected.match_level === 'high' || selected.match_level === 'medium') && <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(async () => {
              const response = await jobsRequest<{match: JobMatch}>('/' + selected.id + '/match', { semantic: true })
              setSemantic({id: selected.id, hash: selected.content_hash, result: response.match})
            })}>请求语义解释</ActionButton>}
          </div>
          {semantic?.id === selected.id && semantic.hash === selected.content_hash && <p>{semantic.result.ai_explanation ?? '本次使用本地规则解释。'}{semantic.result.ai_score !== undefined && ' · 模型评分 ' + semantic.result.ai_score}</p>}
        </section>}
        <div className="btn-row">
          <ActionButton type="button" className="btn primary" disabledReason={busy?'正在准备，请稍候。':scenario!=='live'?'预录示例不能创建真实申请，请切换到本地后端。':selected.details_available===false?'官网完整要求尚未读取，请先核对官方详情。':'岗位已关闭、归档或仅为参考快照，可先恢复合适的岗位。'} disabled={busy || scenario !== 'live' || !canPrepareJob(selected)} onClick={() => void perform(async () => {
            const sameJob = activeJobId === selected.id || workflow?.target_job?.id === selected.id
            if (!sameJob && (workflow?.resume_claims.length || Object.keys(reviewDrafts).length) &&
                !window.confirm('更换岗位会结束当前申请，并清除本次申请的正文和暂存编辑。继续更换？')) return
            if (selected.stage !== 'preparing') await jobsRequest(`/${selected.id}/stage`, { stage: 'preparing' })
            if (activeJobId !== selected.id && workflow?.target_job?.id !== selected.id) setWorkflow(null)
            setActiveJobId(selected.id)
            navigate(`/jd?job=${selected.id}`)
          })}>用此岗位准备申请</ActionButton>
          <ActionButton type="button" className="btn secondary" disabledReason={busy?'正在检查，请稍候。':'官网完整职责和要求尚未读取，请先核对官方详情。'} disabled={busy || selected.details_available === false} onClick={() => void perform(analyze)}>检查证据缺口</ActionButton>
          <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => {
            setEditingId(selected.id); setForm({ title: selected.title, company: selected.company,
              location: selected.location, url: selected.url, status: selected.status, description: selected.description })
            openForm()
          }}>编辑 JD</ActionButton>
          <ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(async () => {
            const restoring = selected.stage === 'archived'
            await jobsRequest(`/${selected.id}/stage`, { stage: restoring ? 'saved' : 'archived' })
            await reload(selected.id)
            setStatusFilter(current => current === 'all' ? current : restoring ? 'active' : 'archived')
            setMessage(restoring ? `已恢复收藏「${selected.title}」。` : `已归档「${selected.title}」，可在「已归档」中恢复。`)
          })}>{selected.stage === 'archived' ? '恢复收藏' : '归档'}</ActionButton>
          <ActionButton type="button" className="btn ghost-danger" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => {
            const linked = activeJobId === selected.id || workflow?.target_job?.id === selected.id
            const impact = linked ? '\n当前申请正文会保留。要继续使用岗位原文，请到「岗位说明」解除关联。' : ''
            if (!window.confirm(`永久删除「${selected.title}」及其岗位版本记录？${impact}`)) return
            void perform(async () => {
              await jobsRequest(`/${selected.id}`, undefined, 'DELETE')
              await reload()
              if (editingId === selected.id) {
                setEditingId(null)
                setForm(initialForm)
                if (formPanel.current) formPanel.current.open = false
              }
              setDetailOpen(false)
              setDetailTab('description')
              setMessage(`已删除「${selected.title}」。`)
            })
          }}>删除岗位</ActionButton>
        </div>
        {!canPrepareJob(selected) && <div className="callout warn">{selected.details_available === false ? <><p>官网只返回了岗位列表，尚未获取完整职责和要求。请打开招聘原文，复制职责和要求后补充到岗位说明。</p><button type="button" className="btn primary" onClick={()=>{setEditingId(selected.id);setForm({title:selected.title,company:selected.company,location:selected.location,url:selected.url,status:selected.status,description:selected.description});openForm()}}>补充岗位要求</button>{selected.url&&<a className="btn secondary" href={selected.url} target="_blank" rel="noreferrer">打开招聘原文 ↗</a>}</> : <p>已归档、已关闭或参考快照仅供查看，不能从这里准备申请。</p>}</div>}
        <Tabs id="job-tab" label="岗位详情视图" panelId="job-detail-panel" value={detailTab} onChange={setDetailTab} items={[{id:'description',label:'岗位原文'},{id:'analysis',label:'证据预检'},{id:'versions',label:'版本记录'}]} />
        <div id="job-detail-panel" role="tabpanel" aria-labelledby={'job-tab-'+detailTab} tabIndex={0}>
        <section className="radar-recommendation" aria-label="岗位推荐依据"><h4>为什么推荐</h4><ul>{selected.recommendation_reasons?.map(reason=><li key={reason}>{reason}</li>)}</ul><p>兴趣反馈只影响本机推荐，不会投递，也不会更改你的简历。</p><div className="btn-row">
          <ActionButton type="button" className="btn secondary" aria-pressed={selected.interest===1} disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={()=>void perform(async()=>{await jobsRequest('/'+selected.id+'/feedback',{interest:selected.interest===1?0:1});await reload(selected.id)})}>{selected.interest===1?'取消感兴趣':'感兴趣'}</ActionButton>
          <ActionButton type="button" className="btn secondary" aria-pressed={selected.interest===-1} disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={()=>void perform(async()=>{await jobsRequest('/'+selected.id+'/feedback',{interest:selected.interest===-1?0:-1});await reload(selected.id)})}>{selected.interest===-1?'恢复正常推荐':'减少此类推荐'}</ActionButton>
        </div></section>
        {detailTab === 'description' && <div><h4>岗位说明</h4><pre className="radar-jd">{selected.description}</pre>
        <details className="radar-factor-panel" key={selected.id}>
          <summary>技术与能力标签（{selected.factors.length}）</summary>
          <div className="radar-factor-content">
            <div className="radar-tags">{selected.factors.map(factor => <span className="badge muted" key={factor.slug}>{factor.label} · {factor.category}</span>)}</div>
            <p className="muted">标签仅标记原文关键词。</p>
            {Array.from(excerpts, ([quote, labels]) => <div key={quote} className="radar-factor">
              <strong>{labels.join(' · ')}</strong><blockquote>{quote}</blockquote>
            </div>)}
            {!selected.factors.length && <p>暂无可识别的标签。</p>}
          </div>
        </details>
        </div>}
        {detailTab === 'versions' && <div className="radar-versions"><h4>来源版本记录</h4>{versions && versionsFor === selected.id ? versions.map(v => <details key={v.version}><summary>v{v.version} · {new Date(v.imported_at).toLocaleString()} · {JOB_STATUS[v.job.status]}</summary><pre className="radar-jd">{v.job.description}</pre></details>) : <div className="radar-inline-empty"><Icon name="history" /><p>对照每次导入和修改，确认当前使用的原文。</p><ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(async () => {const data = await jobsRequest<{items:NonNullable<typeof versions>}>('/'+selected.id+'/versions');setVersions(data.items);setVersionsFor(selected.id)})}>读取版本记录</ActionButton></div>}</div>}
        {detailTab === 'analysis' && !freshAnalysis && <div className="radar-inline-empty"><Icon name="shield" /><h4>先看看，还缺哪些证据。</h4><p>按当前经历进行规则预检，不调用付费模型。预检不替代陈述核验。</p><ActionButton type="button" className="btn secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={busy} onClick={() => void perform(analyze)}>开始证据预检</ActionButton></div>}
        {detailTab === 'analysis' && freshAnalysis && analysis && <section className="radar-analysis" aria-label="证据缺口结果">
          <div className="coverage-heading"><div><span>有已核验证据支持</span><strong>{analysis.supported}<small> / {analysis.total} 条要求</small></strong></div><Link to="/evidence" className="btn secondary">补充证据<Icon name="arrow" /></Link></div><p className="muted">{analysis.notice}</p>
          {!analysis.has_resume && <p className="callout warn">尚未提供有效经历，请先 <Link to="/">导入简历</Link> 或完善经历库。这里不会使用演示种子替代你的经历。</p>}
          {!analysis.total && <p className="callout warn">{analysis.excluded ? '当前没有可匹配的职责或任职条件。' : '规则未识别出要求，请人工检查完整 JD；这不表示没有要求。'}</p>}
          <div className="scope-switch" aria-label="预检结果筛选">{[['all','全部'],['missing','待补证'],['supported','已支持']].map(([id,label]) => <button type="button" key={id} aria-pressed={coverageFilter === id} onClick={() => setCoverageFilter(id)}>{label}</button>)}</div>
          {!visibleRequirements.length && <p className="radar-inline-empty">此分类下没有要求。可切换到“全部”查看预检结果。</p>}
          {visibleRequirements.map((req) => <div className="item-block" key={req.requirement_id}>
            <span className={`badge ${req.coverage === 'SUPPORTED' ? 'ok' : 'warn'}`}>{req.coverage === 'SUPPORTED' ? '有已核验证据支持' : ({ NEEDS_EVIDENCE: '有相关经历，仍需补证', NO_MATCH: '未找到支持证据', PROFILE_REPORTED: '个人资料对照', REVIEW_REQUIRED: '需人工核对' })[req.coverage]}</span>
            <span className="muted"> · {zhLookup(ZH_REQ_TYPE, req.type)}</span><p>{req.text}</p>
            <ProfileCheckList checks={analysis.profile_checks?.[req.requirement_id]} />
            {!!req.related_projects?.length && <details><summary>相关经历 · {req.related_projects.length} 项</summary>{req.related_projects.map((p,i) => <p key={i}><strong>{p.title}</strong> · {p.kind === "framework" ? "框架待确认" : p.terms.join("、")}<br/>{p.quote}</p>)}</details>}
            {req.evidence_ids.length > 0 && <p className="muted">证据：{req.evidence_ids.join('、')}</p>}
            {req.notes.map((note, i) => <p className="muted" key={i}>{zhText(note)}</p>)}
          </div>)}
          <Link to="/evidence" className="btn secondary">整理与关联证据</Link>
        </section>}
        </div>
      </article>}
    </div>
    {library && <div className="radar-secondary">      <details className="radar-import">
        <summary>收藏岗位的高频需求（{library.stats.analyzed_jobs} 个岗位）</summary>
        <p className="muted">{library.notice}</p>
        <div className="radar-tags">{library.stats.factors.map((f) => <span className="badge muted" key={f.slug}>{f.label} · {f.jobs} 个岗位</span>)}</div>
        {!library.stats.factors.length && <p>暂无可统计的标签。</p>}
      </details></div>}
  </section>
}
