import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import type { EditableResumeForm } from '../api/types'
import { generateInterview, getApiClient } from '../api/client'
import { useDemo } from '../context/DemoContext'
import { interviewResume, type InterviewGuide, type InterviewResume } from '../resume/interview'
import { normalizeResumeForm } from '../resume/formModel'
import { LoadingState } from '../components/States'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'

const STORAGE_KEY = 'applyguard.interview.v1'
interface SavedPreparation {
  resume: InterviewResume
  jd: string
  result: { signature: string; guide: InterviewGuide } | null
}

function readPreparation(): SavedPreparation | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? 'null') as SavedPreparation | null
    if (value && typeof value.jd === 'string' && Array.isArray(value.resume?.projects) &&
        Array.isArray(value.resume?.internships) && Array.isArray(value.resume?.education)) return value
  } catch { /* The preparation can be regenerated. */ }
  return null
}

export function InterviewPage() {
  const location = useLocation()
  const { resumeForm, workflow, jdRawInput } = useDemo()
  const [saved] = useState(readPreparation)
  const handedForm = (location.state as { form?: EditableResumeForm } | null)?.form
  const [resume, setResume] = useState<InterviewResume | null>(() =>
    handedForm ? interviewResume(normalizeResumeForm(handedForm)) :
      resumeForm ? interviewResume(normalizeResumeForm(resumeForm)) : saved?.resume ?? null)
  const [jd, setJd] = useState(() => {
    const sameResume = saved && JSON.stringify(saved.resume) === JSON.stringify(resume)
    return sameResume ? saved.jd : jdRawInput || workflow?.parsed_jd.source_text || ''
  })
  const [result, setResult] = useState(saved?.result ?? null)
  const [loading, setLoading] = useState(!resume)
  const [error, setError] = useState('')
  const [storageError, setStorageError] = useState('')
  const [busy, setBusy] = useState(false)
  const [consent, setConsent] = useState('')
  const [duration, setDuration] = useState<'one_minute' | 'three_minutes'>('one_minute')
  const request = useRef<AbortController | null>(null)
  const signature = JSON.stringify([jd.trim(), resume])
  const guide = result?.signature === signature && result.guide.coverage_version === 2 ? result.guide : null

  useEffect(() => () => { request.current?.abort() }, [])
  useEffect(() => {
    if (resume) return
    let active = true
    void getApiClient().getResumeDraft().then(response => {
      if (!active) return
      if (response.data) setResume(interviewResume(normalizeResumeForm(response.data)))
      if (response.error) setError(response.error.message)
      setLoading(false)
    })
    return () => { active = false }
  }, [resume])
  useEffect(() => {
    if (!resume) return
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ resume, jd, result }))
    } catch {
      setStorageError('浏览器暂存失败，请下载已生成的内容后再离开。')
    }
  }, [resume, jd, result])

  async function generate() {
    if (!resume || busy || consent !== signature) return
    const controller = new AbortController()
    request.current = controller
    setBusy(true)
    setError('')
    const response = await generateInterview(jd.trim(), resume,
      AbortSignal.any([controller.signal, AbortSignal.timeout(180000)]))
    if (controller.signal.aborted) return
    if (response.data) setResult({ signature, guide: response.data })
    else setError(response.error?.message ?? '面经生成未完成，请重试。')
    setBusy(false)
  }

  function download() {
    if (!guide) return
    const text = [
      '1 分钟自我介绍', guide.one_minute, '', '3 分钟自我介绍', guide.three_minutes, '',
      ...guide.questions.flatMap((item, index) => [
        `${index + 1}. ${item.question}`, ...(item.project_name ? [`项目：${item.project_name}`] : []),
        item.answer, `对应内容：${item.basis}`,
        ...item.to_confirm.map(value => `待补充：${value}`), '',
      ]),
    ].join('\n')
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'ApplyGuard-面试准备.txt'
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  if (loading) return <LoadingState label="正在读取简历资料…" />
  return <section className="panel interview-page">
    <header className="panel-head">
      <h2>生成面经</h2>
      <p>围绕目标岗位，准备自我介绍和项目追问。</p>
    </header>
    <Card className="profile-card interview-input">
      <div className="item-head">
        <h3>本次准备</h3>
        <Link className="text-action" to="/history">返回简历生成</Link>
      </div>
      {resume && <p className="muted">当前简历 · {resume.projects.length} 段项目 · {resume.internships.length} 段实习</p>}
      {!resume && <p>请先<Link to="/history">生成简历</Link>，或到<Link to="/vault">经历库</Link>保存项目资料。</p>}
      <label className="field-label" htmlFor="interview-jd">目标岗位 JD</label>
      <textarea id="interview-jd" className="jd-input" rows={5} maxLength={20000} value={jd}
        disabled={busy} placeholder="粘贴岗位职责、技术要求和任职条件。" onChange={event => setJd(event.target.value)} />
      {resume && <details className="interview-source">
        <summary>查看本次项目与实习资料</summary>
        {[...resume.projects, ...resume.internships].map((item, index) => <div key={index}>
          <h4>{item.title || item.organization || '未命名经历'}</h4>
          <p>{item.role}{item.techStack && ` · ${item.techStack}`}</p>
          <p className="interview-text">{item.description}</p>
        </div>)}
      </details>}
      <label className="interview-consent">
        <input type="checkbox" checked={consent === signature} disabled={busy}
          onChange={event => setConsent(event.target.checked ? signature : '')} />
        将本次 JD、自我介绍资料及项目经历发送给已配置的模型生成面经，可能产生费用。
      </label>
      <Button
        disabled={busy || !resume || jd.trim().length < 20 || consent !== signature ||
          (!resume.projects.length && !resume.internships.length)} onClick={() => void generate()}>
        {busy ? '正在生成面经…' : guide ? '重新生成面经' : '生成自我介绍与模拟问答'}
      </Button>
      {jd.trim().length > 0 && jd.trim().length < 20 && <p className="muted">请补充至少 20 字的岗位说明。</p>}
      {resume && !resume.projects.length && !resume.internships.length &&
        <p className="muted">请先在经历库补充至少一段项目或实习经历。</p>}
      {error && <p className="danger-text" role="alert">{error}</p>}
      {storageError && <p className="warn-text" role="status">{storageError}</p>}
      {result && !guide && <p className="muted">请重新生成面经，确保内容对应当前资料并覆盖每个项目。</p>}
    </Card>

    {guide && <div className="interview-output">
      <section className="profile-card">
        <div className="item-head"><h3>自我介绍</h3>
          <button type="button" className="btn secondary" onClick={download}>下载面经 TXT</button>
        </div>
        <div className="btn-row" aria-label="自我介绍时长">
          <button className="btn secondary" type="button" aria-pressed={duration === 'one_minute'} onClick={() => setDuration('one_minute')}>1 分钟版</button>
          <button className="btn secondary" type="button" aria-pressed={duration === 'three_minutes'} onClick={() => setDuration('three_minutes')}>3 分钟版</button>
        </div>
        <p className="interview-text">{guide[duration]}</p>
        <p className="muted">按个人语速试读调整时长，使用前核对经历事实。</p>
      </section>
      <section className="interview-questions">
        <h3>模拟问题与参考回答</h3>
        <p className="muted">每个项目至少一题。先尝试回答，再展开对照。</p>
        {guide.questions.map((item, index) => <details className="item-block" key={index}>
          <summary><span className="muted">{item.project_name || item.category}</span><strong>{index + 1}. {item.question}</strong></summary>
          <p className="interview-text">{item.answer}</p>
          <p className="muted">对应内容 · {item.basis}</p>
          {item.to_confirm.length > 0 && <div className="interview-gaps">
            <h4>请补充确认</h4>
            <ul>{item.to_confirm.map((value, i) => <li key={i}>{value}</li>)}</ul>
          </div>}
        </details>)}
      </section>
    </div>}
  </section>
}
