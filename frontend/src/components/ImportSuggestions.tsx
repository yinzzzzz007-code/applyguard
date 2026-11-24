import type { ResumeImportSuggestion } from '../api/types'
import { Button } from './ui/button'

const fields: Record<string, string> = {
  school: '学校', degree: '学历', major: '专业', fullTime: '全日制', rank: '成绩 / 排名',
  title: '名称', organization: '组织', role: '角色', start: '开始时间', end: '结束时间',
  description: '描述', name: '名称', issuer: '颁发单位', date: '获奖时间', location: '地点', techStack: '技术栈',
  phone: '手机', email: '邮箱', skills: '技能', city: '城市', expectRole: '期望职位', expectCity: '期望城市',
  summary: '自我介绍', gender: '性别', birthday: '出生日期', projectType: '招聘项目', availability: '到岗时间',
  gpa: 'GPA', coursework: '相关课程', link: '链接', github: 'GitHub', linkedin: 'LinkedIn', website: '个人主页',
  languages: '语言能力', publications: '论文 / 科研成果', researchFocus: '研究兴趣',
}
export function ImportSuggestions({ items, targetId, disabled, onResolve }: {
  items: ResumeImportSuggestion[]; targetId?: string; disabled: boolean
  onResolve: (id: string, action: 'keep' | 'use' | 'new', targetId?: string) => void
}) {
  if (!items.length) return null
  return <div className="vault-suggestions">{items.map(item => <details className="vault-suggestion" key={item.id}>
    <summary>有新的识别建议 · 当前保留已有内容</summary>
    {item.row ? <dl>{Object.entries(item.row).filter(([field, value]) => fields[field] && value).map(([field, value]) =>
      <div key={field}><dt>{fields[field]}</dt><dd>{value}</dd></div>)}</dl> : <div>
      <p>{fields[item.field ?? ''] ?? item.field}</p><p>已有：{item.before}</p><p>识别：{item.after}</p>
    </div>}
    <div className="btn-row">
      <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={disabled} onClick={() => onResolve(item.id, 'use', targetId)}>使用本次识别内容</Button>
      <Button variant="ghost" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={disabled} onClick={() => onResolve(item.id, 'keep')}>保留已有内容</Button>
      {item.row && <Button variant="ghost" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={disabled} onClick={() => onResolve(item.id, 'new')}>作为新经历</Button>}
    </div>
  </details>)}</div>
}
