import type { EditableResumeForm } from '../api/types'
import { Link } from 'react-router-dom'
import { Card } from './ui/card'
import { Button } from './ui/button'
import { ImportSuggestions } from './ImportSuggestions'
import { resumeSections } from '../resume/formModel'
import type { ImportRow, RowSection } from '../resume/importReview'

const labels = { education: '教育经历', internships: '实习经历', projects: '项目经历', awards: '获奖 / 竞赛' }
export const editorSection = { education: 'education', internships: 'internship', projects: 'project', awards: 'awards' } as const
export function rowTitle(row: ImportRow) {
  if ('school' in row) return row.school || '未填写学校'
  if ('name' in row) return row.name || '未填写奖项'
  return row.title || row.role || row.organization || '未命名经历'
}
export function CareerVaultOverview({ form, saving, onEdit, onAdd, onDelete, onSuggestion }: {
  form: EditableResumeForm; saving: boolean
  onEdit: (section: 'basic' | 'intention' | 'skills' | 'education' | 'internship' | 'project' | 'awards', id?: string) => void
  onSuggestion: (id: string, action: 'keep' | 'use' | 'new', targetId?: string) => void
  onAdd: (section: RowSection) => void
  onDelete: (section: RowSection, id: string) => void
}) {
  return <div className="vault-overview">
    <div className="vault-profile-grid">
      {([
        ['basic', '个人资料', [form.basic.name, form.basic.email, form.basic.phone].filter(Boolean).join(' · ')],
        ['intention', '求职意向', [form.intention.expectRole, form.intention.expectCity].filter(Boolean).join(' · ')],
        ['skills', '技能 / 其他', form.extras.skills],
      ] as const).map(([section, label, detail]) => <Card key={section} className="vault-profile-card">
        <h3>{label}</h3><p>{detail || '尚未填写，可随时补充'}</p>
        <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={saving} onClick={() => onEdit(section)}>编辑{label}</Button>
        <ImportSuggestions items={(form.importContext?.suggestions ?? []).filter(item => item.group === (section === 'skills' ? 'extras' : section))} disabled={saving} onResolve={onSuggestion} />
      </Card>)}
    </div>
    {resumeSections.map(section => <section className="vault-category" key={section} aria-labelledby={`vault-${section}`}>
      <header className="vault-category-head"><h3 id={`vault-${section}`}>{labels[section]} <span>{form[section].length}</span></h3>
        <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={saving} onClick={() => onAdd(section)}>新增{labels[section]}</Button></header>
      {form[section].length ? <div className="vault-card-grid">{form[section].map(row => {
        const detail = 'school' in row ? [row.degree, row.major].filter(Boolean).join(' · ') : 'issuer' in row ? row.issuer : [row.organization, row.role].filter(Boolean).join(' · ')
        const dates = 'date' in row ? row.date : [row.start, row.end].filter(Boolean).join(' — ')
        return <Card asChild key={row.id}><article className="vault-experience-card">
          <h4>{rowTitle(row)}</h4>{detail && <p className="vault-card-detail">{detail}</p>}{dates && <p className="muted">{dates}</p>}
          {'description' in row && row.description && <p className="vault-card-description">{row.description}</p>}
          <ImportSuggestions items={(form.importContext?.suggestions ?? []).filter(item => item.section === section && item.candidateIds?.includes(row.id))} targetId={row.id} disabled={saving} onResolve={onSuggestion} />
          <div className="btn-row"><Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={saving} onClick={() => onEdit(editorSection[section], row.id)}>编辑</Button>
            <Button variant="ghost" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={saving} onClick={() => onDelete(section, row.id)}>删除</Button></div>
        </article></Card>
      })}</div> : <div className="vault-category-empty">暂无{labels[section]}。可以<Link to="/">导入简历</Link>，或点击“新增”。</div>}
    </section>)}
  </div>
}
