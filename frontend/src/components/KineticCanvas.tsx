import { useEffect, useRef, useState } from 'react'
import type { ReelProject } from '../motion/reel'
import type { KineticRenderer } from '../motion/kineticEngine'

export function KineticCanvas({projects, time, still, onReady}: {projects: ReelProject[]; time: number; still: boolean; onReady: (ready: boolean) => void}) {
  const holder = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const engine = useRef<KineticRenderer | null>(null)
  const latest = useRef({time, still})
  const [compact, setCompact] = useState(window.innerWidth < 700)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [attempt, setAttempt] = useState(0)
  useEffect(() => { latest.current = {time, still}; engine.current?.draw(time, still) }, [time, still])
  useEffect(() => {
    if (!holder.current) return
    const observer = new ResizeObserver(([entry]) => {
      const next = entry.contentRect.width < 600
      if (next !== compact) { onReady(false); setState('loading'); setCompact(next) }
    })
    observer.observe(holder.current)
    return () => observer.disconnect()
  }, [compact, onReady])
  useEffect(() => {
    if (!canvas.current) return
    let disposed = false
    let instance: KineticRenderer | null = null
    const node = canvas.current
    const onLoss = (event: Event) => { event.preventDefault(); onReady(false); setState('error') }
    node.addEventListener('webglcontextlost', onLoss)
    import('../motion/kineticEngine.js').then(async module => {
      // A canvas cannot change from a disposed WebGL context back into a new one.
      instance = await module.createKineticReel(node, projects, {compact})
      if (disposed) { instance.dispose(); return }
      engine.current = instance
      instance.draw(latest.current.time, latest.current.still)
      setState('ready')
      onReady(true)
    }).catch(() => { if (!disposed) { onReady(false); setState('error') } })
    return () => { disposed = true; engine.current = null; node.removeEventListener('webglcontextlost', onLoss); instance?.dispose() }
  }, [projects, compact, attempt, onReady])
  return <div className={`kinetic-canvas${compact ? ' is-portrait' : ''}`} ref={holder}>
    <canvas key={`${compact ? 'portrait' : 'landscape'}:${attempt}`} ref={canvas} aria-hidden="true" />
    {state !== 'ready' && <div className="kinetic-poster"><span>APPLY<br />WITH CARE.</span><p>{state === 'error' ? '当前设备无法显示动画，可在下方阅读完整操作说明。' : '正在准备新手引导…'}</p>{state === 'error' && <button type="button" onClick={() => {setState('loading');setAttempt(value => value+1)}}>重新载入动画</button>}</div>}
  </div>
}
