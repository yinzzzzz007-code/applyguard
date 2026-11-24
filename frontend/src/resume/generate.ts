import type { EditableResumeForm } from '../api/types'

export type ResumeTemplateId = 'cn-academic' | 'en-classic' | 'cn-campus'

export const RESUME_TEMPLATES: Array<{ id: ResumeTemplateId; label: string; hint: string }> = [
  { id: 'cn-academic', label: '中文学术技术', hint: '教育 / 项目 / 科研分段，适合校招与科研岗' },
  { id: 'en-classic', label: '英文标准单栏', hint: 'Education / Experience / Projects / Skills' },
  { id: 'cn-campus', label: '中文校招一页', hint: '求职意向置顶，技能与经历紧凑排版' },
]

export function splitBullets(text: string): string[] {
  return text
    .split(/\r?\n|；|;|•|·/)
    .map((line) => line.trim().replace(/^(?:[-*]\s+|\d+[、)]\s*|\d+\.\s+)/, '').trim())
    .filter(Boolean)
}

export function formatDateRange(start: string, end: string): string {
  const a = start.trim()
  const b = end.trim() || '至今'
  if (!a && !b) return ''
  if (!a) return b
  return `${a} – ${b}`
}

export function contactLine(form: EditableResumeForm): string[] {
  return [
    form.basic.phone,
    form.basic.email,
    form.basic.city,
    form.basic.github,
    form.basic.linkedin,
    form.basic.website,
  ].filter((item) => item.trim())
}

export type ResumeBlock = {kind:'name'|'heading'|'text'|'bullet'; text:string}
export function resumeBlocks(form: EditableResumeForm, template: ResumeTemplateId): ResumeBlock[] {
  const blocks: ResumeBlock[] = []
  const add = (kind:ResumeBlock['kind'], text:string) => { if (text.trim()) blocks.push({kind,text}) }
  const paragraph = (text:string) => add('text',text)
  const heading = (text:string) => add('heading',text)
  const bullet = (text:string) => add('bullet',text)
  const name = form.basic.name || '未命名'
  add('name',name)
  paragraph(contactLine(form).join(' · '))
  if (template === 'cn-campus' && (form.intention.expectRole || form.intention.availability)) {
    paragraph(
      `求职意向：${[form.intention.expectRole, form.intention.expectCity, form.intention.availability]
        .filter(Boolean)
        .join(' · ')}`,
    )
  }
  if (form.extras.researchFocus.trim()) {
    heading(template.startsWith('en') ? 'Research Interests' : '研究兴趣')
    paragraph(form.extras.researchFocus.trim())
  }
  if (form.education.some((row) => row.school.trim())) {
    heading(template.startsWith('en') ? 'EDUCATION' : '教育经历')
    for (const edu of form.education) {
      if (!edu.school.trim()) continue
      paragraph(
        `${edu.school}${edu.location ? ` · ${edu.location}` : ''}  ${formatDateRange(edu.start, edu.end)}`,
      )
      paragraph(
        [edu.degree, edu.major, edu.gpa ? `GPA ${edu.gpa}` : '', edu.rank].filter(Boolean).join(' · '),
      )
      if (edu.coursework.trim()) paragraph(`相关课程：${edu.coursework}`)
    }
  }
  if (form.internships.some((row) => row.organization.trim() || row.description.trim())) {
    heading(template.startsWith('en') ? 'EXPERIENCE' : '实习经历')
    for (const row of form.internships) {
      if (!row.organization.trim() && !row.description.trim()) continue
      paragraph(
        `${row.organization}${row.location ? ` · ${row.location}` : ''}  ${formatDateRange(row.start, row.end)}`,
      )
      paragraph([row.role || row.title, row.techStack].filter(Boolean).join(' · '))
      if (row.link.trim()) paragraph(row.link)
      for (const line of splitBullets(row.description)) bullet(line)
    }
  }
  if (form.projects.some((row) => row.title.trim() || row.description.trim())) {
    heading(template.startsWith('en') ? 'PROJECTS' : '项目经历')
    for (const row of form.projects) {
      if (!row.title.trim() && !row.description.trim()) continue
      paragraph(
        `${row.title || row.organization}${row.techStack ? ` | ${row.techStack}` : ''}  ${formatDateRange(row.start, row.end)}`,
      )
      paragraph([row.role,row.location].filter(Boolean).join(' · '))
      if (row.link.trim()) paragraph(row.link)
      for (const line of splitBullets(row.description)) bullet(line)
    }
  }
  if (form.extras.publications.trim()) {
    heading(template.startsWith('en') ? 'PUBLICATIONS' : '论文 / 科研成果')
    for (const line of splitBullets(form.extras.publications)) bullet(line)
  }
  if ((form.awards ?? []).some((row) => row.name.trim())) {
    heading(template.startsWith('en') ? 'HONORS' : '获奖 / 竞赛')
    for (const award of form.awards ?? []) {
      if (!award.name.trim()) continue
      bullet(
        `${[award.name, award.issuer, award.date].filter(Boolean).join(' · ')}${
          award.description ? `：${award.description}` : ''
        }`,
      )
    }
  }
  if (form.extras.skills.trim() || form.extras.languages.trim()) {
    heading(template.startsWith('en') ? 'SKILLS' : '专业技能')
    if (form.extras.skills.trim()) paragraph(form.extras.skills.trim())
    if (form.extras.languages.trim()) paragraph(`语言：${form.extras.languages.trim()}`)
  }
  if (form.extras.summary.trim()) {
    heading(template.startsWith('en') ? 'SUMMARY' : '自我评价')
    paragraph(form.extras.summary.trim())
  }
  return blocks
}

export function buildPlainResume(form: EditableResumeForm, template: ResumeTemplateId): string {
  return resumeBlocks(form, template).map(({kind,text}) =>
    kind === 'heading' ? '\n'+text : kind === 'bullet' ? '- '+text : text).join('\n').trim()
}
