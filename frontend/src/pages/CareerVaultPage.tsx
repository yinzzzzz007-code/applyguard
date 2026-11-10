import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getApiClient } from '../api/client'
import type {
  CareerVaultSeed,
  EditableResumeForm,
  EvidenceLink,
  ResumeAward,
  ResumeEducation,
  ResumeExperienceEntry,
} from '../api/types'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import {
  buildResumeFormFromVault,
  emptyResumeForm,
  newExperienceId,
  normalizeResumeForm,
  resumeCompleteness,
  syncAwardText,
} from '../resume/formModel'
import {
  DEGREE_OPTIONS,
  ETHNICITY_OPTIONS,
  EXPECTED_CITY_OPTIONS,
  EXPECTED_ROLE_OPTIONS,
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
] as const

function FieldShell({
  label,
  required,
  wide,
  htmlFor,
  children,
}: {
  label: string
  required?: boolean
  wide?: boolean
  htmlFor?: string
  children: React.ReactNode
}) {
  return (
    <div className={wide ? 'resume-field resume-field-wide' : 'resume-field'}>
      <label htmlFor={htmlFor}>
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
  type = "text",
  error,
  onChange,
}: {
  label: string
  value: string
  required?: boolean
  wide?: boolean
  multiline?: boolean
  placeholder?: string
  type?: "text" | "tel" | "email"
  error?: string
  onChange: (v: string) => void
}) {
  const id = useId()
  return (
    <FieldShell label={label} required={required} wide={wide} htmlFor={id}>
      {multiline ? (
        <textarea
          id={id}
          className="resume-input"
          rows={4}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          id={id}
          type={type}
          autoComplete={type === "text" ? undefined : type}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? id + "-error" : undefined}
          className="resume-input"
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {error && <p id={id + "-error"} className="danger-text">{error}</p>}
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
  showPreviousValue,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  required?: boolean
  wide?: boolean
  placeholder?: string
  showPreviousValue?: boolean
  onChange: (v: string) => void
}) {
  const id = useId()
  const previousValue = showPreviousValue && value && !options.includes(value) ? value : ''
  return (
    <FieldShell label={label} required={required} wide={wide} htmlFor={id}>
      <select
        id={id}
        className="resume-input resume-select"
        value={value}
        aria-describedby={previousValue ? `${id}-previous` : undefined}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {previousValue && <option value={previousValue} disabled>原值待重选</option>}
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
      {previousValue && <p id={`${id}-previous`} className="resume-hint intention-previous">
        原值：{previousValue}。可从列表重选或清空。
      </p>}
    </FieldShell>
  )
}

function CalendarField({ label, value, type, required, onChange }: {
  label: string
  value: string
  type: 'date' | 'month'
  required?: boolean
  onChange: (value: string) => void
}) {
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const isMonth = type === 'month'
  const isCalendarValue = (candidate: string) => {
    const fullDate = isMonth ? `${candidate}-01` : candidate
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fullDate) || fullDate.startsWith('0000')) return false
    const parsed = new Date(`${fullDate}T00:00:00Z`)
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === fullDate
  }
  const dateValue = isCalendarValue(value) ? value : ''
  const previousValue = value && !dateValue ? value : ''

  return (
    <FieldShell label={label} required={required} htmlFor={id}>
      <input
        id={id}
        ref={input}
        className="resume-input intention-date"
        type={type}
        value={dateValue}
        min={isMonth ? '0001-01' : '0001-01-01'}
        max={isMonth ? '9999-12' : '9999-12-31'}
        aria-describedby={previousValue ? `${id}-previous` : undefined}
        onChange={(event) => {
          const next = event.currentTarget.value
          if (event.currentTarget.validity.valid && (!next || isCalendarValue(next))) onChange(next)
        }}
      />
      {previousValue && <p id={`${id}-previous`} className="resume-hint intention-previous">
        原值：{previousValue}。选择{isMonth ? '年月' : '日期'}即可替换。
        {' '}
        <button type="button" className="text-action" onClick={() => {
          onChange('')
          input.current?.focus()
        }}>清除原值</button>
      </p>}
    </FieldShell>
  )
}

/** 出生日期：年 / 月 / 日 下拉（校招常见日期选取） */
const EXPERIENCE_YEARS = Array.from({ length: 81 }, (_, index) => String(new Date().getFullYear() + 10 - index))

