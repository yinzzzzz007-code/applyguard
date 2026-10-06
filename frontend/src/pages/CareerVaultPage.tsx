import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DEFAULT_CANDIDATE, getApiClient } from '../api/client'
import type {
  CareerVaultSeed,
  EditableResumeForm,
  PdfResumePreview,
  ResumeAward,
  ResumeEducation,
  ResumeExperienceEntry,
} from '../api/types'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import {
  buildResumeFormFromVault,
  buildResumeFormFromPdf,
  newExperienceId,
  resumeCompleteness,
} from '../resume/formModel'
import {
  DEGREE_OPTIONS,
  ETHNICITY_OPTIONS,
  FULL_TIME_OPTIONS,
  GENDER_OPTIONS,
  ID_TYPE_OPTIONS,
  MONTH_OPTIONS,
  POLITICS_OPTIONS,
  PROJECT_TYPE_OPTIONS,
  PROVINCES,
  REGION_TREE,
  YEAR_OPTIONS,
  dayOptions,
  joinDate,
  joinRegion,
  splitDate,
  splitRegion,
} from '../resume/options'

const SECTIONS = [
  { id: 'basic', label: '基本信息' },
  { id: 'intention', label: '求职意向' },
  { id: 'education', label: '教育经历' },
  { id: 'internship', label: '实习经历' },
  { id: 'project', label: '项目经历' },
  { id: 'awards', label: '获奖 / 竞赛' },
  { id: 'skills', label: '技能 / 其他' },
  { id: 'evidence', label: '证据溯源' },
] as const

function FieldShell({
  label,
  required,
  wide,
  children,
}: {
  label: string
  required?: boolean
  wide?: boolean
  children: React.ReactNode
}) {
  return (
    <div className={wide ? 'resume-field resume-field-wide' : 'resume-field'}>
      <label>
        {required ? <span className="req">*</span> : null}
        {label}
      </label>
      {children}
    </div>
  )
}

function FieldInput({
  label,
  value,
  required,
  wide,
  multiline,
  placeholder,
  onChange,
}: {
  label: string
  value: string
  required?: boolean
  wide?: boolean
  multiline?: boolean
  placeholder?: string
  onChange: (v: string) => void
}) {
  return (
    <FieldShell label={label} required={required} wide={wide}>
      {multiline ? (
        <textarea
          className="resume-input"
          aria-label={label}
          rows={4}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          className="resume-input"
          aria-label={label}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </FieldShell>
  )
}

function FieldSelect({
  label,
  value,
  options,
  required,
  wide,
  placeholder = '请选择',
  onChange,
}: {
  label: string
  value: string
  options: string[]
  required?: boolean
  wide?: boolean
  placeholder?: string
  onChange: (v: string) => void
}) {
  return (
    <FieldShell label={label} required={required} wide={wide}>
      <select
        className="resume-input resume-select"
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </FieldShell>
  )
}

/** 出生日期：年 / 月 / 日 下拉（校招常见日期选取） */
function BirthDateSelect({
  value,
  onChange,
}: {
  value: string
  onChange: (v: string) => void
}) {
  const { y, m, d } = splitDate(value)
  const days = dayOptions(y, m)
  const setPart = (nextY: string, nextM: string, nextD: string) => {
    const validDays = dayOptions(nextY, nextM)
    const day = validDays.includes(nextD) ? nextD : validDays[validDays.length - 1] || ''
    onChange(joinDate(nextY, nextM, day))
  }
  return (
    <FieldShell label="出生日期" required>
      <div className="resume-triple">
        <select
          className="resume-input resume-select"
          value={y}
          aria-label="年"
          onChange={(e) => setPart(e.target.value, m || '01', d || '01')}
        >
          <option value="">年</option>
          {YEAR_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt}年
            </option>
          ))}
        </select>
        <select
          className="resume-input resume-select"
          value={m}
          aria-label="月"
          onChange={(e) => setPart(y || String(new Date().getFullYear() - 20), e.target.value, d || '01')}
        >
          <option value="">月</option>
          {MONTH_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {Number(opt)}月
            </option>
          ))}
        </select>
        <select
          className="resume-input resume-select"
          value={d}
          aria-label="日"
          onChange={(e) => setPart(y || String(new Date().getFullYear() - 20), m || '01', e.target.value)}
        >
          <option value="">日</option>
          {days.map((opt) => (
            <option key={opt} value={opt}>
              {Number(opt)}日
            </option>
          ))}
        </select>
      </div>
    </FieldShell>
  )
}

