import { useEffect, useState } from 'react'
import { getApiClient } from '../api/client'

export function BackendStatus({ live }: { live: boolean }) {
  const [state, setState] = useState<'checking' | 'online' | 'offline'>('checking')
  useEffect(() => {
    if (!live) return
    let active = true
    let busy = false
    async function check() {
      if (busy || document.hidden) return
      busy = true
      try {
        const result = await getApiClient().getHealth()
        if (active) setState(result.data?.status === 'ok' && !result.error ? 'online' : 'offline')
      } catch {
        if (active) setState('offline')
      } finally { busy = false }
    }
    void check()
    const timer = window.setInterval(() => void check(), 15000)
    document.addEventListener('visibilitychange', check)
    window.addEventListener('online', check)
    return () => {
      active = false
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', check)
      window.removeEventListener('online', check)
    }
  }, [live])
  const status = live ? state : 'demo'
  return <span className="backend-status" role="status" title={live ? '每 15 秒检查本地服务；连接正常不代表模型服务可用。' : '使用内置样例，不依赖后端或模型服务。'}>
    <span className={`connection-dot is-${status}`} aria-hidden="true" />
    {{ checking: '正在检查连接', online: '本地服务已连接', offline: '本地服务未连接', demo: '预录 / 模拟' }[status]}
  </span>
}