function PrecisionDateField({ label, value, required, allowOngoing, onChange }: {
  label: string
  value: string
  required?: boolean
  allowOngoing?: boolean
  onChange: (value: string) => void
}) {
  const id = useId()
  const ongoing = /^(至今|现在|present|current|now)$/i.test(value)
  const valid = /^\d{4}(?:-\d{2}(?:-\d{2})?)?$/.test(value)
  const [year = '', month = '', day = ''] = valid ? value.split('-') : []
  const years = [...new Set([year, ...EXPERIENCE_YEARS])].filter(Boolean).sort().reverse()

  return <FieldShell label={label} required={required} htmlFor={id}>
    <div className="precision-date">
      <select id={id} aria-label={label + '年份'} value={ongoing ? 'ongoing' : year} className="resume-input"
        onChange={event => {
          const next = event.target.value
          onChange(next === 'ongoing' ? '至今' : [next, next && month].filter(Boolean).join('-'))
        }}>
        <option value="">选择年份</option>
        {allowOngoing && <option value="ongoing">至今</option>}
        {years.map(item => <option key={item} value={item}>{item} 年</option>)}
      </select>
      <select aria-label={label + '月份'} value={month} disabled={!year || ongoing} className="resume-input"
        onChange={event => onChange([year, event.target.value].filter(Boolean).join('-'))}>
        <option value="">仅年份</option>
        {MONTH_OPTIONS.map(item => <option key={item} value={item}>{item} 月</option>)}
      </select>
    </div>
    {day && <p className="resume-hint">已记录日期 {value}。调整年月会按新的精度保存。</p>}
    {!valid && value && !ongoing && <p className="resume-hint">原值 {value}。请选择年月，
      或 <button type="button" className="text-action" onClick={() => onChange('')}>清除原值</button>。</p>}
  </FieldShell>
}

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
    <FieldShell label="出生日期（选填）">
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
        <PrecisionDateField label="开始时间" value={entry.start} required onChange={(v) => set('start', v)} />
        <PrecisionDateField label="结束时间" value={entry.end} required allowOngoing onChange={(v) => set('end', v)} />
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

