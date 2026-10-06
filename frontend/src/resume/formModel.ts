import type { CareerVaultSeed, EditableResumeForm, PdfResumePreview } from '../api/types'

export function buildResumeFormFromVault(vault: CareerVaultSeed): EditableResumeForm {
  const internships = vault.experiences
    .filter((e) => e.experience_id === 'exp_ml_evaluation')
    .map((e) => ({
      id: e.experience_id,
      organization: e.organization,
      title: e.title ?? e.role,
      role: e.role,
      start: e.start_date,
      end: e.end_date,
      description: [e.summary, ...(e.responsibilities ?? [])].filter(Boolean).join('\n'),
      sourceExperienceId: e.experience_id,
    }))

  const projects = vault.experiences
    .filter((e) => e.experience_id !== 'exp_ml_evaluation')
    .map((e) => ({
      id: e.experience_id,
      organization: e.organization,
      title: e.title ?? e.role,
      role: e.role,
      start: e.start_date,
      end: e.end_date,
      description: [e.summary, ...(e.responsibilities ?? [])].filter(Boolean).join('\n'),
      sourceExperienceId: e.experience_id,
    }))

  const skills = Array.from(new Set(vault.experiences.flatMap((e) => e.skills))).join('、')

  return {
    candidateId: vault.candidate_id,
    basic: {
      name: vault.profile.display_name || '林晓舟（演示）',
      gender: '男',
      birthday: '2004-05-18',
      ethnicity: '汉族',
      politics: '共青团员',
      phone: '13800000001',
      email: 'demo.candidate@example.com',
      idType: '居民身份证',
      idNo: '',
      city: '广东省 · 深圳市',
      hukou: '广东省 · 广州市',
    },
    intention: {
      projectType: '应届生',
      expectRole: '后端开发 / 软件开发',
      expectCity: '深圳、北京、上海',
      availability: '毕业后尽快到岗',
    },
    education: [
      {
        id: 'edu_1',
        school: '示例理工大学（虚构）',
        degree: '本科',
        major: '软件工程',
        fullTime: '是',
        start: '2022-09',
        end: '2026-06',
        rank: vault.profile.education,
      },
    ],
    internships,
    projects,
    awards: vault.awards ?? [],
    extras: {
      skills,
      awards: '',
      summary: vault.profile.consent,
    },
    dirty: false,
  }
}

export function buildResumeFormFromPdf(preview: PdfResumePreview, candidateId: string): EditableResumeForm {
  return {
    candidateId,
    basic: { name: preview.basic.name ?? '', gender: '', birthday: '', ethnicity: '', politics: '',
      phone: preview.basic.phone ?? '', email: preview.basic.email ?? '', idType: '', idNo: '',
      city: preview.basic.city ?? '', hukou: '' },
    intention: { projectType: '', expectRole: '', expectCity: '', availability: '' },
    education: preview.education,
    internships: preview.internships,
    projects: preview.projects,
    awards: preview.awards,
    extras: { skills: '', awards: '', summary: '' },
    dirty: true,
  }
}

export function resumeCompleteness(form: EditableResumeForm): number {
  const required: string[] = [
    form.basic.name,
    form.basic.gender,
    form.basic.birthday,
    form.basic.phone,
    form.basic.email,
    form.basic.idType,
    form.basic.city,
    form.intention.projectType,
    form.intention.expectRole,
    form.intention.expectCity,
    form.extras.skills,
  ]
  if (form.education[0]) {
    required.push(
      form.education[0].school,
      form.education[0].degree,
      form.education[0].major,
      form.education[0].start,
      form.education[0].end,
    )
  }
  const filled = required.filter((v) => v.trim().length > 0).length
  const expBonus =
    form.internships.some((i) => i.organization && i.description) ||
    form.projects.some((p) => p.title && p.description)
      ? 1
      : 0
  return Math.min(100, Math.round(((filled + expBonus) / (required.length + 1)) * 100))
}

export function newExperienceId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}
