import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiClient } from '../api/client'
import { analyzeOpportunity, jobsRequest, type ImportResult, type JobAnalysis, type JobLibrary, type RadarPage } from '../api/jobs'
import { ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { canPrepareJob, importMessage, JOB_STAGE, JOB_STATUS, parseJobImport } from '../jobs'
import { zhText, ZH_REQ_TYPE, zhLookup } from '../i18n'

const initialForm = { title: '', company: '', location: '', url: '', status: 'unknown', description: '' }

export function JobRadarPage() {
  const navigate = useNavigate()
  const { resumeForm, setWorkflow, scenario } = useDemo()
  const [library, setLibrary] = useState<JobLibrary | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('active')
  const [form, setForm] = useState(initialForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const formPanel = useRef<HTMLDetailsElement>(null)
  const [analysis, setAnalysis] = useState<(JobAnalysis & { resumeSignature: string }) | null>(null)
  const resumeSignature = JSON.stringify(resumeForm)
  const [versions, setVersions] = useState<Array<{ version: number; imported_at: string; job: { description: string; status: string } }> | null>(null)
  const [radar, setRadar] = useState<RadarPage | null>(null)
  const [radarQuery, setRadarQuery] = useState('')
  const [radarIds, setRadarIds] = useState<number[]>([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const revision = useRef(0)
  const fileInput = useRef<HTMLInputElement>(null)
  const selected = library?.items.find((job) => job.id === selectedId)

  async function reload(preferId?: string) {
    const data = await jobsRequest<JobLibrary>()
    setLibrary(data)
    setSelectedId((prev) => preferId ?? (data.items.some((job) => job.id === prev) ? prev : data.items[0]?.id ?? ''))
    revision.current += 1
    setAnalysis(null)
    setVersions(null)
  }
  useEffect(() => {
    let cancelled = false
    void jobsRequest<JobLibrary>().then((data) => {
      if (!cancelled) { setLibrary(data); setSelectedId(data.items[0]?.id ?? '') }
    }).catch((e) => { if (!cancelled) setError(String(e.message)) })
    return () => { cancelled = true }
  }, [])
  useEffect(() => {
    revision.current += 1
    const invalidate = () => { revision.current += 1; setAnalysis(null) }
    window.addEventListener('applyguard:evidence-changed', invalidate)
    window.addEventListener('storage', invalidate)
    return () => { window.removeEventListener('applyguard:evidence-changed', invalidate); window.removeEventListener('storage', invalidate) }
  }, [resumeForm, selectedId])

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
    if (version === revision.current) setAnalysis({ ...report, resumeSignature })
    else setMessage('经历或证据已变化，请重新预检查。')
  }
  const filtered = (library?.items ?? []).filter((job) =>
    (statusFilter === 'all' || (statusFilter === 'active' ? job.stage !== 'archived' : job.stage === 'archived')) &&
    `${job.title} ${job.company} ${job.location} ${job.description}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))

  return <section className="panel radar-page">
    <header className="panel-head">
      <p className="eyebrow">机会发现 → 证据匹配 → 可信申请</p>
      <h2>岗位雷达</h2>
      <p>收藏目标岗位，查看需求与证据缺口，再进入申请流程。预检查使用本机规则，不调用付费模型。</p>
    </header>
    {scenario !== 'live' && <p className="callout warn">当前是预录演示场景。岗位库仍显示本机数据；准备真实岗位时请先在顶部切换「正常·在线」。</p>}
    {error && <ErrorState message={error} />}
    {message && <p className="callout ok" role="status">{message}</p>}
    {busy && <LoadingState label="正在处理岗位数据…" />}

    <details className="radar-import" ref={formPanel}>
      <summary>{editingId ? '编辑岗位（保存为新版本）' : '添加岗位 / 导入 JSON、JSONL'}</summary>
      <form className="radar-form" onSubmit={(e) => { e.preventDefault(); void perform(async () => {
        if (editingId) {
          const result = await jobsRequest<{ job: { id: string } }>(`/${editingId}/edit`, { job: form })
          await reload(result.job.id); setMessage('岗位已保存为新版本，旧工作流已失效。')
        } else await importRows([form])
        setForm(initialForm); setEditingId(null)
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
          <button className="btn primary" disabled={busy}>{editingId ? '保存新版本' : '保存岗位'}</button>
          {editingId && <button type="button" className="btn secondary" disabled={busy} onClick={() => { setEditingId(null); setForm(initialForm) }}>取消编辑</button>}
          <button type="button" className="btn secondary" disabled={busy} onClick={() => fileInput.current?.click()}>导入 JSON / JSONL</button>
          <a className="btn secondary" href="/data/job-opportunities.example.json" download>下载虚构岗位模板</a>
          <input ref={fileInput} type="file" accept=".json,.jsonl,application/json" hidden aria-label="选择岗位数据文件" onChange={(e) => {
            const file = e.target.files?.[0]; e.target.value = ''
            if (file) void perform(async () => {
              if (file.size > 1_900_000) throw new Error('文件超过 1.9MB，请分批导入。')
              await importRows(parseJobImport(await file.text()))
            })
          }} />
        </div>
      </form>
      <p className="muted">同一来源岗位再次导入会去重或建立新版本。需要完整 JD；雷达的列表 CSV 不含完整详情，不能直接用于申请。</p>
    </details>

    <details className="radar-import">
      <summary>连接本机 AI Career Radar</summary>
      <p>先独立启动 AI Career Radar（默认本机 8787 端口），再读取岗位。此处只读它已保存的数据，刷新官网数据请在雷达中操作。</p>
      <div className="btn-row">
        <input aria-label="搜索雷达岗位" placeholder="公司、岗位或技术关键词" value={radarQuery} onChange={(e) => setRadarQuery(e.target.value)} />
        <button type="button" className="btn secondary" disabled={busy} onClick={() => void perform(() => browseRadar())}>读取雷达岗位</button>
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
          <button type="button" className="btn primary" disabled={busy || !radarIds.length || radarIds.length > 20} onClick={() => void perform(async () => {
            const result = await jobsRequest<ImportResult>('/radar/import', { ids: radarIds })
            await reload(result.items[0]?.id); setRadarIds([]); setMessage(importMessage(result))
          })}>导入选中岗位（{radarIds.length}/20）</button>
          <button type="button" className="btn secondary" disabled={busy || radar.offset === 0} onClick={() => void perform(() => browseRadar(Math.max(0, radar.offset - 50)))}>上一页</button>
          <button type="button" className="btn secondary" disabled={busy || radar.offset + 50 >= radar.total} onClick={() => void perform(() => browseRadar(radar.offset + 50))}>下一页</button>
          <span>第 {Math.floor(radar.offset / 50) + 1} 页 · 共 {radar.total} 条</span>
        </div>
      </>}
    </details>

    {library && <>
      <div className="radar-metrics">
        <span><strong>{library.stats.open}</strong> 来源标记在招</span><span><strong>{library.stats.unknown}</strong> 状态待核对</span>
        <span><strong>{library.stats.reference}</strong> 参考快照</span><span><strong>{library.stats.closed}</strong> 已关闭</span>
      </div>
      <details className="radar-import">
        <summary>收藏岗位的高频需求（{library.stats.analyzed_jobs} 个岗位）</summary>
        <p className="muted">{library.notice}</p>
        <div className="radar-tags">{library.stats.factors.map((f) => <span className="badge muted" key={f.slug}>{f.label} · {f.jobs} 个岗位</span>)}</div>
        {!library.stats.factors.length && <p>暂无可统计的标签。</p>}
      </details>
    </>}
    <div className="btn-row">
      <input aria-label="筛选收藏岗位" placeholder="筛选公司、城市、岗位、技能" value={query} onChange={(e) => setQuery(e.target.value)} />
      <select aria-label="收藏范围" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="active">未归档</option><option value="archived">已归档</option><option value="all">全部收藏</option></select>
      <button type="button" className="btn secondary" disabled={busy} onClick={() => void perform(() => reload())}>刷新收藏</button>
    </div>
    <div className="radar-layout">
      <nav className="radar-job-list" aria-label="收藏岗位">
        {!library && !error && <p>正在读取收藏…</p>}
        {library && !filtered.length && <p>暂无符合条件的收藏。可展开上方入口添加岗位。</p>}
        {filtered.map((job) => <button type="button" key={job.id} disabled={busy} className={`radar-job ${selectedId === job.id ? 'selected' : ''}`} onClick={() => { revision.current += 1; setSelectedId(job.id); setAnalysis(null); setVersions(null) }}>
          <strong>{job.title}</strong><span>{job.company} · {job.location || '地点未知'}</span>
          <small>{JOB_STATUS[job.status]} · {JOB_STAGE[job.stage]} · v{job.version}</small>
        </button>)}
      </nav>
      {selected && filtered.some((job) => job.id === selected.id) && <article className="radar-detail">
        <h3>{selected.title}</h3><p>{selected.company} · {selected.location || '地点未知'}</p>
        <div className="radar-tags"><span className="badge muted">{JOB_STATUS[selected.status]}</span><span className="badge muted">{JOB_STAGE[selected.stage]}</span><span className="badge muted">版本 {selected.version}</span></div>
        <p className="muted">来源：{selected.source_kind} · 导入：{new Date(selected.imported_at).toLocaleString()}<br />来源观察时间：{selected.source_observed_at || '未知；导入时间不代表官网核验时间'}</p>
        {selected.url && <p><a className="radar-source" href={selected.url} target="_blank" rel="noreferrer">查看原始招聘页面 ↗</a></p>}
        <div className="btn-row">
          <button type="button" className="btn primary" disabled={busy || scenario !== 'live' || !canPrepareJob(selected)} onClick={() => void perform(async () => {
            await jobsRequest(`/${selected.id}/stage`, { stage: 'preparing' })
            setWorkflow(null); navigate(`/jd?job=${selected.id}`)
          })}>用此岗位准备申请</button>
          <button type="button" className="btn secondary" disabled={busy} onClick={() => void perform(analyze)}>检查证据缺口</button>
          <button type="button" className="btn secondary" disabled={busy} onClick={() => {
            setEditingId(selected.id); setForm({ title: selected.title, company: selected.company,
              location: selected.location, url: selected.url, status: selected.status, description: selected.description })
            if (formPanel.current) { formPanel.current.open = true; formPanel.current.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
          }}>编辑 JD</button>
          <button type="button" className="btn secondary" disabled={busy} onClick={() => void perform(async () => {
            await jobsRequest(`/${selected.id}/stage`, { stage: selected.stage === 'archived' ? 'saved' : 'archived' }); await reload(selected.id)
          })}>{selected.stage === 'archived' ? '恢复收藏' : '归档'}</button>
          <button type="button" className="btn secondary" disabled={busy} onClick={() => void perform(async () => {
            const data = await jobsRequest<{ items: NonNullable<typeof versions> }>(`/${selected.id}/versions`); setVersions(data.items)
          })}>查看版本</button>
        </div>
        {!canPrepareJob(selected) && <p className="callout warn">已归档、已关闭或参考快照仅供查看，不能从这里准备申请。</p>}
        <details className="radar-import" open><summary>JD 原文</summary><pre className="radar-jd">{selected.description}</pre></details>
        <details className="radar-import"><summary>技术与能力标签（{selected.factors.length}）</summary>
          <p className="muted">按原文词组命中，含优先项或否定表达；标签不判断是否为硬性条件。</p>
          {selected.factors.map((f) => <div key={f.slug} className="radar-factor"><strong>{f.label} · {f.category}</strong>{f.evidence.map((ev, i) => <blockquote key={i}>{ev.text}</blockquote>)}</div>)}
          {!selected.factors.length && <p>规则暂无命中，请以原文为准。</p>}
        </details>
        {versions && <details className="radar-import" open><summary>来源版本记录</summary>{versions.map((v) => <details key={v.version}><summary>v{v.version} · {new Date(v.imported_at).toLocaleString()} · {JOB_STATUS[v.job.status]}</summary><pre className="radar-jd">{v.job.description}</pre></details>)}</details>}
        {analysis && analysis.resumeSignature === resumeSignature && analysis.job_id === selected.id && analysis.content_hash === selected.content_hash && <section className="radar-analysis" aria-label="证据缺口结果">
          <h3>证据覆盖 {analysis.supported} / {analysis.total}</h3><p className="muted">{analysis.notice}</p>
          {!analysis.has_resume && <p className="callout warn">尚未提供有效经历，请先 <Link to="/">导入简历</Link> 或完善经历库。这里不会使用演示种子替代你的经历。</p>}
          {!analysis.total && <p className="callout warn">规则未识别出要求，请人工检查完整 JD；这不表示没有要求。</p>}
          {analysis.requirements.map((req) => <div className="item-block" key={req.requirement_id}>
            <span className={`badge ${req.coverage === 'SUPPORTED' ? 'ok' : 'warn'}`}>{req.coverage === 'SUPPORTED' ? '有已核验证据支持' : req.coverage === 'NEEDS_EVIDENCE' ? '有相关经历，仍需补证' : '未找到支持证据'}</span>
            <span className="muted"> · {zhLookup(ZH_REQ_TYPE, req.type)}</span><p>{req.text}</p>
            {req.evidence_ids.length > 0 && <p className="muted">证据：{req.evidence_ids.join('、')}</p>}
            {req.notes.map((note, i) => <p className="muted" key={i}>{zhText(note)}</p>)}
          </div>)}
          <Link to="/evidence" className="btn secondary">整理与关联证据</Link>
        </section>}
      </article>}
    </div>
  </section>
}