/** 现居住地 / 户口所在地：省 → 市 级联下拉 */
function RegionSelect({
  label,
  value,
  required,
  onChange,
}: {
  label: string
  value: string
  required?: boolean
  onChange: (v: string) => void
}) {
  const { province, city } = splitRegion(value)
  const cities = province ? REGION_TREE[province] ?? [] : []
  return (
    <FieldShell label={label} required={required}>
      <div className="resume-triple resume-dual">
        <select
          className="resume-input resume-select"
          value={province}
          aria-label={`${label}-省`}
          onChange={(e) => {
            const p = e.target.value
            const nextCities = REGION_TREE[p] ?? []
            onChange(joinRegion(p, nextCities[0] ?? ''))
          }}
        >
          <option value="">请选择省 / 直辖市</option>
          {PROVINCES.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <select
          className="resume-input resume-select"
          value={city}
          disabled={!province}
          aria-label={`${label}-市`}
          onChange={(e) => onChange(joinRegion(province, e.target.value))}
        >
          <option value="">请选择城市 / 区</option>
          {cities.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    </FieldShell>
  )
}

function ExperienceEditor({
  entry,
  mode,
  onChange,
  onRemove,
}: {
  entry: ResumeExperienceEntry
  mode: 'internship' | 'project'
  onChange: (next: ResumeExperienceEntry) => void
  onRemove: () => void
}) {
  const set = (key: keyof ResumeExperienceEntry, value: string) =>
    onChange({ ...entry, [key]: value })

  return (
    <div className="resume-entry">
      <div className="resume-entry-bar">
        <span className="muted">{mode === 'internship' ? '实习' : '项目'}条目</span>
        <button type="button" className="btn ghost-danger" onClick={onRemove}>
          删除
        </button>
      </div>
      <div className="resume-fields">
        {mode === 'internship' ? (
          <>
            <FieldInput
              label="公司 / 组织"
              value={entry.organization}
              required
              onChange={(v) => set('organization', v)}
            />
            <FieldInput
              label="职位"
              value={entry.role || entry.title}
              required
              onChange={(v) => onChange({ ...entry, role: v, title: v })}
            />
          </>
        ) : (
          <>
            <FieldInput
              label="项目名称"
              value={entry.title}
              required
              onChange={(v) => set('title', v)}
            />
            <FieldInput label="担任角色" value={entry.role} required onChange={(v) => set('role', v)} />
          </>
        )}
        <FieldInput label="开始时间" value={entry.start} required onChange={(v) => set('start', v)} />
        <FieldInput label="结束时间" value={entry.end} required onChange={(v) => set('end', v)} />
        {mode === 'project' ? (
          <FieldInput
            label="所属组织"
            value={entry.organization}
            onChange={(v) => set('organization', v)}
          />
        ) : null}
        <FieldInput
          label="工作 / 项目描述"
          value={entry.description}
          required
          wide
          multiline
          placeholder="职责、技术栈、量化结果…"
          onChange={(v) => set('description', v)}
        />
      </div>
    </div>
  )
}

function AwardEditor({ entry, onChange, onRemove }: {
  entry: ResumeAward
  onChange: (next: ResumeAward) => void
  onRemove: () => void
}) {
  const set = (key: keyof ResumeAward, value: string) => onChange({ ...entry, [key]: value })
  return (
    <div className="resume-entry">
      <div className="resume-entry-bar">
        <span className="muted">竞赛 / 获奖条目 · {entry.rank || '名次待确认'}</span>
        <button type="button" className="btn ghost-danger" onClick={onRemove}>删除</button>
      </div>
      <div className="resume-fields">
        <FieldInput label="竞赛或奖项名称" value={entry.name} required wide onChange={(v) => set('name', v)} />
        <FieldSelect label="类别" value={entry.category} options={['竞赛', '奖学金', '荣誉', '其他']} onChange={(v) => set('category', v)} />
        <FieldSelect label="级别" value={entry.level} options={['国际级', '国家级', '省级', '市级', '校级', '其他']} onChange={(v) => set('level', v)} />
        <FieldInput label="主办方" value={entry.organizer} onChange={(v) => set('organizer', v)} />
        <FieldInput label="获奖名次 / 结果" value={entry.rank} placeholder="未知则留空，不推断获奖" onChange={(v) => set('rank', v)} />
        <FieldInput label="时间（YYYY-MM）" value={entry.date} onChange={(v) => set('date', v)} />
        <FieldInput label="本人角色" value={entry.role} onChange={(v) => set('role', v)} />
      </div>
      {entry.sourceLine ? <p className="resume-hint">来源{entry.sourcePage ? `：PDF 第 ${entry.sourcePage} 页` : ''}：{entry.sourceLine}</p> : null}
      <p className="resume-hint">本条尚无证明材料，不能直接成为可复制的已核验陈述。</p>
    </div>
  )
}

export function CareerVaultPage() {
  const navigate = useNavigate()
  const { scenario, resumeForm, setResumeForm, setWorkflow } = useDemo()
  const [status, setStatus] = useState<'loading' | 'success' | 'empty' | 'error'>('loading')
  const [vault, setVault] = useState<CareerVaultSeed | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [activeSection, setActiveSection] = useState<string>('basic')
  const [saveMsg, setSaveMsg] = useState('')
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const latestFormRef = useRef<EditableResumeForm | null>(null)
  const [pdfPreview, setPdfPreview] = useState<PdfResumePreview | null>(null)
  const [pdfName, setPdfName] = useState('')
  const [pdfStatus, setPdfStatus] = useState<'idle' | 'extracting' | 'ready' | 'error'>('idle')
  const [pdfError, setPdfError] = useState('')

  useEffect(() => {
    latestFormRef.current = resumeForm
  }, [resumeForm])

  const load = useCallback(async () => {
    setStatus('loading')
    setErrorMsg('')
    setSaveMsg('')
    const res = await getApiClient().getCareerVault()
    if (res.error) {
      setErrorMsg(res.error.message)
      setStatus('error')
      return
    }
    if (!res.data) {
      setStatus('empty')
      return
    }
    setVault(res.data)
    const draft = await getApiClient().getResumeDraft()
    if (draft.error) {
      setErrorMsg(draft.error.message)
      setStatus('error')
      return
    }
    setResumeForm((prev) => {
      if (prev && prev.candidateId === res.data!.candidate_id) return prev
      if (draft.data?.form?.candidateId === res.data!.candidate_id) return draft.data.form
      return buildResumeFormFromVault(res.data!)
    })
    setSaveStatus(draft.data ? 'saved' : 'idle')
    setStatus('success')
  }, [setResumeForm])

  useEffect(() => {
    void load()
  }, [load, scenario])

  const form = resumeForm

  const patchForm = (updater: (prev: EditableResumeForm) => EditableResumeForm) => {
    if (!resumeForm) return
    const next = { ...updater(resumeForm), dirty: true }
    latestFormRef.current = next
    setResumeForm(next)
    setWorkflow(null)
    setSaveStatus('idle')
    setSaveMsg('')
  }

  const completeness = useMemo(() => (form ? resumeCompleteness(form) : 0), [form])

  const scrollTo = (id: string) => {
    setActiveSection(id)
    document.getElementById(`resume-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const saveLocal = async () => {
    if (!form) return
    setSaveStatus('saving')
    const result = await getApiClient().saveResumeDraft(form)
    if (result.error || !result.data) {
      setSaveStatus('error')
      setSaveMsg(result.error?.message ?? '保存失败，请重试。')
      return
    }
    const stillCurrent = latestFormRef.current === form
    if (stillCurrent) {
      latestFormRef.current = result.data.form
      setResumeForm(result.data.form)
    }
    const latest = await getApiClient().getCareerVault()
    if (latest.data) setVault(latest.data)
    setSaveStatus(stillCurrent ? 'saved' : 'idle')
    setSaveMsg(stillCurrent ? '已保存到本机后端 data/local/，重新打开页面可恢复。' : '较早版本已保存；当前修改仍未保存，请再次保存。')
  }

  const selectPdf = async (file?: File) => {
    setPdfPreview(null)
    setPdfError('')
    if (!file) return
    setPdfName(file.name)
    setPdfStatus('extracting')
    const result = await getApiClient().extractResumePdf(file)
    if (result.error || !result.data) {
      setPdfStatus('error')
      setPdfError(result.error?.message ?? '提取失败，请直接填写经历库。')
      return
    }
    setPdfPreview(result.data)
    setPdfStatus('ready')
  }

  const confirmPdfReplacement = async () => {
    if (!pdfPreview) return
    if (!window.confirm('确认用 PDF 提取稿替换当前简历？旧经历及其证据将退出活动版本；保存失败则保留原稿。')) return
    const replacement = buildResumeFormFromPdf(pdfPreview, form?.candidateId ?? vault?.candidate_id ?? DEFAULT_CANDIDATE)
    setSaveStatus('saving')
    const result = await getApiClient().saveResumeDraft(replacement)
    if (result.error || !result.data) {
      setSaveStatus('error')
      setPdfError(result.error?.message ?? '替换保存失败，原稿未变更。')
      return
    }
    setResumeForm(result.data.form)
    setWorkflow(null)
    const latest = await getApiClient().getCareerVault()
    if (latest.data) setVault(latest.data)
    setPdfPreview(null)
    setPdfStatus('idle')
    setSaveStatus('saved')
    setSaveMsg('PDF 提取稿已替换并保存；旧经历与旧证据已退出活动版本，请逐项核对后再匹配。')
  }

  const resetFromSeed = () => {
    if (!vault) return
    if (!window.confirm('用种子数据覆盖当前编辑？未保存修改将丢失。')) return
    void fetch(`${import.meta.env.BASE_URL}data/career-vault.seed.json`)
      .then((res) => res.json())
      .then((seed: CareerVaultSeed) => {
        setResumeForm({ ...buildResumeFormFromVault(seed), dirty: true, savedAt: undefined })
        setWorkflow(null)
        setSaveStatus('idle')
        setSaveMsg('已载入种子，尚未保存；保存后才替换当前草稿。')
      })
      .catch(() => {
        setSaveStatus('error')
        setSaveMsg('种子载入失败。')
      })
  }

  return (
    <section className="panel resume-panel">
      <header className="panel-head">
        <h2>经历库 · 简历编辑</h2>
        <p>
          可编辑表单，布局参考腾讯校招简历页。保存到本机后端，不会提交招聘网站；编辑经历后必须重新核验，旧证据不会自动继承。
        </p>
      </header>

      <section className="item-block" aria-label="PDF 简历导入">
        <h3>第一步前：可选 PDF 导入</h3>
        <p className="muted">可跳过，直接填写经历库。文本 PDF 自动提取后先预览；确认替换才写入本地草稿。扫描件暂不支持 OCR。</p>
        <label className="field-label" htmlFor="resume-pdf">选择 PDF 简历（不超过 8 MB、20 页）</label>
        <input id="resume-pdf" type="file" accept=".pdf,application/pdf" onChange={(event) => void selectPdf(event.target.files?.[0])} />
        {pdfStatus === 'extracting' ? <p className="muted">正在提取 {pdfName}…</p> : null}
        {pdfError ? <p className="danger-text" role="alert">{pdfError}</p> : null}
        {pdfPreview ? (
          <div className="callout warn">
            <strong>提取预览：{pdfName} · {pdfPreview.page_count} 页</strong>
            <p>姓名：{pdfPreview.basic.name || '待手填'}；教育 {pdfPreview.education.length} 条；实习 {pdfPreview.internships.length} 条；项目 {pdfPreview.projects.length} 条；竞赛 / 奖项 {pdfPreview.awards.length} 条。</p>
            {pdfPreview.awards.map((award) => <p key={award.id}>竞赛 / 奖项：{award.name} · {award.rank || '名次未识别'}（第 {award.sourcePage} 页）</p>)}
            {pdfPreview.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            <div className="btn-row">
              <button type="button" className="btn primary" disabled={saveStatus === 'saving'} onClick={() => void confirmPdfReplacement()}>确认替换并保存</button>
              <button type="button" className="btn secondary" onClick={() => { setPdfPreview(null); setPdfStatus('idle') }}>取消预览</button>
            </div>
          </div>
        ) : null}
      </section>

      {status === 'loading' && <LoadingState label="正在加载简历库…" />}
      {status === 'error' && (
        <ErrorState message={errorMsg} onRetry={() => void load()} onFallback={() => navigate('/')} />
      )}
      {status === 'empty' && (
        <EmptyState
          title="暂无简历数据"
          detail="种子数据为空。"
          actionLabel="重新加载"
          onAction={() => void load()}
        />
      )}

      {status === 'success' && vault && form && (
        <>
          <div className={`resume-toolbar${!form.dirty && form.savedAt ? ' saved' : ''}`}>
            <div>
              <strong>简历完整度 {completeness}%</strong>
              <div className="resume-progress">
                <span style={{ width: `${completeness}%` }} />
              </div>
            </div>
            <span className="resume-tip">
              {vault.candidate_id}
              {form.dirty ? ' · 有未保存修改' : form.savedAt ? ` · 已保存 ${form.savedAt}` : ''}
            </span>
          </div>
          {saveMsg ? <p className={saveStatus === 'error' ? 'danger-text tip-inline' : 'ok-text tip-inline'}>{saveMsg}</p> : null}

          <div className="resume-layout">
            <aside className="resume-side">
              <p className="resume-side-title">简历模块</p>
              <nav>
                {SECTIONS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={activeSection === s.id ? 'resume-side-item active' : 'resume-side-item'}
                    onClick={() => scrollTo(s.id)}
                  >
                    {s.label}
                  </button>
                ))}
              </nav>
            </aside>

            <div className="resume-main">
              <section id="resume-basic" className="resume-section">
                <h3>
                  <i />
                  基本信息
                </h3>
                <div className="resume-fields">
                  <FieldInput
                    label="姓名"
                    required
                    value={form.basic.name}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, name: v } }))
                    }
                  />
                  <FieldSelect
                    label="性别"
                    required
                    options={GENDER_OPTIONS}
                    value={form.basic.gender}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, gender: v } }))
                    }
                  />
                  <BirthDateSelect
                    value={form.basic.birthday}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, birthday: v } }))
                    }
                  />
                  <FieldSelect
                    label="民族"
                    options={ETHNICITY_OPTIONS}
                    value={form.basic.ethnicity}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, ethnicity: v } }))
                    }
                  />
                  <FieldSelect
                    label="政治面貌"
                    options={POLITICS_OPTIONS}
                    value={form.basic.politics}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, politics: v } }))
                    }
                  />
                  <FieldInput
                    label="手机号码"
                    required
                    value={form.basic.phone}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, phone: v } }))
                    }
                  />
                  <FieldInput
                    label="电子邮箱"
                    required
                    value={form.basic.email}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, email: v } }))
                    }
                  />
                  <FieldSelect
                    label="证件类型"
                    required
                    options={ID_TYPE_OPTIONS}
                    value={form.basic.idType}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, idType: v } }))
                    }
                  />
                  <FieldInput
                    label="证件号码"
                    required
                    wide
                    value={form.basic.idNo}
                    placeholder="演示环境请勿填写真实证件号"
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, idNo: v } }))
                    }
                  />
                  <RegionSelect
                    label="现居住地"
                    required
                    value={form.basic.city}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, city: v } }))
                    }
                  />
                  <RegionSelect
                    label="户口所在地"
                    value={form.basic.hukou}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, hukou: v } }))
                    }
                  />
                </div>
              </section>

              <section id="resume-intention" className="resume-section">
                <h3>
                  <i />
                  求职意向
                </h3>
                <div className="resume-fields">
                  <FieldSelect
                    label="招聘项目"
                    required
                    options={PROJECT_TYPE_OPTIONS}
                    value={form.intention.projectType}
                    onChange={(v) =>
                      patchForm((p) => ({
                        ...p,
                        intention: { ...p.intention, projectType: v },
                      }))
                    }
                  />
                  <FieldInput
                    label="期望职位"
                    required
                    value={form.intention.expectRole}
                    onChange={(v) =>
                      patchForm((p) => ({
                        ...p,
                        intention: { ...p.intention, expectRole: v },
                      }))
                    }
                  />
                  <FieldInput
                    label="期望城市"
                    required
                    value={form.intention.expectCity}
                    onChange={(v) =>
                      patchForm((p) => ({
                        ...p,
                        intention: { ...p.intention, expectCity: v },
                      }))
                    }
                  />
                  <FieldInput
                    label="到岗时间"
                    value={form.intention.availability}
                    onChange={(v) =>
                      patchForm((p) => ({
                        ...p,
                        intention: { ...p.intention, availability: v },
                      }))
                    }
                  />
                </div>
              </section>

              <section id="resume-education" className="resume-section">
                <h3>
                  <i />
                  教育经历
                </h3>
                <p className="resume-hint">请按照从新到旧的顺序填写</p>
                {form.education.map((edu, idx) => (
                  <div key={edu.id} className="resume-entry">
                    <div className="resume-fields">
                      <FieldInput
                        label="学校"
                        required
                        value={edu.school}
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, school: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                      <FieldSelect
                        label="学历"
                        required
                        options={DEGREE_OPTIONS}
                        value={edu.degree}
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, degree: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                      <FieldInput
                        label="专业"
                        required
                        value={edu.major}
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, major: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                      <FieldSelect
                        label="是否全日制"
                        required
                        options={FULL_TIME_OPTIONS}
                        value={edu.fullTime}
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, fullTime: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                      <FieldInput
                        label="入学时间"
                        required
                        value={edu.start}
                        placeholder="YYYY-MM"
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, start: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                      <FieldInput
                        label="毕业时间"
                        required
                        value={edu.end}
                        placeholder="YYYY-MM"
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, end: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                      <FieldInput
                        label="成绩 / 排名"
                        wide
                        value={edu.rank}
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, rank: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() =>
                    patchForm((p) => ({
                      ...p,
                      education: [
                        ...p.education,
                        {
                          id: newExperienceId('edu'),
                          school: '',
                          degree: '',
                          major: '',
                          fullTime: '是',
                          start: '',
                          end: '',
                          rank: '',
                        } satisfies ResumeEducation,
                      ],
                    }))
                  }
                >
                  + 添加教育经历
                </button>
              </section>

              <section id="resume-internship" className="resume-section">
                <h3>
                  <i />
                  实习经历
                </h3>
                <p className="resume-hint">按时间从新到旧；建议用数据展现实习成果</p>
                {form.internships.map((entry) => (
                  <ExperienceEditor
                    key={entry.id}
                    entry={entry}
                    mode="internship"
                    onChange={(next) =>
                      patchForm((p) => ({
                        ...p,
                        internships: p.internships.map((row) =>
                          row.id === entry.id ? next : row,
                        ),
                      }))
                    }
                    onRemove={() =>
                      patchForm((p) => ({
                        ...p,
                        internships: p.internships.filter((row) => row.id !== entry.id),
                      }))
                    }
                  />
                ))}
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() =>
                    patchForm((p) => ({
                      ...p,
                      internships: [
                        ...p.internships,
                        {
                          id: newExperienceId('intern'),
                          organization: '',
                          title: '',
                          role: '',
                          start: '',
                          end: '',
                          description: '',
                        },
                      ],
                    }))
                  }
                >
                  + 添加实习经历
                </button>
              </section>

              <section id="resume-project" className="resume-section">
                <h3>
                  <i />
                  项目经历
                </h3>
                <p className="resume-hint">可填写校园项目、竞赛、课程实践等</p>
                {form.projects.map((entry) => (
                  <ExperienceEditor
                    key={entry.id}
                    entry={entry}
                    mode="project"
                    onChange={(next) =>
                      patchForm((p) => ({
                        ...p,
                        projects: p.projects.map((row) => (row.id === entry.id ? next : row)),
                      }))
                    }
                    onRemove={() =>
                      patchForm((p) => ({
                        ...p,
                        projects: p.projects.filter((row) => row.id !== entry.id),
                      }))
                    }
                  />
                ))}
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() =>
                    patchForm((p) => ({
                      ...p,
                      projects: [
                        ...p.projects,
                        {
                          id: newExperienceId('proj'),
                          organization: '',
                          title: '',
                          role: '',
                          start: '',
                          end: '',
                          description: '',
                        },
                      ],
                    }))
                  }
                >
                  + 添加项目经历
                </button>
              </section>

              <section id="resume-awards" className="resume-section">
                <h3><i />获奖 / 竞赛</h3>
                <p className="resume-hint">如实填写参赛或获奖结果；未提供证据时不会自动升级为可复制陈述。</p>
                {(form.awards ?? []).map((award) => (
                  <AwardEditor
                    key={award.id}
                    entry={award}
                    onChange={(next) => patchForm((p) => ({ ...p, awards: (p.awards ?? []).map((item) => item.id === award.id ? next : item) }))}
                    onRemove={() => patchForm((p) => ({ ...p, awards: (p.awards ?? []).filter((item) => item.id !== award.id) }))}
                  />
                ))}
                <button type="button" className="btn secondary" onClick={() => patchForm((p) => ({
                  ...p, awards: [...(p.awards ?? []), { id: newExperienceId('award'), name: '', category: '竞赛', organizer: '', level: '', rank: '', date: '', role: '' }],
                }))}>+ 添加获奖 / 竞赛</button>
              </section>

              <section id="resume-skills" className="resume-section">
                <h3>
                  <i />
                  技能 / 其他
                </h3>
                <div className="resume-fields">
                  <FieldInput
                    label="专业技能"
                    required
                    wide
                    value={form.extras.skills}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, extras: { ...p.extras, skills: v } }))
                    }
                  />
                  <FieldInput
                    label="其他补充（不进入自动核验）"
                    wide
                    multiline
                    value={form.extras.awards}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, extras: { ...p.extras, awards: v } }))
                    }
                  />
                  <FieldInput
                    label="自我评价"
                    wide
                    multiline
                    value={form.extras.summary}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, extras: { ...p.extras, summary: v } }))
                    }
                  />
                </div>
              </section>

              <section id="resume-evidence" className="resume-section">
                <h3>
                  <i />
                  证据溯源（申请护栏）
                </h3>
                <p className="resume-hint">
                  当前已保存版本的陈述与证据。修改尚未保存时，此处仅代表上次保存的版本；保存后变更的经历不继承旧证据。
                </p>
                <div className="stack">
                  {vault.experiences.map((exp) => (
                    <article key={exp.experience_id} className="item-block">
                      <div className="item-head">
                        <h3>{exp.title ?? exp.role}</h3>
                        <span className="muted">{exp.experience_id}</span>
                      </div>
                      <ul>
                        {exp.claims.map((c) => (
                          <li key={c.claim_id}>
                            <strong>{c.claim_id}</strong>：{c.text}
                            <p className="muted">证据编号：{c.evidence_ids.join(', ')}</p>
                          </li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              </section>
            </div>
          </div>

          <div className="btn-row end">
            <button type="button" className="btn secondary" onClick={resetFromSeed}>
              从种子重载
            </button>
            <button type="button" className={saveStatus === 'saved' && !form.dirty ? 'btn resume-save saved' : 'btn resume-save'} disabled={saveStatus === 'saving'} onClick={() => void saveLocal()}>
              {saveStatus === 'saving' ? '保存中…' : saveStatus === 'saved' && !form.dirty ? '已保存' : '保存简历'}
            </button>
            <button type="button" className="btn primary" disabled={form.dirty || saveStatus === 'saving'} onClick={() => navigate('/jd')}>
              下一步：输入 JD
            </button>
          </div>
        </>
      )}
    </section>
  )
}
