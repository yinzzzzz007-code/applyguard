import {completeGuideStep} from '../guide'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiClient, type ResumeParseMode } from '../api/client'
import type { ResumeParseResult } from '../api/types'
import {agentUi} from '../api/agent'
import { DemoQuickStart } from '../components/DemoQuickStart'
import { ErrorState, LoadingState } from '../components/States'
import { Icon } from '../components/Icon'
import { Button } from '../components/ui/button'
import { Card, CardHeader, CardTitle } from '../components/ui/card'
import { queueResumeImport } from '../resume/importTransfer'

const ProjectReel = lazy(() => import('../components/ProjectReel').then(module => ({default:module.ProjectReel})))

export function ResumeImportPage() {
  const navigate = useNavigate()
  const [connections,setConnections]=useState<{github:boolean;harness:string}|null>(null)
  useEffect(()=>{let active=true;void agentUi({action:'connections_summary'}).then(v=>{if(active)setConnections(v)}).catch(()=>{});return ()=>{active=false}},[])
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [parsed, setParsed] = useState<ResumeParseResult | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const [importError, setImportError] = useState('')
  const applying = useRef(false)
  const [dragOver, setDragOver] = useState(false)
  const [parseMode, setParseMode] = useState<ResumeParseMode>('offline')

  async function runParse(target: File) {
    try {sessionStorage.setItem('applyguard.review.importStartedAt',String(Date.now()))} catch { /* optional local timing */ }
    setStatus('loading')
    setErrorMsg('')
    setParsed(null)
    setImportError('')
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

  function applyToVault() {
    if (!parsed || status !== 'success' || applying.current) return
    applying.current = true
    try {
      queueResumeImport(parsed)
      completeGuideStep('import')
      navigate('/vault')
    } catch {
      applying.current = false
      setImportError('暂时无法保留识别结果，请保留此页并重试。')
    }
  }

  const basic = parsed?.form.basic

  return (
    <section className="panel import-page">
      <div className="home-intro">
        <header className="panel-head home-intro-copy">
          <div>
            <h2>简历导入</h2>
            <p>识别简历后，一键带入经历库，再编辑保存。</p>
              <p className="muted">{connections?`GitHub 私库${connections.github?'已授权':'未连接'} · DeepSeek Harness ${{paired:'已配对',authorized:'已授权，等待配对',none:'未连接'}[connections.harness]??'未连接'}`:'正在检查本机连接…'} · <Link to="/evidence">选择材料来源</Link></p>
          </div>
          <div className="home-actions">
            <Button asChild variant="secondary"><Link to="/vault">继续编辑经历库</Link></Button>
            <Button data-guide="import" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={status === 'loading'} onClick={() => parsed && status === 'success' ? applyToVault() : fileInput.current?.click()}>{status === 'loading' ? '正在识别…' : parsed && status === 'success' ? '导入到经历库' : '选择简历'} <Icon name="arrow" /></Button>
          </div>
        </header>
      <Card asChild><section id="resume-import" className="import-card" aria-labelledby="resume-import-title">
      <CardHeader>
        <CardTitle asChild><h3 id="resume-import-title">上传 PDF</h3></CardTitle>
      </CardHeader>
      <label className="field-label" htmlFor="resume-parse-mode">识别方式</label>
      <select id="resume-parse-mode" value={parseMode} disabled={status === 'loading'}
        onChange={(event) => { setParseMode(event.target.value as ResumeParseMode); setParsed(null); setImportError(''); setStatus('idle') }}>
        <option value="offline">本地自动识别（默认，不调用模型）</option>
        <option value="offline_ocr">本地 OCR（图片或扫描件）</option>
        <option value="dynamic">模型抽取（发送简历正文，可能产生费用）</option>
      </select>
      <p className="mode-note">{parseMode === 'offline' ? '优先提取文字；遇到扫描页时自动使用本地 OCR（最多 5 页）。如组件不可用，页面会提示配置；识别结果请逐项核对。' : parseMode === 'offline_ocr' ? '在本机逐页识别，最多 5 页；如 OCR 组件不可用，页面会提示配置。识别可能耗时较长，结果须逐项核对。' : '正文和文件名将发送给后端配置的模型服务，可能产生费用；请先脱敏。'}</p>
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
          if (next && status !== 'loading' && !applying.current) {
            setFile(next)
            void runParse(next)
          }
        }}
      >
        <input
          ref={fileInput}
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
              event.target.value = ''
              void runParse(next)
            }
          }}
        />
        <span className="upload-document"><Icon name="upload" /></span>
        <span className="upload-copy">
          <strong>{file ? file.name : '把简历拖到这里'}</strong>
          <span className="upload-choice">或 <span>选择文件</span></span>
          <span className="muted" id="upload-requirements">单个 PDF，最大 5 MB；扫描件自动使用本地 OCR（最多 5 页）。</span>
        </span>
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
          <p>点击上方“导入到经历库”，即可在经历库中编辑、补充和保存。</p>
          {importError && <p role="alert" className="callout warn">{importError}</p>}
          <button type="button" className="text-action" onClick={() => fileInput.current?.click()}>重新选择简历</button>
          {parsed.source_text || parsed.preview ? (
            <>
              <p className="field-label">识别原文</p>
              <pre className="copy-pack jd-input">{parsed.source_text ?? parsed.preview}</pre>
            </>
          ) : null}
        </div>
      )}

      <p className="muted"><Link to="/vault">也可以先手动填写经历</Link></p>
      </section></Card>
        <Suspense fallback={<Card className="home-reel-loading" role="status">正在加载 24 秒操作介绍…</Card>}>
          <ProjectReel variant="home" />
        </Suspense>
      </div>
      <div className="home-resources">
        <Card asChild><section className="import-context" aria-labelledby="import-context-title">
        <CardHeader asChild><header className="home-resources-heading">
          <CardTitle asChild><h3 id="import-context-title">申请流程</h3></CardTitle>
          <Link to="/help" className="text-action">查看完整操作说明 <Icon name="arrow" /></Link>
        </header></CardHeader>
        <ol className="import-journey">
          <li><Icon name="folder" /><div><strong>把经历整理好</strong><p>集中保存教育、项目和实习，建立自己的经历库。</p></div></li>
          <li><Icon name="spark" /><div><strong>让表达更贴合岗位</strong><p>检索相关经历，生成可对照原文的润色建议。</p></div></li>
          <li><Icon name="shield" /><div><strong>逐项核对，再由你确认</strong><p>检查职责、技术、数字与时间，保留版本和修改记录。</p></div></li>
        </ol>
        </section></Card>
        <DemoQuickStart />
      </div>
    </section>
  )
}
