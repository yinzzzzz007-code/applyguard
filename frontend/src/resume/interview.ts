import type { EditableResumeForm } from '../api/types'

export interface InterviewResume {
  name: string
  skills: string
  summary: string
  education: Array<Pick<EditableResumeForm['education'][number], 'school' | 'degree' | 'major'>>
  projects: Array<Pick<EditableResumeForm['projects'][number], 'title' | 'organization' | 'role' | 'description' | 'techStack' | 'start' | 'end'>>
  internships: InterviewResume['projects']
}

export interface InterviewGuide {
  coverage_version?: number
  one_minute: string
  three_minutes: string
  questions: Array<{ category: string; question: string; answer: string; basis: string; to_confirm: string[]; project_name?: string; project_index?: number | null }>
}

export function interviewResume(form: EditableResumeForm): InterviewResume {
  const experiences = (rows: EditableResumeForm['projects']) =>
    rows.map(({ title, organization, role, description, techStack, start, end }) =>
      ({ title, organization, role, description, techStack, start, end }))
  return {
    name: form.basic.name, skills: form.extras.skills, summary: form.extras.summary,
    education: form.education.map(({ school, degree, major }) => ({ school, degree, major })),
    projects: experiences(form.projects), internships: experiences(form.internships),
  }
}
