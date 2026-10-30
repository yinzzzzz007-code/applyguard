import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motionAllowed, projectStart, REEL_DURATION, reelFrame } from '../motion/reel'
import { ONBOARDING_STEPS, type OnboardingStep } from '../motion/onboarding'
import { Icon } from './Icon'
import { KineticCanvas } from './KineticCanvas'
import '../motion.css'

function preference(key: string) {
  try { return sessionStorage.getItem(key) === 'true' } catch { return false }
}
function remember(key: string, value: boolean) {
  try { sessionStorage.setItem(key, String(value)) } catch { /* Optional UI preference. */ }
}

function ReelPlayer() {
  const projects = ONBOARDING_STEPS
  const root = useRef<HTMLDivElement>(null)
  const clock = useRef(0)
  const audio = useRef<HTMLAudioElement>(null)
  const [sound, setSound] = useState(false)
  const [soundError, setSoundError] = useState('')
  const [time, setTime] = useState(0)
  const [paused, setPaused] = useState(() => preference('applyguard.reel.paused'))
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [visible, setVisible] = useState(false)
  const [rendererReady, setRendererReady] = useState(false)
  const [pageVisible, setPageVisible] = useState(!document.hidden)
  const frame = reelFrame(time, projects.length)
  const current = projects[frame.index]
  const playing = motionAllowed(reduced, paused, visible, pageVisible) && rendererReady

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onMotion = () => setReduced(media.matches)
    const onVisibility = () => setPageVisible(!document.hidden)
    const observer = new IntersectionObserver(([entry]) => {
      const inView = entry.isIntersecting && entry.intersectionRatio >= .12
      setVisible(inView)
      if (!inView) setRendererReady(false)
    }, { threshold: .12 })
    if (root.current) observer.observe(root.current)
    media.addEventListener('change', onMotion)
    document.addEventListener('visibilitychange', onVisibility)
    return () => { observer.disconnect(); media.removeEventListener('change', onMotion); document.removeEventListener('visibilitychange', onVisibility) }
  }, [])

  useEffect(() => {
    if (!playing) return
    let handle = 0
    let previous: number | null = null
    let lastPaint = 0
    const tick = (now: number) => {
      if (sound && audio.current && !audio.current.paused) clock.current = audio.current.currentTime % REEL_DURATION
      else if (previous !== null) clock.current = (clock.current + Math.max(now - previous, 0) / 1000) % REEL_DURATION
      previous = now
      if (now - lastPaint >= 1000 / 30) { setTime(clock.current); lastPaint = now }
      handle = requestAnimationFrame(tick)
    }
    handle = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(handle)
  }, [playing, sound])

  useEffect(() => {
    const element = audio.current
    if (!element) return
    if (!playing || !sound) { element.pause(); return }
    element.currentTime = clock.current
    element.volume = .28
    void element.play().catch(() => { setSound(false); setSoundError('配乐暂时无法播放，画面可继续浏览。') })
    return () => element.pause()
  }, [playing, sound])

  function seek(next: number) {
    clock.current = next
    setTime(next)
    if (audio.current) audio.current.currentTime = next
  }
  function togglePause() {
    setPaused(value => { remember('applyguard.reel.paused', !value); return !value })
  }
  function selectProject(index: number) {
    setPaused(true); remember('applyguard.reel.paused', true)
    seek(projectStart(index, projects.length) + 3.8)
  }

  return <div className="project-player" ref={root} data-playing={playing} data-phase={frame.phase}>
    <div className="reel-stage" role="img" aria-label={frame.phase === 'project' ? `阶段：${current.title}。${current.excerpt}` : frame.phase === 'open' ? '第一次使用 ApplyGuard：建立经历、补充依据、准备岗位、核对保存。' : '先核对，再申请。完整操作说明在下方。'}>{visible && <KineticCanvas projects={projects} time={time} still={reduced || (paused && time === 0)} onReady={setRendererReady} />}</div>
    <audio ref={audio} src="/assets/kinetic-score.wav" preload="none" loop onError={() => { setSound(false); setSoundError('配乐暂时无法播放，画面可继续浏览。') }} />
    <div className="reel-transport">
      <button type="button" className="reel-play" onClick={togglePause} disabled={reduced} aria-label={reduced ? '系统已开启减少动态效果' : paused ? '播放新手引导' : '暂停新手引导'}><Icon name={paused || reduced ? 'play' : 'pause'} /><span>{reduced ? '静态浏览' : paused ? '播放' : '暂停'}</span></button>
      <label className="reel-seek"><span className="reel-sr-only">短片进度，单位秒</span><input type="range" min="0" max="23.99" step=".01" value={frame.time} onChange={event => { setPaused(true); remember('applyguard.reel.paused', true); seek(Number(event.target.value)) }} aria-valuetext={`${frame.time.toFixed(1)} 秒，共 24 秒`} /></label>
      <span className="reel-time" aria-hidden="true">{String(Math.floor(frame.time)).padStart(2, '0')} / 24</span>
      <button type="button" className="reel-restart" onClick={() => seek(0)} aria-label="回到开头"><Icon name="refresh" /></button>
      <button type="button" className="reel-restart" aria-label={sound ? '关闭配乐' : '开启配乐'} aria-pressed={sound} onClick={() => { setSoundError(''); setSound(!sound) }}><Icon name={sound ? 'volume' : 'mute'} /></button>
    </div>
    <div className="reel-chapters" role="group" aria-label="跳到引导阶段并暂停">{projects.map((project, index) => <button type="button" key={project.id} aria-pressed={frame.phase === 'project' && frame.index === index} onClick={() => selectProject(index)}><span>{index + 1}</span><span>{project.title}</span></button>)}</div>
    {reduced && <p className="reel-motion-note">已遵循系统的减少动态效果设置，可点击阶段或拖动进度查看。</p>}
    {soundError && <p className="reel-motion-note" role="status">{soundError}</p>}
    <div className="onboarding-next"><p>第一次只准备一个岗位，从自己的简历开始。</p><Link to="/" className="btn primary">开始准备我的申请<Icon name="arrow" /></Link></div>
    <details className="reel-sources"><summary><Icon name="file" />查看完整操作说明<Icon name="down" /></summary><div>{projects.map((stage: OnboardingStep) => <article key={stage.id}><h3>{stage.title}</h3><p>{stage.original}</p><p><strong>为什么：</strong>{stage.why}</p><p><strong>完成标志：</strong>{stage.completion}</p></article>)}<p className="reel-motion-note">首次使用不需要先安装其他工具或连接 Agent，先用自己的简历和相关材料完成一次申请准备。</p></div></details>
  </div>
}

export function ProjectReel() {
  const [collapsed, setCollapsed] = useState(() => preference('applyguard.guide.collapsed'))
  return <section className={`project-reel${collapsed ? ' is-collapsed' : ''}`} aria-labelledby="project-reel-title">
    <div className="project-reel-heading"><div><h2 id="project-reel-title">第一次使用 ApplyGuard</h2><p>24 秒，了解从简历到申请稿的四个阶段。</p></div><button type="button" className="reel-collapse" aria-expanded={!collapsed} aria-controls="project-reel-body" onClick={() => { remember('applyguard.guide.collapsed', !collapsed); setCollapsed(!collapsed) }}><span>{collapsed ? '展开引导' : '收起'}</span><Icon name={collapsed ? 'play' : 'down'} /></button></div>
    {!collapsed && <div id="project-reel-body"><ReelPlayer /></div>}
  </section>
}
