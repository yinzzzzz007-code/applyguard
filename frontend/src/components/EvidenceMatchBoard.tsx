import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { EvidenceFieldCheck, EvidenceSourceFile, ResumeMatchItem } from '../api/types'
import { FieldCheckTable } from './FieldCheckTable'
import {
  associationLabel,
  materialKindLabel,
  recognitionLabel,
  supportSummary,
} from '../evidence/verification'
import { materialName } from '../evidence/materials'

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
  libraryFiles?: EvidenceSourceFile[]
  fieldChecks?: EvidenceFieldCheck[]
  onSelect: (row: ResumeMatchItem) => void
  onConfirm: (row: ResumeMatchItem) => void
  onReject: (row: ResumeMatchItem) => void
  onUnlink: (row: ResumeMatchItem) => void
  onSupplement: (row: ResumeMatchItem) => void
  onPickExisting?: (row: ResumeMatchItem, file: EvidenceSourceFile) => void
  onChangeFieldStatus?: (key: string, status: string) => void
  onDelete: (row: ResumeMatchItem) => void
  onMatch: () => void
  renderSupplement: (row: ResumeMatchItem) => ReactNode
  renderEvidence: (row: ResumeMatchItem) => ReactNode
}

export function EvidenceMatchBoard(props: Props) {
  const { rows, selectedKey, busy, onSelect } = props
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const visible = useMemo(() => rows.filter((row) => accepts(row, filter)
    && `${row.label} ${row.relative_path || ''}`.toLowerCase().includes(query.trim().toLowerCase())),
  [rows, filter, query])
  const selected = rows.find((row) => matchKey(row) === selectedKey)
    ?? visible.find((row) => row.status !== 'LINKED') ?? visible[0]
  useEffect(() => {
    if (selected && matchKey(selected) !== selectedKey) onSelect(selected)
  }, [selected, selectedKey, onSelect])
  useEffect(() => { setPickerOpen(false) }, [selectedKey])

  const changeFilter = (next: Filter) => {
    setFilter(next)
    const first = rows.find((row) => accepts(row, next)
      && `${row.label} ${row.relative_path || ''}`.toLowerCase().includes(query.trim().toLowerCase()))
    if (first) onSelect(first)
  }
  const nextPending = selected ? [...rows.slice(rows.indexOf(selected) + 1), ...rows.slice(0, rows.indexOf(selected))]
    .find((row) => row.status !== 'LINKED') : undefined
  const isCandidate = selected && ['MATCHED', 'NEEDS_CONFIRM'].includes(selected.status)
  const checks = props.fieldChecks ?? selected?.field_checks ?? []
  const canPickExisting = selected && selected.status !== 'LINKED' && !!props.libraryFiles?.length && !!props.onPickExisting
  const pickable = (props.libraryFiles || []).filter((file) => file.evidence_id
    && file.evidence_id !== selected?.evidence_id)

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
              <span className="relation-file-caption">{row.evidence_id
                ? `↳ ${row.material_kind_label || materialKindLabel(row.material_kind) || '材料'} · ${row.relative_path || '证据'}`
                : '尚无对应材料'}</span>
            </button>
          ))}
          {!visible.length && <div className="relation-empty">
            {rows.length ? '没有符合筛选条件的经历。' : '先保存经历，再导入证明材料。'}
            {rows.length ? <button type="button" className="linkish" onClick={() => { setQuery(''); changeFilter('all') }}>清除筛选</button>
              : <Link to="/vault">前往经历库 →</Link>}
          </div>}
        </nav>
        {selected ? <div className="relation-detail" aria-label="当前关联详情" aria-busy={busy}>
          {!visible.some((row) => matchKey(row) === matchKey(selected)) && <p className="relation-filter-note">当前对照不在筛选结果中。可从左侧选择其他经历，或清除筛选。</p>}
          <div className="relation-detail-head">
            <div><span className="relation-eyebrow">当前对照 · {selected.kind}</span><h3>{selected.label}</h3></div>
            <span className={`chip status-${selected.status}`}>{labels[selected.status] || selected.status}</span>
          </div>

          <div className="relation-concept-row" aria-label="识别 / 关联 / 支持">
            <div><span>识别</span><strong>{recognitionLabel(selected.review_state, !!selected.evidence_id)}</strong></div>
            <div><span>关联</span><strong>{associationLabel(selected.status)}</strong></div>
            <div><span>信息获支持</span><strong>{supportSummary(checks)}</strong></div>
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
              <span className="relation-eyebrow">B · {selected.status === 'LINKED' ? '已关联材料' : selected.evidence_id ? '候选材料' : '下一步'}</span>
              {selected.evidence_id ? (
                <>
                  <h4>{selected.relative_path || '证据材料'}</h4>
                  {selected.material_kind_label || selected.material_kind ? (
                    <p className="relation-material-kind">材料类型：{selected.material_kind_label || materialKindLabel(selected.material_kind)}</p>
                  ) : null}
                  {props.evidenceExcerpt?.evidenceId === selected.evidence_id && props.evidenceExcerpt.text ? (
                    <blockquote className="relation-excerpt">
                      <span className="relation-eyebrow">材料原文片段</span>{props.evidenceExcerpt.text}
                    </blockquote>
                  ) : (
                    <p className="muted">可展开下方原件与识别文字查看上下文。</p>
                  )}
                  {(selected.linked_evidence_ids?.length || 0) > 1 && (
                    <p className="muted">已关联 {selected.linked_evidence_ids!.length} 份材料（可继续追加）。</p>
                  )}
                </>
              ) : (
                <h4>{selected.status === 'UNCHECKED' ? '尚未对照' : '尚未选择材料'}</h4>
              )}

              <div className={`relation-reasons relation-reasons-in-proof ${selected.status === 'CONFLICT' ? 'relation-reasons-conflict' : ''}`}>
                <strong>{selected.status === 'LINKED' ? '关联结果' : selected.status === 'CONFLICT' ? '需要解决的冲突' : '下一步'}</strong>
                <p>{selected.action}</p>
                {!!selected.notes?.length && <ul>{selected.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}
                {selected.evidence_id && selected.status !== 'LINKED' && (
                  <small>匹配分 {selected.score}/100 · 仅用于推荐。请先向下看完字段核对与原件，再在底部决定。</small>
                )}
              </div>

              {/* 无材料时：补材料操作留在 B；有候选时确认/排除放到页面底部，避免先点后看 */}
              {!selected.evidence_id && (
                <div className="relation-actions relation-actions-in-proof">
                  <div className="btn-row">
                    {selected.status === 'UNCHECKED' && <button type="button" className="btn primary" disabled={busy} onClick={props.onMatch}>查找对应关系</button>}
                    <button type="button" className="btn primary" disabled={busy} onClick={() => props.onSupplement(selected)}>上传新材料</button>
                    {canPickExisting && (
                      <button type="button" className="btn secondary" disabled={busy} onClick={() => setPickerOpen((v) => !v)}>
                        {pickerOpen ? '收起已有材料' : '从已有材料中选择'}
                      </button>
                    )}
                  </div>
                  <button type="button" className="btn secondary" disabled={busy || !nextPending} onClick={() => nextPending && onSelect(nextPending)}>下一条待处理 →</button>
                </div>
              )}

              {pickerOpen && canPickExisting && !selected.evidence_id && (
                <div className="relation-material-picker" role="listbox" aria-label="选择已有材料">
                  <p className="muted">不会重复上传。选中后进入核对，确认关联前仍可调整字段状态。</p>
                  {pickable.length ? pickable.map((file) => (
                    <button
                      type="button"
                      key={file.file_id}
                      className="relation-material-option"
                      role="option"
                      disabled={busy || !file.evidence_id}
                      onClick={() => props.onPickExisting?.(selected, file)}
                    >
                      <strong>{materialName(file.relative_path)}</strong>
                      <span>{file.evidence_review_state === 'REVIEWED' ? '识别完成' : '待确认内容'} · {file.relative_path}</span>
                    </button>
                  )) : <p className="muted">没有其他可关联的已导入材料。</p>}
                </div>
              )}
              {props.renderSupplement(selected)}
            </article>
          </div>

          {selected.evidence_id ? (
            <div className="relation-verify-block">
              <div className="relation-verify-head">
                <strong>字段核对</strong>
                <span className="muted">仅核对有填写的字段；未提及 ≠ 冲突；确认关联不会把全部字段标成支持</span>
              </div>
              <FieldCheckTable
                checks={checks}
                editable={!!props.onChangeFieldStatus}
                busy={busy}
                onChangeStatus={props.onChangeFieldStatus}
                emptyHint="当前经历没有可核对的已填字段。"
              />
            </div>
          ) : null}

          {props.renderEvidence(selected)}

          {selected.evidence_id ? (
            <div className="relation-decision" aria-label="核对后的决定">
              <div className="relation-decision-copy">
                <strong>看完后决定</strong>
                <p>确认关联或排除这份材料。决定前请已核对上方字段与原件。</p>
              </div>
              <div className="relation-actions relation-actions-footer">
                <div className="btn-row">
                  {isCandidate && <button type="button" className="btn primary" disabled={busy} onClick={() => props.onConfirm(selected)}>确认关联</button>}
                  {(isCandidate || selected.status === 'CONFLICT') && (
                    <button type="button" className="btn secondary" disabled={busy} onClick={() => props.onReject(selected)}>这份材料不符合</button>
                  )}
                  {selected.status === 'LINKED' && (
                    <button type="button" className="btn secondary" disabled={busy} onClick={() => props.onUnlink(selected)}>取消此关联</button>
                  )}
                  {selected.status !== 'LINKED' && (
                    <button type="button" className="btn secondary" disabled={busy} onClick={() => props.onSupplement(selected)}>换一份新材料</button>
                  )}
                  {canPickExisting && (
                    <button type="button" className="btn secondary" disabled={busy} onClick={() => setPickerOpen((v) => !v)}>
                      {pickerOpen ? '收起已有材料' : '改选已有材料'}
                    </button>
                  )}
                </div>
                <button type="button" className="btn secondary" disabled={busy || !nextPending} onClick={() => nextPending && onSelect(nextPending)}>下一条待处理 →</button>
              </div>
              {pickerOpen && canPickExisting && (
                <div className="relation-material-picker" role="listbox" aria-label="选择已有材料">
                  <p className="muted">不会重复上传。选中后重新核对，再决定是否关联。</p>
                  {pickable.length ? pickable.map((file) => (
                    <button
                      type="button"
                      key={file.file_id}
                      className="relation-material-option"
                      role="option"
                      disabled={busy || !file.evidence_id}
                      onClick={() => props.onPickExisting?.(selected, file)}
                    >
                      <strong>{materialName(file.relative_path)}</strong>
                      <span>{file.evidence_review_state === 'REVIEWED' ? '识别完成' : '待确认内容'} · {file.relative_path}</span>
                    </button>
                  )) : <p className="muted">没有其他可关联的已导入材料。</p>}
                </div>
              )}
            </div>
          ) : null}

          <details className="relation-more"><summary>编辑经历 / 更多操作</summary><div className="btn-row">
            <Link className="btn secondary" to="/vault">去经历库编辑</Link>
            <button type="button" className="btn ghost-danger" disabled={busy} onClick={() => props.onDelete(selected)}>删除此经历</button>
          </div></details>
        </div> : <div className="relation-empty">选择一条经历，即可在这里核对对应材料。</div>}
      </div>
    </section>
  )
}
