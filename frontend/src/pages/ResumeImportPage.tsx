import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiClient, type WorkflowParseMode } from '../api/client'
import type { ResumeParseResult } from '../api/types'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { overwriteFromExtracted } from '../resume/formModel'

export function ResumeImportPage() {
  const navigate = useNavigate()
  const { setResumeForm } = useDemo()
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [parsed, setParsed] = useState<ResumeParseResult | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [parseMode, setParseMode] = useState<WorkflowParseMode>('offline')

  async function runParse(target: File) {
    setStatus('loading')
    setErrorMsg('')
    setParsed(null)
    const res = await getApiClient().parseResumePdf(target, parseMode)
    if (res.error) {
      setErrorMsg(res.error.message)
      setStatus('error')
      return
    }
    if (!res.data) {
      setErrorMsg('未返回识别结果。')
      setStatus('error')
      return
    }
    setParsed(res.data)
    setStatus('success')
  }

  async function applyToVault() {
    if (!parsed) return
    const vault = await getApiClient().getCareerVault()
    if (!vault.data?.candidate_id) {
      setErrorMsg('无法加载经历库种子，识别结果暂不能写入。')
      setStatus('error')
      return
    }
    if (
      !window.confirm('将清空经历库中的原有简历，并写入本次识别结果。是否继续？')
    ) {
      return
    }
    const next = overwriteFromExtracted(vault.data.candidate_id, parsed.form)
    setResumeForm(next)
    try {
      sessionStorage.setItem('applyguard.resumeForm', JSON.stringify(next))
    } catch {
      /* ignore quota */
    }
    const saved = await getApiClient().saveResumeDraft(next)
    if (saved.error) {
      setErrorMsg(`已覆盖本页内容，但后端草稿未保存：${saved.error.message}`)
    }
    sessionStorage.setItem('applyguard.importNotice', '已清空原简历，并写入本次识别结果。请核对后点击保存。')
    navigate('/vault', { state: { importCleared: true } })
  }

  const basic = parsed?.form.basic

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>简历识别</h2>
        <p>
          可选步骤：上传可复制文字的 PDF，抽出姓名、联系方式、教育、经历与获奖等，再写入经历库核对。也可跳过，直接从经历库开始（演示种子或已保存草稿）。扫描件无法识别。不会向招聘网站提交。
        </p>
      </header>

      <label className="field-label" htmlFor="resume-parse-mode">识别方式</label>
      <select id="resume-parse-mode" value={parseMode} disabled={status === 'loading'}
        onChange={(event) => { setParseMode(event.target.value as WorkflowParseMode); setParsed(null); setStatus('idle') }}>
        <option value="offline">本地规则（默认，不调用模型）</option>
        <option value="dynamic">模型抽取（发送简历正文，可能产生费用）</option>
      </select>
      <p className="muted">仅选择模型抽取时，才会将 PDF 正文和文件名发送给后端配置的服务商。可先脱敏；模型结果仍需人工核对。</p>
      <label
        className={dragOver ? 'resume-dropzone is-over' : 'resume-dropzone'}
        onDragOver={(event) => {
          event.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragOver(false)
          const next = event.dataTransfer.files[0]
          if (next) {
            setFile(next)
            void runParse(next)
          }
        }}
      >
        <input
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={(event) => {
            const next = event.target.files?.[0]
            if (next) {
              setFile(next)
              void runParse(next)
            }
          }}
        />
        <strong>{file ? file.name : '点击或拖入 PDF'}</strong>
        <span className="muted">单个文件，不超过 5MB</span>
      </label>

      {status === 'loading' && <LoadingState label="正在识别简历…" />}
      {status === 'error' && (
        <ErrorState
          message={errorMsg}
          onRetry={() => {
            if (file) void runParse(file)
          }}
        />
      )}

      {status === 'success' && parsed && (
        <div className="item-block">
          <h3>识别结果 · {parsed.extractor}</h3>
          <p>{parsed.notice}</p>
          <ul className="ats-summary">
            <li>姓名：{basic?.name || '未抽出'}</li>
            <li>手机：{basic?.phone || '未抽出'}</li>
            <li>邮箱：{basic?.email || '未抽出'}</li>
            <li>性别：{basic?.gender || '未抽出'}</li>
            <li>现居住地：{basic?.city || '未抽出'}</li>
            <li>教育条数：{parsed.form.education.length}</li>
            <li>实习条数：{parsed.form.internships.length}</li>
            <li>项目条数：{parsed.form.projects.length}</li>
            <li>获奖 / 竞赛条数：{(parsed.form.awards ?? []).length}</li>
          </ul>
          {parsed.preview ? (
            <>
              <p className="field-label">正文摘录</p>
              <pre className="copy-pack jd-input">{parsed.preview}</pre>
            </>
          ) : null}
        </div>
      )}

      {status === 'idle' && (
        <EmptyState
          title="尚未上传"
          detail="这不是必做步骤。可点下方按钮，或顶部「经历库」，直接从第二步开始。"
        />
      )}

      <div className="btn-row end">
        <button type="button" className="btn secondary" onClick={() => navigate('/vault')}>
          跳过，直接进入经历库
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={!parsed}
          onClick={() => void applyToVault()}
        >
          写入经历库并核对
        </button>
      </div>
    </section>
  )
}
