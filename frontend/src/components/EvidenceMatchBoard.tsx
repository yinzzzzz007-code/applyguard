import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { ResumeMatchItem } from '../api/types'

const matchKey = (row: ResumeMatchItem) => `${row.target_type}:${row.target_id}`
const labels: Record<string, string> = {
  LINKED: '已关联', MATCHED: '待确认', NEEDS_CONFIRM: '待确认', CONFLICT: '有冲突',
  MISSING: '缺证据', UNCHECKED: '未对照', REJECTED: '已排除',
}
const filters = [
  ['all', '全部'], ['pending', '待确认'], ['attention', '需补充 / 排查'], ['LINKED', '已关联'],
] as const
type Filter = typeof filters[number][0]
const accepts = (row: ResumeMatchItem, filter: Filter) => filter === 'all'
  || (filter === 'pending' && ['MATCHED', 'NEEDS_CONFIRM'].includes(row.status))
  || (filter === 'attention' && ['MISSING', 'CONFLICT', 'UNCHECKED', 'REJECTED'].includes(row.status))
  || row.status === filter

type Props = {
  rows: ResumeMatchItem[]
  selectedKey: string
  busy: boolean
  sourceDetails: Record<string, { label: string; value: string }[]>
  evidenceExcerpt?: { evidenceId: string; text: string }
  onSelect: (row: ResumeMatchItem) => void
  onConfirm: (row: ResumeMatchItem) => void
  onReject: (row: ResumeMatchItem) => void
  onUnlink: (row: ResumeMatchItem) => void
  onSupplement: (row: ResumeMatchItem) => void
  onDelete: (row: ResumeMatchItem) => void
  onMatch: () => void
  renderEvidence: (row: ResumeMatchItem) => ReactNode
}

