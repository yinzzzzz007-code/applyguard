import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiClient } from '../api/client'
import type {
  CareerVaultSeed,
  EditableResumeForm,
  ResumeEducation,
  ResumeExperienceEntry,
} from '../api/types'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import {
  buildResumeFormFromVault,
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
          rows={4}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          className="resume-input"
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

export function CareerVaultPage() {
  const navigate = useNavigate()
  const { scenario, resumeForm, setResumeForm } = useDemo()
  const [status, setStatus] = useState<'loading' | 'success' | 'empty' | 'error'>('loading')
  const [vault, setVault] = useState<CareerVaultSeed | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const [activeSection, setActiveSection] = useState<string>('basic')
  const [saveMsg, setSaveMsg] = useState('')

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
    if (res.empty || !res.data?.experiences.length) {
      setVault(res.data ?? null)
      setStatus('empty')
      return
    }
    setVault(res.data)
    setResumeForm((prev) => {
      if (prev && prev.candidateId === res.data!.candidate_id) return prev
      try {
        const raw = sessionStorage.getItem('applyguard.resumeForm')
        if (raw) {
          const parsed = JSON.parse(raw) as EditableResumeForm
          if (parsed.candidateId === res.data!.candidate_id) return { ...parsed, dirty: false }
        }
      } catch {
        /* ignore */
      }
      return buildResumeFormFromVault(res.data!)
    })
    setStatus('success')
  }, [setResumeForm])

  useEffect(() => {
    void load()
  }, [load, scenario])

  const form = resumeForm

  const patchForm = (updater: (prev: EditableResumeForm) => EditableResumeForm) => {
    if (!resumeForm) return
    setResumeForm({ ...updater(resumeForm), dirty: true })
    setSaveMsg('')
  }

  const completeness = useMemo(() => (form ? resumeCompleteness(form) : 0), [form])

  const scrollTo = (id: string) => {
    setActiveSection(id)
    document.getElementById(`resume-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const saveLocal = () => {
    if (!form) return
    const saved = {
      ...form,
      dirty: false,
      savedAt: new Date().toLocaleString(),
    }
    setResumeForm(saved)
    try {
      sessionStorage.setItem('applyguard.resumeForm', JSON.stringify(saved))
    } catch {
      /* ignore quota */
    }
    setSaveMsg('已保存到本机会话。后端暂无经历库写入接口，刷新标签页前有效。')
  }

  const resetFromSeed = () => {
    if (!vault) return
    if (!window.confirm('用种子数据覆盖当前编辑？未保存修改将丢失。')) return
    setResumeForm(buildResumeFormFromVault(vault))
    setSaveMsg('已从种子数据重新载入。')
  }

  return (
    <section className="panel resume-panel">
      <header className="panel-head">
        <h2>经历库 · 简历编辑</h2>
        <p>
          可编辑表单，布局参考腾讯校招简历页。可改字段、增删实习/项目；「保存」写入浏览器会话，不上传招聘网站，也不写后端（尚无经历库保存接口）。
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

      {status === 'success' && vault && form && (
        <>
          <div className="resume-toolbar">
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
          {saveMsg ? <p className="ok-text tip-inline">{saveMsg}</p> : null}

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
                    label="获奖 / 补充"
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
                  来自种子经历库的陈述与证据（供后续核验）。编辑上方简历不会自动改后端证据图。
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
            <button type="button" className="btn secondary" onClick={saveLocal}>
              保存简历
            </button>
            <button type="button" className="btn primary" onClick={() => navigate('/jd')}>
              下一步：输入 JD
            </button>
          </div>
        </>
      )}
    </section>
  )
}
