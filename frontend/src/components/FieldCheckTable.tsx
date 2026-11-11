import type { EvidenceFieldCheck } from '../api/types'
import { FIELD_STATUS_LABELS, statusLabel } from '../evidence/verification'

type Props = {
  checks: EvidenceFieldCheck[]
  editable?: boolean
  busy?: boolean
  onChangeStatus?: (key: string, status: string) => void
  emptyHint?: string
}

const STATUS_OPTIONS = ['SUPPORTED', 'NOT_MENTIONED', 'CONFLICT', 'PENDING'] as const

export function FieldCheckTable({ checks, editable, busy, onChangeStatus, emptyHint }: Props) {
  if (!checks.length) {
    return <p className="muted field-check-empty">{emptyHint || '当前经历没有可核对的已填字段。'}</p>
  }
  return (
    <div className="field-check-table" role="table" aria-label="经历字段核对">
      <div className="field-check-head" role="row">
        <span role="columnheader">经历中的信息</span>
        <span role="columnheader">材料中的对应原文</span>
        <span role="columnheader">核对状态</span>
      </div>
      {checks.map((row) => {
        const quoteOk = row.quote_available !== false && !!row.quote
        return (
          <div key={row.key} className={`field-check-row status-${row.status}`} role="row">
            <div role="cell">
              <span className="field-check-label">{row.label}</span>
              <strong>{row.experience_value || '未填写'}</strong>
            </div>
            <div role="cell">
              {quoteOk ? (
                <blockquote className="field-check-quote">{row.quote}</blockquote>
              ) : (
                <span className="field-check-missing">{row.quote_note || '原文定位不可用'}</span>
              )}
              {row.source === 'program' && <small className="muted">程序建议</small>}
              {row.source === 'legacy' && <small className="muted">旧数据 · 待核对</small>}
              {row.source === 'user' && <small className="muted">已确认</small>}
            </div>
            <div role="cell">
              {editable && onChangeStatus ? (
                <select
                  className="resume-input field-check-status"
                  aria-label={`${row.label}核对状态`}
                  disabled={busy}
                  value={row.status}
                  onChange={(event) => onChangeStatus(row.key, event.target.value)}
                >
                  {STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>{FIELD_STATUS_LABELS[status]}</option>
                  ))}
                </select>
              ) : (
                <span className={`chip field-status-${row.status}`}>{row.status_label || statusLabel(row.status)}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
