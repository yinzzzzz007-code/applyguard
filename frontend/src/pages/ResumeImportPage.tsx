import { useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiClient, type WorkflowParseMode } from '../api/client'
import type { EditableResumeForm, ResumeParseResult } from '../api/types'
import { ErrorState, LoadingState } from '../components/States'
import { Icon } from '../components/Icon'
import { useDemo } from '../context/DemoContext'
import { normalizeResumeForm, overwriteFromExtracted, resumeSections, selectImportRows, syncAwardText } from '../resume/formModel'

const sectionLabels = { education: '教育经历', internships: '实习经历', projects: '项目经历', awards: '获奖 / 竞赛' }
const fieldLabels: Record<string, string> = {
  name: '姓名 / 名称', gender: '性别', birthday: '出生日期', ethnicity: '民族', politics: '政治面貌',
  phone: '手机', email: '邮箱', idType: '证件类型', idNo: '证件号码', city: '现居住地', hukou: '户籍',
  school: '学校', degree: '学历', major: '专业', fullTime: '全日制', rank: '成绩 / 排名',
  title: '名称', organization: '所属组织', role: '角色', start: '开始时间', end: '结束时间',
  description: '描述', issuer: '颁发单位', date: '获奖时间', projectType: '招聘项目',
  expectRole: '期望职位', expectCity: '期望城市', availability: '到岗时间', skills: '技能', awards: '获奖', summary: '自我介绍',
}

function ImportFields({ row, previous }: { row: object; previous?: object }) {
  const old = previous as Record<string, string> | undefined
  return <dl className="import-preview-fields">{Object.entries(row).filter(([key]) => fieldLabels[key]).map(([key, value]) =>
    <div key={key}><dt>{fieldLabels[key]}</dt><dd>{value || '未填写'}
      {old?.[key] && old[key] !== value && <small>原值：{old[key]}</small>}</dd></div>)}</dl>
}

function toggleId(set: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(set)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  return next
}

