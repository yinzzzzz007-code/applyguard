import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { EmptyState, RiskBadge } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { loadApplicationHistory, removeApplicationHistory } from '../history'
import {
  RESUME_TEMPLATES,
  buildPlainResume,
  contactLine,
  formatDateRange,
  splitBullets,
  type ResumeTemplateId,
} from '../resume/generate'
import { normalizeResumeForm } from '../resume/formModel'
import type { EditableResumeForm } from '../api/types'

function storedResumeForm(): EditableResumeForm | null {
  try {
    const raw = sessionStorage.getItem('applyguard.resumeForm')
    return raw ? normalizeResumeForm(JSON.parse(raw) as EditableResumeForm) : null
  } catch {
    return null
  }
}

function cloneForm(form: EditableResumeForm): EditableResumeForm {
  return normalizeResumeForm(structuredClone(form))
}

function RemoveButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" className="resume-edit-remove" aria-label={label} title={label} onClick={onClick}>
      删除
    </button>
  )
}

function ResumePreview({
  form,
  template,
  editing,
  onChange,
}: {
  form: EditableResumeForm
  template: ResumeTemplateId
  editing: boolean
  onChange: (next: EditableResumeForm) => void
}) {
  const contacts = contactLine(form)
  const awards = form.awards ?? []
  const en = template.startsWith('en')

  const patchExtras = (patch: Partial<EditableResumeForm['extras']>) =>
    onChange({ ...form, extras: { ...form.extras, ...patch } })

  const removeContact = (value: string) => {
    const basic = { ...form.basic }
    if (basic.phone === value) basic.phone = ''
    else if (basic.email === value) basic.email = ''
    else if (basic.city === value) basic.city = ''
    else if (basic.github === value) basic.github = ''
    else if (basic.linkedin === value) basic.linkedin = ''
    else if (basic.website === value) basic.website = ''
    onChange({ ...form, basic })
  }

  const removeBullet = (
    kind: 'internship' | 'project',
    id: string,
    bullet: string,
  ) => {
    onChange({
      ...form,
      [kind === 'internship' ? 'internships' : 'projects']: form[kind === 'internship' ? 'internships' : 'projects'].map(
        (row) => {
          if (row.id !== id) return row
          const next = splitBullets(row.description).filter((item) => item !== bullet)
          return { ...row, description: next.join('\n') }
        },
      ),
    })
  }

  return (
    <article className={`resume-sheet resume-${template}${editing ? ' is-editing' : ''}`} id="resume-print-root">
      <header className="resume-sheet-head">
        <div className="resume-sheet-byline">
          <span className="resume-sheet-name">{form.basic.name || '未填写姓名'}</span>
          {contacts.length > 0 && (
            <span className="resume-sheet-contacts">
              {contacts.map((item, index) => (
                <span className="resume-sheet-contact-chip" key={`${item}-${index}`}>
                  {index > 0 ? <span aria-hidden="true"> · </span> : null}
                  {item}
                  {editing && <RemoveButton label={`删除联系方式 ${item}`} onClick={() => removeContact(item)} />}
                </span>
              ))}
            </span>
          )}
        </div>
        {template === 'cn-campus' && (form.intention.expectRole || form.intention.availability) && (
          <div className="resume-sheet-block">
            <p className="resume-sheet-intention">
              {[form.intention.expectRole, form.intention.expectCity, form.intention.availability]
                .filter(Boolean)
                .join(' · ')}
            </p>
            {editing && (
              <RemoveButton
                label="删除求职意向"
                onClick={() =>
                  onChange({
                    ...form,
                    intention: { ...form.intention, expectRole: '', expectCity: '', availability: '' },
                  })
                }
              />
            )}
          </div>
        )}
      </header>

      {form.extras.researchFocus.trim() && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Research Interests' : '研究兴趣'}</h2>
            {editing && (
              <RemoveButton label="删除研究兴趣" onClick={() => patchExtras({ researchFocus: '' })} />
            )}
          </div>
          <p>{form.extras.researchFocus}</p>
        </section>
      )}

      {form.education.some((row) => row.school.trim()) && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Education' : '教育经历'}</h2>
            {editing && (
              <RemoveButton
                label="删除全部教育经历"
                onClick={() => onChange({ ...form, education: [] })}
              />
            )}
          </div>
          {form.education.map((edu) =>
            edu.school.trim() ? (
              <div className="resume-sheet-entry" key={edu.id}>
                {editing && (
                  <RemoveButton
                    label={`删除教育经历 ${edu.school}`}
                    onClick={() =>
                      onChange({ ...form, education: form.education.filter((row) => row.id !== edu.id) })
                    }
                  />
                )}
                <div className="resume-sheet-line">
                  <strong>{edu.school}</strong>
                  <span>{formatDateRange(edu.start, edu.end)}</span>
                </div>
                <div className="resume-sheet-line muted-line">
                  <em>{[edu.degree, edu.major].filter(Boolean).join(' · ')}</em>
                  <span>{edu.location}</span>
                </div>
                {(edu.gpa || edu.rank) && (
                  <p className="resume-sheet-meta">
                    {[edu.gpa ? `GPA ${edu.gpa}` : '', edu.rank].filter(Boolean).join(' · ')}
                  </p>
                )}
                {edu.coursework.trim() && <p className="resume-sheet-meta">相关课程：{edu.coursework}</p>}
              </div>
            ) : null,
          )}
        </section>
      )}

      {form.internships.some((row) => row.organization.trim() || row.description.trim()) && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Experience' : '实习经历'}</h2>
            {editing && (
              <RemoveButton
                label="删除全部实习经历"
                onClick={() => onChange({ ...form, internships: [] })}
              />
            )}
          </div>
          {form.internships.map((row) =>
            row.organization.trim() || row.description.trim() ? (
              <div className="resume-sheet-entry" key={row.id}>
                {editing && (
                  <RemoveButton
                    label={`删除实习 ${row.organization || row.title}`}
                    onClick={() =>
                      onChange({
                        ...form,
                        internships: form.internships.filter((item) => item.id !== row.id),
                      })
                    }
                  />
                )}
                <div className="resume-sheet-line">
                  <strong>{row.organization || '未命名组织'}</strong>
                  <span>{formatDateRange(row.start, row.end)}</span>
                </div>
                <div className="resume-sheet-line muted-line">
                  <em>{[row.role || row.title, row.techStack].filter(Boolean).join(' · ')}</em>
                  <span>{row.location}</span>
                </div>
                {row.link.trim() && <p className="resume-sheet-link">{row.link}</p>}
                <ul>
                  {splitBullets(row.description).map((bullet) => (
                    <li key={bullet}>
                      <span>{bullet}</span>
                      {editing && (
                        <RemoveButton
                          label="删除这条要点"
                          onClick={() => removeBullet('internship', row.id, bullet)}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </section>
      )}

      {form.projects.some((row) => row.title.trim() || row.description.trim()) && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Projects' : '项目经历'}</h2>
            {editing && (
              <RemoveButton label="删除全部项目经历" onClick={() => onChange({ ...form, projects: [] })} />
            )}
          </div>
          {form.projects.map((row) =>
            row.title.trim() || row.description.trim() ? (
              <div className="resume-sheet-entry" key={row.id}>
                {editing && (
                  <RemoveButton
                    label={`删除项目 ${row.title || row.organization}`}
                    onClick={() =>
                      onChange({
                        ...form,
                        projects: form.projects.filter((item) => item.id !== row.id),
                      })
                    }
                  />
                )}
                <div className="resume-sheet-line">
                  <strong>
                    {row.title || row.organization || '未命名项目'}
                    {row.techStack ? <em className="resume-sheet-stack"> | {row.techStack}</em> : null}
                  </strong>
                  <span>{formatDateRange(row.start, row.end)}</span>
                </div>
                {(row.role || row.location) && (
                  <div className="resume-sheet-line muted-line">
                    <em>{row.role}</em>
                    <span>{row.location}</span>
                  </div>
                )}
                {row.link.trim() && <p className="resume-sheet-link">{row.link}</p>}
                <ul>
                  {splitBullets(row.description).map((bullet) => (
                    <li key={bullet}>
                      <span>{bullet}</span>
                      {editing && (
                        <RemoveButton
                          label="删除这条要点"
                          onClick={() => removeBullet('project', row.id, bullet)}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </section>
      )}

      {form.extras.publications.trim() && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Publications' : '论文 / 科研成果'}</h2>
            {editing && (
              <RemoveButton label="删除论文成果" onClick={() => patchExtras({ publications: '' })} />
            )}
          </div>
          <ul>
            {splitBullets(form.extras.publications).map((line) => (
              <li key={line}>
                <span>{line}</span>
                {editing && (
                  <RemoveButton
                    label="删除这条论文"
                    onClick={() =>
                      patchExtras({
                        publications: splitBullets(form.extras.publications)
                          .filter((item) => item !== line)
                          .join('\n'),
                      })
                    }
                  />
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {awards.some((row) => row.name.trim()) && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Honors & Awards' : '获奖 / 竞赛'}</h2>
            {editing && (
              <RemoveButton label="删除全部获奖" onClick={() => onChange({ ...form, awards: [] })} />
            )}
          </div>
          <ul>
            {awards
              .filter((row) => row.name.trim())
              .map((award) => (
                <li key={award.id}>
                  <span>
                    {[award.name, award.issuer, award.date].filter(Boolean).join(' · ')}
                    {award.description ? `：${award.description}` : ''}
                  </span>
                  {editing && (
                    <RemoveButton
                      label={`删除获奖 ${award.name}`}
                      onClick={() =>
                        onChange({
                          ...form,
                          awards: (form.awards ?? []).filter((row) => row.id !== award.id),
                        })
                      }
                    />
                  )}
                </li>
              ))}
          </ul>
        </section>
      )}

      {(form.extras.skills.trim() || form.extras.languages.trim()) && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Skills' : '专业技能'}</h2>
            {editing && (
              <RemoveButton
                label="删除专业技能"
                onClick={() => patchExtras({ skills: '', languages: '' })}
              />
            )}
          </div>
          {form.extras.skills.trim() && (
            <div className="resume-sheet-block">
              <p>{form.extras.skills}</p>
              {editing && (
                <RemoveButton label="删除技能正文" onClick={() => patchExtras({ skills: '' })} />
              )}
            </div>
          )}
          {form.extras.languages.trim() && (
            <div className="resume-sheet-block">
              <p>语言：{form.extras.languages}</p>
              {editing && (
                <RemoveButton label="删除语言能力" onClick={() => patchExtras({ languages: '' })} />
              )}
            </div>
          )}
        </section>
      )}

      {form.extras.summary.trim() && (
        <section className="resume-sheet-section">
          <div className="resume-sheet-section-head">
            <h2>{en ? 'Summary' : '自我评价'}</h2>
            {editing && (
              <RemoveButton label="删除自我评价" onClick={() => patchExtras({ summary: '' })} />
            )}
          </div>
          <p>{form.extras.summary}</p>
        </section>
      )}
    </article>
  )
}

export function ApplicationHistoryPage() {
  const navigate = useNavigate()
  const { resumeForm, workflow } = useDemo()
  const [records, setRecords] = useState(loadApplicationHistory)
  const [error, setError] = useState('')
  const [template, setTemplate] = useState<ResumeTemplateId>('cn-academic')
  const [copied, setCopied] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<EditableResumeForm | null>(null)

  const sourceForm = useMemo(() => {
    const source = resumeForm ?? storedResumeForm()
    return source ? normalizeResumeForm(source) : null
  }, [resumeForm])

  useEffect(() => {
    if (!sourceForm) {
      setDraft(null)
      return
    }
    setDraft((prev) => (prev ? prev : cloneForm(sourceForm)))
  }, [sourceForm])

  const form = draft
  const plain = useMemo(
    () => (form ? buildPlainResume(form, template) : ''),
    [form, template],
  )

  function remove(id: string) {
    if (!window.confirm('删除这条本地模拟记录？此操作无法撤销。')) return
    if (!removeApplicationHistory(id)) {
      setError('无法删除这条本地记录，请检查浏览器存储权限。')
      return
    }
    setRecords(loadApplicationHistory())
    setError('')
  }

  function resetDraft() {
    if (!sourceForm) return
    if (!window.confirm('恢复为经历库当前内容？预览里已删除的段落会回来。')) return
    setDraft(cloneForm(sourceForm))
  }

  function copyPlain() {
    void navigator.clipboard.writeText(plain).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    })
  }

  function downloadText() {
    const blob = new Blob([plain], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${form?.basic.name || 'resume'}.txt`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function printResume() {
    setEditing(false)
    window.setTimeout(() => window.print(), 0)
  }

  return (
    <section className="panel resume-generate-page">
      <header className="panel-head">
        <h2>简历生成</h2>
        <p>
          用经历库资料生成预览。可在下方直接删除不想要的段落；只影响本次导出，不会改经历库原文。
        </p>
      </header>

      {!form || !sourceForm ? (
        <EmptyState
          title="还没有可生成的简历资料"
          detail="请先到经历库填写并保存，再回到本页选择模板生成。"
          actionLabel="去经历库"
          onAction={() => navigate('/vault')}
        />
      ) : (
        <>
          <div className="profile-card">
            <p>
              当前资料：{sourceForm.basic.name || '未命名'}
              {workflow?.parsed_jd?.title
                ? ` · 关联岗位 ${workflow.parsed_jd.title === 'UNKNOWN' ? '未知岗位' : workflow.parsed_jd.title}`
                : ''}
            </p>
            <p className="muted">预览编辑只用于生成稿；要永久改内容请回经历库。</p>
            <div className="btn-row">
              <Link className="btn secondary" to="/vault">
                编辑经历库
              </Link>
              {RESUME_TEMPLATES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={template === item.id ? 'btn primary' : 'btn secondary'}
                  onClick={() => setTemplate(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <p className="muted">{RESUME_TEMPLATES.find((item) => item.id === template)?.hint}</p>
            <div className="btn-row">
              <button
                type="button"
                className={editing ? 'btn primary' : 'btn secondary'}
                onClick={() => setEditing((value) => !value)}
              >
                {editing ? '完成编辑' : '编辑预览（可删除）'}
              </button>
              <button type="button" className="btn secondary" onClick={resetDraft}>
                恢复经历库内容
              </button>
              <button type="button" className="btn primary" onClick={copyPlain}>
                {copied ? '已复制文本' : '复制纯文本'}
              </button>
              <button type="button" className="btn secondary" onClick={downloadText}>
                下载 TXT
              </button>
              <button type="button" className="btn secondary" onClick={printResume}>
                打印 / 另存 PDF
              </button>
            </div>
            {editing && (
              <p className="muted">点击预览里的「删除」去掉整段、整条经历或单条要点。打印前会自动退出编辑态。</p>
            )}
          </div>

          <ResumePreview
            form={form}
            template={template}
            editing={editing}
            onChange={setDraft}
          />
        </>
      )}

      <div className="stack resume-history-block">
        <h3>本地申请模拟记录</h3>
        <p className="muted">
          仍保留本浏览器的模拟结果摘要，不含姓名、联系方式、证件号与简历正文。可用于对照目标岗位再改经历库。
        </p>
        {error && <div className="callout danger">{error}</div>}
        {!records.length ? (
          <p className="muted">还没有模拟记录。完成人工确认或阻断回顾后会出现在这里。</p>
        ) : (
          records.map((record) => (
            <article className="item-block" key={record.id}>
              <div className="item-head">
                <h3>
                  {record.title === 'UNKNOWN' ? '未知岗位' : record.title} ·{' '}
                  {record.company === 'UNKNOWN' ? '未知公司' : record.company}
                </h3>
                <RiskBadge level={record.riskLevel} />
              </div>
              <p>
                <strong>结果：</strong>
                {record.outcome === 'BLOCKED_REVIEWED' ? '已知悉阻断，未投递' : '本地模拟确认，未投递'}
              </p>
              <p className="muted">
                记录时间：{new Date(record.recordedAt).toLocaleString()} · 来源：{record.source}
              </p>
              <button type="button" className="btn secondary" onClick={() => remove(record.id)}>
                删除本地记录
              </button>
            </article>
          ))
        )}
      </div>
    </section>
  )
}