function AwardEditor({
  entry,
  onChange,
  onRemove,
}: {
  entry: ResumeAward
  onChange: (next: ResumeAward) => void
  onRemove: () => void
}) {
  const set = (key: keyof ResumeAward, value: string) => onChange({ ...entry, [key]: value })
  const [links, setLinks] = useState<EvidenceLink[]>([])

  useEffect(() => {
    void getApiClient()
      .listEvidenceLinks({ target_type: 'award', target_id: entry.id })
      .then((res) => setLinks(res.data ?? []))
  }, [entry.id])

  return (
    <div className="resume-entry">
      <div className="resume-entry-bar">
        <span className="muted">获奖条目</span>
        <button type="button" className="btn ghost-danger" onClick={onRemove}>
          删除
        </button>
      </div>
      <div className="resume-fields">
        <FieldInput label="奖项名称" value={entry.name} required onChange={(v) => set('name', v)} />
        <FieldInput label="颁发单位" value={entry.issuer} onChange={(v) => set('issuer', v)} />
        <PrecisionDateField label="获奖时间" value={entry.date} onChange={(v) => set('date', v)} />
        <FieldInput
          label="说明"
          value={entry.description}
          wide
          multiline
          placeholder="级别、名次、参赛形式等"
          onChange={(v) => set('description', v)}
        />
      </div>
      <div className="evidence-award-links">
        {links.length ? (
          <ul>
            {links.map((link) => (
              <li key={link.link_id}>
                <Link to={`/evidence?evidence_id=${link.evidence_id}&target_type=award&target_id=${entry.id}`}>
                  {link.evidence_id}
                </Link>
                <span className={link.link_state === 'STALE' ? 'danger-text' : 'muted'}>
                  {' '}
                  · {link.link_state}
                  {link.relative_path ? ` · ${link.relative_path} v${link.version}` : ''}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">尚未关联本地证据原件。</p>
        )}
        <Link
          className="btn secondary"
          to={`/evidence?target_type=award&target_id=${encodeURIComponent(entry.id)}`}
        >
          导入 / 关联证据
        </Link>
      </div>
    </div>
  )
}

export function CareerVaultPage() {
  const navigate = useNavigate()
  const { scenario, resumeForm, setResumeForm } = useDemo()
  const [status, setStatus] = useState<'loading' | 'success' | 'empty' | 'error'>('loading')
  const [vault, setVault] = useState<CareerVaultSeed | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [activeSection, setActiveSection] = useState<string>('basic')
  const [saveMsg, setSaveMsg] = useState('')
  const [saveKind, setSaveKind] = useState<'ok' | 'warn' | ''>('')
  const [saving,setSaving] = useState(false)
  const [beforeClear, setBeforeClear] = useState<EditableResumeForm | null>(null)
  const editRevision = useRef(0)

  const hasFormRef = useRef(false)
  hasFormRef.current = !!resumeForm

  const load = useCallback(async () => {
    // Avoid full-page flash back to「加载中」when form is already on screen
    if (!hasFormRef.current) setStatus('loading')
    setErrorMsg('')
    const [res, draft] = await Promise.all([
      getApiClient().getCareerVault(),
      getApiClient().getResumeDraft(),
    ])
    // 已保存草稿优先，读取失败时保留本标签页的表单。
    if (draft.data) {
      setVault(res.data ?? null)
      setResumeForm((prev) => {
        if (prev?.dirty && prev.candidateId === draft.data!.candidateId) {
          return normalizeResumeForm(prev)
        }
        const fromDisk = normalizeResumeForm(draft.data!)
        return { ...fromDisk, dirty: false }
      })
      const notice = sessionStorage.getItem('applyguard.importNotice')
      if (notice) {
        sessionStorage.removeItem('applyguard.importNotice')
        setSaveKind('ok')
        setSaveMsg(notice)
      }
      setStatus('success')
      return
    }
    if (draft.error && !hasFormRef.current) {
      setErrorMsg(draft.error.message)
      setStatus('error')
      return
    }
    if (res.error) {
      setErrorMsg(res.error.message)
      setStatus('error')
      return
    }
    if (res.empty || !res.data?.candidate_id) {
      setVault(res.data ?? null)
      setStatus('empty')
      return
    }
    setVault(res.data)
    setResumeForm((prev) => {
      if (
        prev &&
        prev.candidateId === res.data!.candidate_id &&
        prev.dirty
      ) {
        return normalizeResumeForm(prev)
      }
      return emptyResumeForm(res.data!.candidate_id)
    })
    const notice = sessionStorage.getItem('applyguard.importNotice')
    if (notice) {
      sessionStorage.removeItem('applyguard.importNotice')
      setSaveKind('ok')
      setSaveMsg(notice)
    }
    setStatus('success')
  }, [setResumeForm])

  useEffect(() => {
    void load()
  }, [load, scenario])

  const form = resumeForm
  const phone = form?.basic.phone.trim() ?? ''
  const email = form?.basic.email.trim() ?? ''
  const phoneError = phone && !/^(?:1[3-9]\d{9}|\+861[3-9]\d{9}|\+(?!86)[1-9]\d{6,14})$/.test(phone.replace(/[\s()-]/g, ''))
    ? '请输入有效手机号。其他地区号码请带国际区号。' : ''
  const emailError = email && !/^[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+$/.test(email)
    ? '请输入有效的电子邮箱。' : ''

  const patchForm = (updater: (prev: EditableResumeForm) => EditableResumeForm) => {
    if (!resumeForm) return
    editRevision.current += 1
    setResumeForm({ ...updater(resumeForm), dirty: true })
    setSaveKind('')
    setSaveMsg('')
  }

  const completeness = useMemo(() => (form ? resumeCompleteness(form) : 0), [form])

  const scrollTo = (id: string) => {
    setActiveSection(id)
    document.getElementById(`resume-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const saveLocal = async (): Promise<boolean> => {
    if (!form || saving) return false
    if (phoneError || emailError) {
      setSaveKind('warn')
      setSaveMsg('请先修正基本信息中的手机号或邮箱。')
      scrollTo('basic')
      document.querySelector<HTMLInputElement>('#resume-basic input[aria-invalid="true"]')?.focus()
      return false
    }
    const revision = editRevision.current
    setSaving(true)
    const saved = {
      ...form,
      dirty: false,
    }
    try {
        const res = await getApiClient().saveResumeDraft(saved, form.savedAt ?? null)
        if (res.error || !res.data?.saved) {
          setSaveKind('warn')
          setSaveMsg(`未保存到后端：${res.error?.message ?? '未收到保存确认'}`)
          return false
        }
        const savedAt = res.data.saved_at
        setBeforeClear(null)
        if (editRevision.current !== revision) {
          setResumeForm(prev => prev ? { ...prev, savedAt } : prev)
          setSaveKind('warn')
          setSaveMsg('上一版本已保存，刚才的新修改尚未保存，请再次保存。')
          return false
        }
        setResumeForm({ ...saved, savedAt })
        setSaveKind('ok')
        setSaveMsg('保存成功')
        return true
    } catch {setSaveKind('warn');setSaveMsg('保存未完成，请检查连接后重试。当前输入仍保留。');return false}
    finally {setSaving(false)}
  }

  const clearForm = () => {
    if (!form || saving || !window.confirm(
      '清空当前经历库表单？点「保存经历」后才会覆盖已保存的资料，原件仍可在材料库查看。')) return
    const blank = emptyResumeForm(form.candidateId)
    setBeforeClear(form)
    patchForm(() => ({ ...blank, basic: { ...blank.basic, idType: '' }, savedAt: form.savedAt }))
    setSaveKind('warn')
    setSaveMsg('表单已清空，尚未保存。可以撤销清空，或点「保存经历」应用。')
  }

  const undoClear = () => {
    if (!beforeClear || saving) return
    editRevision.current += 1
    setResumeForm(beforeClear)
    setBeforeClear(null)
    setSaveKind('ok')
    setSaveMsg('已恢复清空前的表单。')
  }

  const loadDemoResume = () => {
    if (!vault) return
    if (!window.confirm('载入虚构的演示简历？当前未保存的修改会丢失。再次保存时，演示简历会覆盖已保存的草稿。')) return
    setBeforeClear(null)
    setResumeForm({ ...buildResumeFormFromVault(vault), dirty: true, savedAt: resumeForm?.savedAt })
    setSaveKind('warn')
    setSaveMsg('已载入演示简历，尚未保存。')
  }

  return (
    <section className={`panel resume-panel ${form && !form.dirty && form.savedAt ? 'is-saved' : 'is-unsaved'}`}>
      <header className="panel-head">
        <h2>整理自己的经历</h2>
        <p>
          优先核对项目、实习与技能，保存后到 <Link to="/evidence">证明材料</Link> 补充依据。个人资料和教育信息按填写使用，不代表已被证据核验。
        </p>
      </header>

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

      {status === 'success' && form && (
        <>
          <div className={form.dirty || !form.savedAt ? 'resume-toolbar is-unsaved' : 'resume-toolbar is-saved'}>
            <div>
              <strong>核心资料准备度 {completeness}%</strong>
              <div className="resume-progress">
                <span style={{ width: `${completeness}%` }} />
              </div>
            </div>
            <div className="btn-row">
              <span className="resume-tip">
                {form.dirty || !form.savedAt ? '未保存' : `已保存${form.savedAt ? ` · ${new Date(form.savedAt).toLocaleString()}` : ''}`}
              </span>
              <button type="button" className={beforeClear ? 'btn secondary' : 'btn ghost-danger'} disabled={saving}
                onClick={beforeClear ? undoClear : clearForm}>{beforeClear ? '撤销清空' : '清空表单'}</button>
            </div>
          </div>
          {saveMsg ? (
            <div role="status" className={saveKind === 'ok' ? 'callout ok' : 'callout warn'}>{saveMsg}</div>
          ) : null}

          <p className="resume-hint">星号表示建议优先填写，可先保存不完整草稿。网申补充信息为选填，不影响准备度。</p>
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
                  <FieldInput
                    label="手机号码"
                    type="tel"
                    error={phoneError}
                    required
                    value={form.basic.phone}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, phone: v } }))
                    }
                  />
                  <FieldInput
                    label="电子邮箱"
                    type="email"
                    error={emailError}
                    required
                    value={form.basic.email}
                    onChange={(v) =>
                      patchForm((p) => ({ ...p, basic: { ...p.basic, email: v } }))
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
                </div>
                <details className="vault-optional"><summary>网申补充信息（选填）</summary>
                  <p className="resume-hint">仅在目标招聘表单确有需要时填写。演示请使用虚构信息；留空不影响整理经历和材料。</p>
                  <div className="resume-fields">
                    <FieldSelect label="性别" options={GENDER_OPTIONS} value={form.basic.gender} onChange={v => patchForm(p => ({...p,basic:{...p.basic,gender:v}}))} />
                    <BirthDateSelect value={form.basic.birthday} onChange={v => patchForm(p => ({...p,basic:{...p.basic,birthday:v}}))} />
                    <FieldSelect label="民族" options={ETHNICITY_OPTIONS} value={form.basic.ethnicity} onChange={v => patchForm(p => ({...p,basic:{...p.basic,ethnicity:v}}))} />
                    <FieldSelect label="政治面貌" options={POLITICS_OPTIONS} value={form.basic.politics} onChange={v => patchForm(p => ({...p,basic:{...p.basic,politics:v}}))} />
                    <FieldSelect label="证件类型" options={ID_TYPE_OPTIONS} value={form.basic.idType} onChange={v => patchForm(p => ({...p,basic:{...p.basic,idType:v}}))} />
                    <FieldInput label="证件号码" value={form.basic.idNo} placeholder="演示请勿填写真实证件号" onChange={v => patchForm(p => ({...p,basic:{...p.basic,idNo:v}}))} />
                    <RegionSelect label="户口所在地" value={form.basic.hukou} onChange={v => patchForm(p => ({...p,basic:{...p.basic,hukou:v}}))} />
                  </div>
                </details>
              </section>

              <section id="resume-intention" className="resume-section">
                <h3>
                  <i />
                  求职意向
                </h3>
                <div className="resume-fields intention-fields">
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
                  <FieldSelect
                    label="期望职位"
                    required
                    options={EXPECTED_ROLE_OPTIONS}
                    placeholder="请选择职位"
                    showPreviousValue
                    value={form.intention.expectRole}
                    onChange={(v) =>
                      patchForm((p) => ({
                        ...p,
                        intention: { ...p.intention, expectRole: v },
                      }))
                    }
                  />
                  <FieldSelect
                    label="期望城市"
                    required
                    options={EXPECTED_CITY_OPTIONS}
                    placeholder="请选择城市"
                    showPreviousValue
                    value={form.intention.expectCity}
                    onChange={(v) =>
                      patchForm((p) => ({
                        ...p,
                        intention: { ...p.intention, expectCity: v },
                      }))
                    }
                  />
                  <CalendarField
                    label="到岗时间"
                    type="date"
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
                      <CalendarField
                        label="入学时间"
                        type="month"
                        required
                        value={edu.start}
                        onChange={(v) =>
                          patchForm((p) => {
                            const education = p.education.map((row, i) =>
                              i === idx ? { ...row, start: v } : row,
                            )
                            return { ...p, education }
                          })
                        }
                      />
                      <CalendarField
                        label="毕业时间"
                        type="month"
                        required
                        value={edu.end}
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
                          fullTime: '',
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
                <h3>
                  <i />
                  获奖 / 竞赛
                </h3>
                <p className="resume-hint">竞赛、比赛、奖学金、荣誉称号等，可增删条目</p>
                {(form.awards ?? []).map((entry) => (
                  <AwardEditor
                    key={entry.id}
                    entry={entry}
                    onChange={(next) =>
                      patchForm((p) => {
                        const awards = (p.awards ?? []).map((row) => (row.id === entry.id ? next : row))
                        return { ...p, awards, extras: { ...p.extras, awards: syncAwardText(awards) } }
                      })
                    }
                    onRemove={() =>
                      patchForm((p) => {
                        const awards = (p.awards ?? []).filter((row) => row.id !== entry.id)
                        return { ...p, awards, extras: { ...p.extras, awards: syncAwardText(awards) } }
                      })
                    }
                  />
                ))}
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() =>
                    patchForm((p) => {
                      const awards = [
                        ...(p.awards ?? []),
                        { id: newExperienceId('award'), name: '', issuer: '', date: '', description: '' },
                      ]
                      return { ...p, awards, extras: { ...p.extras, awards: syncAwardText(awards) } }
                    })
                  }
                >
                  + 添加获奖
                </button>
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

            </div>
          </div>

          <div className="btn-row end">
            <button type="button" className="btn secondary" onClick={() => navigate('/')}>
              可选：简历识别
            </button>
            <button type="button" className="btn secondary" onClick={loadDemoResume} disabled={!vault || saving}>
              载入演示简历
            </button>
            <button type="button" className="btn secondary" disabled={saving} onClick={() => void saveLocal()}>
              {saving ? '正在保存…' : '保存经历'}
            </button>
            <button
              type="button"
              className="btn primary"
              disabled={saving}
              onClick={async () => {
                // Persist before leaving so returning from later steps doesn't look「被清空」
                if ((form.dirty || !form.savedAt) && !await saveLocal()) return
                navigate('/evidence?view=materials')
              }}
            >
              保存并补充证明材料
            </button>
          </div>
        </>
      )}
    </section>
  )
}
