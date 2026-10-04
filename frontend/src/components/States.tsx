import type { ClaimState, FieldControlLevel, AggregateRiskLevel } from '../api/types'
import { ZH_CLAIM, ZH_LEVEL, ZH_RISK } from '../i18n'

export function LoadingState({ label = '加载中…' }: { label?: string }) {
  return (
    <div className="state-panel state-loading" role="status" aria-live="polite">
      <div className="spinner" aria-hidden />
      <p>{label}</p>
    </div>
  )
}

export function EmptyState({
  title,
  detail,
  actionLabel,
  onAction,
}: {
  title: string
  detail: string
  actionLabel?: string
  onAction?: () => void
}) {
  return (
    <div className="state-panel state-empty">
      <h3>{title}</h3>
      <p>{detail}</p>
      {actionLabel && onAction ? (
        <button type="button" className="btn secondary" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}

export function ErrorState({
  message,
  onRetry,
  onFallback,
  fallbackLabel = '回退上一步',
}: {
  message: string
  onRetry?: () => void
  onFallback?: () => void
  fallbackLabel?: string
}) {
  return (
    <div className="state-panel state-error" role="alert">
      <h3>处理失败</h3>
      <p>{message}</p>
      <div className="btn-row">
        {onRetry ? (
          <button type="button" className="btn primary" onClick={onRetry}>
            重试
          </button>
        ) : null}
        {onFallback ? (
          <button type="button" className="btn secondary" onClick={onFallback}>
            {fallbackLabel}
          </button>
        ) : null}
      </div>
    </div>
  )
}

export function ClaimBadge({ status }: { status: ClaimState }) {
  const map: Record<ClaimState, string> = {
    VERIFIED: 'badge ok',
    NEEDS_REVIEW: 'badge warn',
    BLOCKED: 'badge danger',
  }
  return <span className={map[status]}>{ZH_CLAIM[status] ?? status}</span>
}

export function LevelBadge({ level }: { level: FieldControlLevel }) {
  const map: Record<FieldControlLevel, string> = {
    L0: 'badge muted',
    L1: 'badge ok',
    L2: 'badge warn',
    L3: 'badge danger',
  }
  return <span className={map[level]}>{ZH_LEVEL[level] ?? level}</span>
}

export function RiskBadge({ level }: { level: AggregateRiskLevel }) {
  const map: Record<AggregateRiskLevel, string> = {
    LOW: 'badge ok',
    MEDIUM: 'badge warn',
    HIGH: 'badge warn',
    BLOCK: 'badge danger',
  }
  return <span className={map[level]}>{ZH_RISK[level] ?? level}</span>
}
