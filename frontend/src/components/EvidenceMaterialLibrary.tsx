import { useRef, useState, type ReactNode } from 'react'
import type { EvidenceSearchMatch, EvidenceSourceFile, ResumeMatchItem } from '../api/types'
import { materialFolder, materialName, materialStatus, materialType } from '../evidence/materials'

type DetailTab = 'original' | 'text' | 'fields'
type Props = {
  files: EvidenceSourceFile[]
  rows: ResumeMatchItem[]
  selectedFileId: string
  workspaceName: string
  busy: boolean
  imports: ReactNode
  settings: ReactNode
  notice: ReactNode
  onSelect: (file: EvidenceSourceFile) => void
  onFocusRow: (row: ResumeMatchItem) => void
  onSearch: (query: string) => Promise<{ matches: EvidenceSearchMatch[]; error?: string }>
  renderDetail: (file: EvidenceSourceFile, tab: DetailTab) => ReactNode
}

export function EvidenceMaterialLibrary(props: Props) {
  const [query, setQuery] = useState('')
  const [type, setType] = useState('all')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [tab, setTab] = useState<DetailTab>('original')
  const [hits, setHits] = useState<EvidenceSearchMatch[] | null>(null)
  const [searchBusy, setSearchBusy] = useState(false)
  const [searchError, setSearchError] = useState('')
  const searchVersion = useRef(0)
  const inspectorRef = useRef<HTMLElement | null>(null)
  const filtered = props.files.filter((file) => {
    if (type !== 'all' && materialType(file) !== type) return false
    if (status !== 'all' && materialStatus(file).key !== status) return false
    if (hits) return hits.some((hit) => hit.file_id === file.file_id)
    return [file.relative_path, file.ocr_text_preview, ...Object.values(file.normalized_fields || {})]
      .join(' ').toLowerCase().includes(query.trim().toLowerCase())
  })
  const totalPages = Math.max(1, Math.ceil(filtered.length / 8))
  const currentPage = Math.min(page, totalPages)
  const visible = filtered.slice((currentPage - 1) * 8, currentPage * 8)
  const selected = props.files.find((file) => file.file_id === props.selectedFileId)
  const related = selected?.evidence_id ? props.rows.filter((row) => row.evidence_id === selected.evidence_id) : []
  const choose = (file: EvidenceSourceFile) => {
    setTab('original'); props.onSelect(file)
    requestAnimationFrame(() => {
      if (window.matchMedia('(max-width: 850px)').matches) inspectorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }
  const clear = () => {
    searchVersion.current += 1
    setQuery(''); setType('all'); setStatus('all'); setHits(null); setSearchError(''); setSearchBusy(false); setPage(1)
  }
  const fullTextSearch = async () => {
    if (!query.trim()) return
    const version = ++searchVersion.current
    setSearchBusy(true); setSearchError('')
    try {
      const result = await props.onSearch(query.trim())
      if (version !== searchVersion.current) return
      if (result.error) setSearchError(result.error)
      else { setHits(result.matches); setPage(1) }
    } catch { if (version === searchVersion.current) setSearchError('全文查找失败，请重试。') }
    finally { if (version === searchVersion.current) setSearchBusy(false) }
  }

  return <section className="material-library" id="evidence-files" aria-label="材料库">
    <header className="material-library-head">
      <div><span className="relation-eyebrow">材料管理</span><h3>材料库</h3><p>在这里整理和核对文件，再到上方为经历确认关联。</p></div>
      <a className="btn secondary" href="#evidence-relations">返回经历对照 ↑</a>
    </header>
    <div className="material-import-strip">
      <div><strong>添加证明材料</strong><p>图片、PDF、Word、Markdown · 单个文件不超过 6 MB · 本机识别</p></div>
      {props.imports}
    </div>
    {props.notice}
    <div className="material-library-layout">
      <div className="material-browser">
        <div className="material-list-heading"><strong>文件列表</strong><span>{props.files.length} 份材料</span></div>
        <form className="material-search" onSubmit={(event) => { event.preventDefault(); void fullTextSearch() }}>
          <input className="resume-input" aria-label="搜索材料" placeholder="搜索文件名 / 识别文字" value={query} onChange={(event) => {
            searchVersion.current += 1; setQuery(event.target.value); setHits(null); setSearchError(''); setSearchBusy(false); setPage(1)
          }} />
          <button type="submit" className="btn secondary" disabled={props.busy || searchBusy || !query.trim()}>{searchBusy ? '查找中…' : '全文查找'}</button>
        </form>
        <div className="material-filters">
          <select className="resume-input" aria-label="材料类型" value={type} onChange={(event) => { setType(event.target.value); setPage(1) }}>
            <option value="all">全部类型</option>{['图片', 'PDF', 'Word', 'Markdown', '其他'].map((value) => <option key={value}>{value}</option>)}
          </select>
          <select className="resume-input" aria-label="材料处理状态" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
            <option value="all">全部状态</option><option value="review">待核对</option><option value="manual">需人工查看</option><option value="reviewed">已核对</option><option value="failed">识别失败</option><option value="processing">处理中</option>
          </select>
          {(query || type !== 'all' || status !== 'all') && <button type="button" className="material-reset" onClick={clear}>清除</button>}
        </div>
        <p className="material-result-count" role="status">{hits ? '全文结果' : '当前结果'} · {filtered.length} 份{query && !hits ? ' · 输入后按回车可查找完整原文' : ''}</p>
        {searchError && <p role="alert" className="danger-text">{searchError}</p>}
        <ul className="material-file-list" aria-label="材料文件列表">
          {visible.map((file) => {
            const state = materialStatus(file)
            return <li key={file.file_id}><button type="button" className="material-file-row" aria-current={selected?.file_id === file.file_id ? 'true' : undefined} disabled={props.busy} onClick={() => choose(file)}>
              <span className="material-type-icon" aria-hidden="true">{materialType(file) === 'Markdown' ? 'MD' : materialType(file) === 'Word' ? 'DOC' : materialType(file)}</span>
              <span className="material-file-copy"><strong title={materialName(file.relative_path)}>{materialName(file.relative_path)}</strong>
                <small title={file.relative_path}>{materialFolder(file.relative_path) || '根目录'}</small>
                {hits && <small className="material-hit">{hits.find((hit) => hit.file_id === file.file_id)?.span.raw_text.slice(0, 90)}</small>}
              </span>
              <span className={`material-status material-status-${state.key}`}>{state.label}</span>
            </button></li>
          })}
        </ul>
        {!visible.length && <div className="material-empty"><strong>{props.files.length ? '没有找到材料' : '还没有导入材料'}</strong><p>{props.files.length ? '试试其他关键词，或清除类型与状态筛选。' : '从上方添加文件或文件夹，系统会保存原件并尝试识别文字。'}</p></div>}
        <nav className="material-pagination" aria-label="材料分页">
          <button type="button" className="btn secondary" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>上一页</button>
          <span>{currentPage} / {totalPages}</span>
          <button type="button" className="btn secondary" disabled={currentPage >= totalPages} onClick={() => setPage(currentPage + 1)}>下一页</button>
        </nav>
      </div>
      <section ref={inspectorRef} className="material-inspector" aria-label="所选材料详情">
        {selected ? <>
          <div className="material-inspector-head"><span className="relation-eyebrow">当前材料 · {materialType(selected)}</span><h4>{materialName(selected.relative_path)}</h4><p>{selected.relative_path}</p></div>
          <div className="material-state-note"><span className={`material-status material-status-${materialStatus(selected).key}`}>{materialStatus(selected).label}</span><span>{materialStatus(selected).hint}</span></div>
          {!filtered.some((file) => file.file_id === selected.file_id) && <p className="material-result-count">此材料不在当前筛选结果中，仍保留详情供核对。</p>}
          <div className="material-tabs" role="group" aria-label="材料详情视图">
            {([['original', '原件预览'], ['text', '识别文字'], ['fields', '核对字段']] as const).map(([key, label]) => <button type="button" key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>{label}</button>)}
          </div>
          <div className="material-tab-content" key={`${selected.file_id}:${tab}`}>{props.renderDetail(selected, tab)}</div>
          <div className="material-relations"><strong>与经历的关系</strong>
            {related.length ? related.map((row) => <button type="button" disabled={props.busy} key={`${row.target_type}:${row.target_id}`} onClick={() => props.onFocusRow(row)}>
              <span>{row.status === 'LINKED' ? '已关联' : row.status === 'CONFLICT' ? '存在冲突' : '候选，待确认'}</span><b>{row.label}</b><span aria-hidden="true">↗</span>
            </button>) : <p>当前没有对应的经历候选。可返回上方重新对照经历库。</p>}
            <small>核对材料内容与确认经历关联是两个步骤；核对完成不会自动建立关联。</small>
          </div>
        </> : <div className="material-empty material-empty-detail"><span aria-hidden="true">▤</span><h4>选择一份材料开始查看</h4><p>点击左侧文件，原件、识别文字和核对字段都会显示在这里。</p><ol><li>查看原件</li><li>核对识别内容</li><li>回到上方确认经历关联</li></ol></div>}
      </section>
    </div>
    <details className="material-settings"><summary>工作区设置 <span>{props.workspaceName || '导入时自动创建'}</span></summary>{props.settings}</details>
  </section>
}
