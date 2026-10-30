import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiClient, type WorkflowParseMode } from '../api/client'
import type { ResumeParseResult } from '../api/types'
import { ErrorState, LoadingState } from '../components/States'
import { Icon } from '../components/Icon'
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
    <section className="panel import-page">
      <header className="panel-head">
        <h2>从真实经历，开始下一份申请。</h2>
        <p>导入简历、整理证据，再把你的经历表达得更好。</p>
      </header>
      <div className="import-layout">
      <div className="import-card">
      <div className="surface-heading"><h3>导入你的简历</h3><span className="quiet-label">PDF 文档</span></div>
      <p className="muted">识别基本信息与经历，写入前由你核对。</p>
      <label className="field-label" htmlFor="resume-parse-mode">识别方式</label>
      <select id="resume-parse-mode" value={parseMode} disabled={status === 'loading'}
        onChange={(event) => { setParseMode(event.target.value as WorkflowParseMode); setParsed(null); setStatus('idle') }}>
        <option value="offline">本地规则（默认，不调用模型）</option>
        <option value="dynamic">模型抽取（发送简历正文，可能产生费用）</option>
      </select>
      <p className="mode-note">{parseMode === 'offline' ? '本地处理，无需调用模型。支持可复制文字的 PDF。' : '正文和文件名将发送给后端配置的模型服务，可能产生费用；请先脱敏。'}</p>
      <label
        className={dragOver ? 'resume-dropzone is-over' : 'resume-dropzone'}
        aria-busy={status === 'loading'}
        onDragOver={(event) => {
          event.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragOver(false)
          const next = event.dataTransfer.files[0]
          if (next && status !== 'loading') {
            setFile(next)
            void runParse(next)
          }
        }}
      >
        <input
          type="file"
          accept="application/pdf,.pdf"
          className="import-file-input"
          aria-label="选择 PDF 简历"
          aria-describedby="upload-requirements"
          disabled={status === 'loading'}
          onChange={(event) => {
            const next = event.target.files?.[0]
            if (next) {
              setFile(next)
              void runParse(next)
            }
          }}
        />
        <span className="upload-document"><Icon name="file" /><span className="document-format">PDF</span></span>
        <strong>{file ? file.name : '把简历拖到这里'}</strong>
        <span className="upload-choice">或 <span>选择文件</span></span>
        <span className="muted" id="upload-requirements">单个 PDF · 最大 5 MB · 暂不支持扫描件</span>
      </label>
      <div className="privacy-line"><Icon name="lock" /><span>只用于整理本次申请，不会提交到招聘网站。</span></div>

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

      <div className="btn-row import-actions">
        <button type="button" className="btn secondary" onClick={() => navigate('/vault')}>
          先手动填写
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={!parsed}
          onClick={() => void applyToVault()}
        >
          写入并核对 <Icon name="arrow" />
        </button>
      </div>
      </div>
      <aside className="import-context">
        <div className="context-title"><h3>好表达，始于有依据。</h3><p>从原始材料到最终陈述，每一步都能回头查看。</p></div>
        <ol className="import-journey">
          <li><Icon name="folder" /><div><strong>把经历整理好</strong><p>集中保存教育、项目和实习，建立自己的经历库。</p></div></li>
          <li><Icon name="spark" /><div><strong>让表达更贴合岗位</strong><p>检索相关经历，生成可对照原文的润色建议。</p></div></li>
          <li><Icon name="shield" /><div><strong>逐项核对，再由你确认</strong><p>检查职责、技术、数字与时间，保留版本和修改记录。</p></div></li>
        </ol>
        <div className="context-footnote"><span className="mini-evidence-mark"><Icon name="layers" /></span><p>表达可以变得更好，<br /><strong>事实始终需要支持。</strong></p></div>
      </aside>
      </div>
      <div className="import-bottom"><span>已有经历记录？可以直接继续编辑。</span><button className="text-action" type="button" onClick={() => navigate('/vault')}>打开经历库 <Icon name="arrow" /></button></div>
    </section>
  )
}