export function EvidenceMatchBoard(props: Props) {
  const { rows, selectedKey, busy, onSelect } = props
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const visible = useMemo(() => rows.filter((row) => accepts(row, filter)
    && `${row.label} ${row.relative_path || ''}`.toLowerCase().includes(query.trim().toLowerCase())),
  [rows, filter, query])
  // Keep the current pair in place after an action, even when its status leaves a filter.
  const selected = rows.find((row) => matchKey(row) === selectedKey)
    ?? visible.find((row) => row.status !== 'LINKED') ?? visible[0]
  useEffect(() => {
    if (selected && matchKey(selected) !== selectedKey) onSelect(selected)
  }, [selected, selectedKey, onSelect])
  const changeFilter = (next: Filter) => {
    setFilter(next)
    const first = rows.find((row) => accepts(row, next)
      && `${row.label} ${row.relative_path || ''}`.toLowerCase().includes(query.trim().toLowerCase()))
    if (first) onSelect(first)
  }
  const nextPending = selected ? [...rows.slice(rows.indexOf(selected) + 1), ...rows.slice(0, rows.indexOf(selected))]
    .find((row) => row.status !== 'LINKED') : undefined
  const isCandidate = selected && ['MATCHED', 'NEEDS_CONFIRM'].includes(selected.status)

  return (
    <section className="relation-board" id="evidence-relations" aria-label="经历与证据对照">
      <div className="relation-toolbar">
        <div className="relation-filters" aria-label="按关联状态筛选">
          {filters.map(([key, label]) => (
            <button type="button" key={key} aria-pressed={filter === key} onClick={() => changeFilter(key)}>
              {label} <span>{rows.filter((row) => accepts(row, key)).length}</span>
            </button>
          ))}
        </div>
        <input className="resume-input relation-search" aria-label="搜索经历或证据文件"
          placeholder="搜索经历 / 文件名" value={query} onChange={(event) => setQuery(event.target.value)} />
      </div>
      <div className="relation-layout">
        <nav className="relation-queue" aria-label="选择要核对的经历">
          <div className="relation-queue-title">经历清单 <span>{visible.length} 条</span></div>
          {visible.map((row) => (
            <button type="button" key={matchKey(row)} className="relation-queue-item"
              aria-current={selected && matchKey(selected) === matchKey(row) ? 'true' : undefined}
              onClick={() => onSelect(row)} disabled={busy}>
              <span className="relation-queue-meta"><span>{row.kind}</span>
                <span className={`chip status-${row.status}`}>{labels[row.status] || row.status}</span></span>
              <strong>{row.label}</strong>
              <span className="relation-file-caption">{row.evidence_id ? '↳ ' + (row.relative_path || '证据材料') : '尚无对应证据'}</span>
            </button>
          ))}
          {!visible.length && <div className="relation-empty">
            {rows.length ? '没有符合筛选条件的经历。' : '先添加经历，再导入证明材料。'}
            {rows.length ? <button type="button" className="linkish" onClick={() => { setQuery(''); changeFilter('all') }}>清除筛选</button>
              : <Link to="/vault">前往经历库 →</Link>}
          </div>}
        </nav>
        {selected ? <div className="relation-detail" aria-label="当前关联详情" aria-busy={busy}>
          {!visible.some((row) => matchKey(row) === matchKey(selected)) && <p className="relation-filter-note">当前对照不在筛选结果中。可从左侧选择其他经历，或清除筛选。</p>}
          <div className="relation-detail-head">
            <div><span className="relation-eyebrow">当前对照</span><h3>{selected.label}</h3></div>
            <span className={`chip status-${selected.status}`}>{labels[selected.status] || selected.status}</span>
          </div>
          <div className={`relation-pair relation-pair-${selected.status}`}>
            <article className="relation-source">
              <span className="relation-eyebrow">A · 经历库记录</span>
              <h4>{selected.label}</h4>
              <dl>{(props.sourceDetails[matchKey(selected)] || []).map((field) => <div key={field.label}>
                <dt>{field.label}</dt><dd>{field.value || '未填写'}</dd>
              </div>)}</dl>
            </article>
            <div className="relation-connector" aria-label={selected.status === 'LINKED' ? '已建立关联' : '待核对关系'}>
              <span aria-hidden="true">{selected.status === 'LINKED' ? '↔' : '⇢'}</span>
              <small>{selected.status === 'LINKED' ? '已关联' : selected.status === 'CONFLICT' ? '有冲突' : selected.evidence_id ? '待确认' : '待补充'}</small>
            </div>
            <article className="relation-proof">
              <span className="relation-eyebrow">B · {selected.status === 'LINKED' ? '已关联证据' : '候选证据'}</span>
              <h4>{selected.relative_path || (selected.evidence_id ? '证据材料' : '尚未找到对应材料')}</h4>
              {selected.evidence_id && props.evidenceExcerpt?.evidenceId === selected.evidence_id && props.evidenceExcerpt.text ? <blockquote className="relation-excerpt">
                <span className="relation-eyebrow">材料原文片段</span>{props.evidenceExcerpt.text}
              </blockquote> : null}
              {selected.evidence_id && selected.target_type === 'award' ? <dl>
                {Object.entries({ award_name: '名称', recipient: '姓名', grade: '等级', issuer: '颁发方', date: '日期' }).map(([key, label]) => {
                  const value = selected.candidate_fields?.[key as keyof NonNullable<ResumeMatchItem['candidate_fields']>]
                  return value ? <div key={key}><dt>{label}</dt><dd>{value}</dd></div> : null
                })}
                {!Object.values(selected.candidate_fields || {}).some(Boolean) && <div><dt>识别字段</dt><dd>暂无结构化字段，请查看原件。</dd></div>}
              </dl> : <p>{selected.evidence_id ? '展开下方原件，核对材料是否支持左侧经历。' : selected.status === 'UNCHECKED' ? '导入材料后，点击「对照经历库」寻找候选。' : selected.gap_hint || '上传能证明这条经历的证书、报告或其他材料。'}</p>}
            </article>
          </div>
          <div className={`relation-reasons ${selected.status === 'CONFLICT' ? 'relation-reasons-conflict' : ''}`}>
            <strong>{selected.status === 'LINKED' ? '关联结果' : selected.status === 'CONFLICT' ? '需要解决的冲突' : '对照依据'}</strong>
            <p>{selected.status === 'LINKED' ? '上方经历已关联到这份材料。' : selected.action}</p>
            {!!selected.notes?.length && <ul>{selected.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}
            {selected.evidence_id && selected.status !== 'LINKED' && <small>匹配分 {selected.score}/100 · 仅用于推荐，确认前请核对原件。</small>}
          </div>
          <div className="relation-actions">
            <div className="btn-row">
              {isCandidate && <button type="button" className="btn primary" disabled={busy} onClick={() => props.onConfirm(selected)}>确认 A 与 B 关联</button>}
              {selected.status === 'LINKED' && <button type="button" className="btn secondary" disabled={busy} onClick={() => props.onUnlink(selected)}>取消此关联</button>}
              {selected.status === 'UNCHECKED' && <button type="button" className="btn primary" disabled={busy} onClick={props.onMatch}>对照经历库</button>}
              {(isCandidate || selected.status === 'CONFLICT') && selected.evidence_id && <button type="button" className="btn secondary" disabled={busy} onClick={() => props.onReject(selected)}>这份证据不符合</button>}
              {selected.status !== 'LINKED' && <button type="button" className={`btn ${selected.status === 'MISSING' ? 'primary' : 'secondary'}`} disabled={busy} onClick={() => props.onSupplement(selected)}>为此经历补充材料</button>}
            </div>
            <button type="button" className="btn secondary" disabled={busy || !nextPending} onClick={() => nextPending && onSelect(nextPending)}>下一条待处理 →</button>
          </div>
          {props.renderEvidence(selected)}
          <details className="relation-more"><summary>编辑经历 / 更多操作</summary><div className="btn-row">
            <Link className="btn secondary" to="/vault">去经历库编辑</Link>
            <button type="button" className="btn ghost-danger" disabled={busy} onClick={() => props.onDelete(selected)}>删除此经历</button>
          </div></details>
        </div> : <div className="relation-empty">选择一条经历，即可在这里核对对应材料。</div>}
      </div>
    </section>
  )
}