export function ResumeImportPage() {
  const navigate = useNavigate()
  const { resumeForm, setResumeForm } = useDemo()
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [parsed, setParsed] = useState<ResumeParseResult | null>(null)
  const [preview, setPreview] = useState<{ next: EditableResumeForm; previous: EditableResumeForm | null; expected: string | null } | null>(null)
  const [excluded, setExcluded] = useState<Set<string>>(new Set())
  const [removed, setRemoved] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const applying = useRef(false)
  const [dragOver, setDragOver] = useState(false)
  const [parseMode, setParseMode] = useState<WorkflowParseMode>('offline')
  const [guideDismissed,setGuideDismissed] = useState(() => {try {return sessionStorage.getItem('applyguard.welcome.dismissed') === 'true'} catch {return false}})

  async function runParse(target: File) {
    try {sessionStorage.setItem('applyguard.review.importStartedAt',String(Date.now()))} catch { /* optional local timing */ }
    setStatus('loading')
    setErrorMsg('')
    setParsed(null)
    setPreview(null)
    setSaveError('')
    setExcluded(new Set())
    setRemoved(new Set())
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
    await preparePreview(res.data)
    setStatus('success')
  }

  async function preparePreview(result: ResumeParseResult) {
    setSaveError('')
    const api = getApiClient()
    const [vault, saved] = await Promise.all([api.getCareerVault(), api.getResumeDraft()])
    const candidate = saved.data?.candidateId ?? resumeForm?.candidateId ?? vault.data?.candidate_id
    if (saved.error || !candidate) {
      setSaveError(saved.error?.message ?? '无法读取经历库，当前识别结果尚未写入。')
      return
    }
    const base = resumeForm?.dirty && resumeForm.candidateId === candidate ? resumeForm : saved.data
    const previous = base ? normalizeResumeForm(base) : null
    const next = overwriteFromExtracted(candidate, result.form, previous)
    setExcluded(new Set())
    setRemoved(new Set())
    setPreview({ next, previous, expected: saved.data?.savedAt ?? null })
  }

  async function applyToVault() {
    if (!preview || applying.current) return
    const { next, previous, expected } = preview
    const awards = selectImportRows(next.awards, previous?.awards ?? [], excluded, removed)
    const draft = {
      ...next,
      education: selectImportRows(next.education, previous?.education ?? [], excluded, removed),
      internships: selectImportRows(next.internships, previous?.internships ?? [], excluded, removed),
      projects: selectImportRows(next.projects, previous?.projects ?? [], excluded, removed),
      awards,
      extras: { ...next.extras, awards: syncAwardText(awards) || next.extras.awards },
      dirty: false,
    }
    if (previous && !window.confirm('写入本次核对的资料？基本信息、求职意向和技能将按预览更新。勾选移除的经历及其材料关联将退出当前简历。')) return
    applying.current = true
    setSaving(true)
    setSaveError('')
    try {
      const saved = await getApiClient().saveResumeDraft(draft, expected)
      if (!saved.data?.saved) {
        setSaveError(saved.error?.message ?? '后端未确认保存，请重试。')
        return
      }
      setResumeForm({ ...draft, savedAt: saved.data.saved_at })
      try { sessionStorage.setItem('applyguard.importNotice', '识别结果已保存到经历库，请核对并补全缺失项。') } catch { /* optional notice */ }
      navigate('/vault')
    } finally {
      applying.current = false
      setSaving(false)
    }
  }

  const basic = parsed?.form.basic

  return (
    <section className="panel import-page">
      <header className="panel-head">
        <h2>从真实经历，开始下一份申请。</h2>
        <p>导入简历、整理证据，再把你的经历表达得更好。</p>
      </header>
      {!guideDismissed && <div className="welcome-guide"><div><strong>第一次使用？先完成一条经历的申请准备。</strong><p>导入简历，补充证明材料，再选择岗位、审核并导出草稿。</p><Link to="/help" className="text-action">查看分步说明</Link></div>
        <button type="button" className="text-action" onClick={() => {setGuideDismissed(true);try {sessionStorage.setItem('applyguard.welcome.dismissed','true')} catch { /* optional preference */ }}}>收起提示</button></div>}
      <div className="import-layout">
      <div className="import-card">
      <div className="surface-heading"><h3>导入你的简历</h3><span className="quiet-label">PDF 文档</span></div>
      <p className="muted">识别基本信息与经历，写入前由你核对。</p>
      <label className="field-label" htmlFor="resume-parse-mode">识别方式</label>
      <select id="resume-parse-mode" value={parseMode} disabled={status === 'loading' || saving}
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
          if (next && status !== 'loading' && !applying.current) {
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
          disabled={status === 'loading' || saving}
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
          {preview && <>
            <details className="sample-data-note"><summary>核对基本信息、求职意向和技能</summary>
              <ImportFields row={preview.next.basic} previous={preview.previous?.basic} />
              <ImportFields row={preview.next.intention} previous={preview.previous?.intention} />
              <ImportFields row={preview.next.extras} previous={preview.previous?.extras} />
            </details>
            <p className="muted">展开每条经历核对字段。已有关联会随同一经历保留。旧条目默认保留，可勾选移除。</p>
            {resumeSections.map(section => <details key={section} className="sample-data-note">
              <summary>{sectionLabels[section]}（本次识别 {preview.next[section].length} 条）</summary>
              {preview.next[section].map((row, index) => {
                const old = preview.previous?.[section].find(item => item.id === row.id)
                return <details className="import-preview-row" key={row.id}>
                  <summary>{'school' in row ? row.school : 'name' in row ? row.name : row.title || row.organization}
                    {' · '}{old ? '已匹配原条目' : '新增'}</summary>
                  <label><input type="checkbox" checked={!excluded.has(row.id)} disabled={saving}
                    onChange={() => setExcluded(value => toggleId(value, row.id))} />
                    {old ? '按本次识别更新' : '加入第 ' + (index + 1) + ' 条'}</label>
                  <ImportFields row={row} previous={old} />
                </details>
              })}
              {preview.previous?.[section].filter(row => !preview.next[section].some(item => item.id === row.id)).map(row =>
                <details className="import-preview-row" key={row.id}><summary>原有条目 · {'school' in row ? row.school : 'name' in row ? row.name : row.title || row.organization}</summary>
                  <label><input type="checkbox" checked={removed.has(row.id)} disabled={saving}
                    onChange={() => setRemoved(value => toggleId(value, row.id))} />移除此条及其在当前简历中的材料关联</label>
                  <ImportFields row={row} /></details>)}
            </details>)}
          </>}
          {saveError && <div className="callout danger" role="alert">
            本次识别结果尚未写入。{saveError}
            <button className="text-action" type="button" onClick={() => void preparePreview(parsed)}>重新读取已有资料</button>
          </div>}
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
          disabled={!preview || status !== "success" || saving}
          onClick={() => void applyToVault()}
        >
          {saving ? "正在保存…" : "写入并核对"} <Icon name="arrow" />
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
