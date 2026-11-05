import { useLayoutEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

/** Animate the DOM container without remounting routes or losing form state. */
export function PageMotion({ children }: { children: React.ReactNode }) {
  const root = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()
  const previousPath = useRef(pathname)
  useLayoutEffect(() => {
    if (previousPath.current === pathname) return
    previousPath.current = pathname
    const node = root.current
    if (!node) return
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const animation = node.animate(reduced
      ? [{ opacity: .88 }, { opacity: 1 }]
      : [{ opacity: .65, transform: 'translateY(7px)' }, { opacity: 1, transform: 'translateY(0)' }],
    { duration: reduced ? 80 : 220, easing: 'cubic-bezier(.16,1,.3,1)' })
    const onPreference = () => animation.cancel()
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    media.addEventListener('change', onPreference)
    // Keyboard navigation should arrive at the new screen rather than an old navigation item.
    const active = document.activeElement
    if (active?.closest('nav') || active?.closest('.btn-row')) {
      document.getElementById('workspace-main')?.focus({ preventScroll: true })
    }
    return () => { animation.cancel(); media.removeEventListener('change', onPreference) }
  }, [pathname])
  return <div className="page-motion" ref={root}>{children}</div>
}
