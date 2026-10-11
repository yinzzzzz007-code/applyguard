import type { CareerVaultSeed, EditableResumeForm, ExtractedResumeForm } from '../api/types'

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
  const awards = (vault.awards ?? []).map((item) => ({
    id: item.award_id,
    name: item.name,
    issuer: item.issuer,
    date: item.date,
    description: item.description,
  }))

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
    awards,
    extras: {
      skills,
      awards: awards.map((item) => item.name).filter(Boolean).join('；'),
      summary: vault.profile.consent,
    },
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
  const awardBonus = (form.awards ?? []).some((item) => item.name.trim()) ? 1 : 0
  return Math.min(100, Math.round(((filled + expBonus + awardBonus) / (required.length + 2)) * 100))
}

export function newExperienceId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

function filled(value: string | undefined): string {
  return (value ?? '').trim()
}

export function syncAwardText(awards: EditableResumeForm['awards']): string {
  return awards.map((item) => item.name).filter((name) => name.trim()).join('；')
}

export function normalizeResumeForm(form: EditableResumeForm): EditableResumeForm {
  if (Array.isArray(form.awards)) {
    return {
      ...form,
      extras: { ...form.extras, awards: form.extras.awards || syncAwardText(form.awards) },
    }
  }
  const leftover = filled(form.extras?.awards)
  return {
    ...form,
    awards: leftover
      ? [{ id: 'award_imported', name: leftover, issuer: '', date: '', description: '' }]
      : [],
  }
}

export function emptyResumeForm(candidateId: string): EditableResumeForm {
  return {
    candidateId,
    basic: {
      name: '',
      gender: '',
      birthday: '',
      ethnicity: '',
      politics: '',
      phone: '',
      email: '',
      idType: '居民身份证',
      idNo: '',
      city: '',
      hukou: '',
    },
    intention: {
      projectType: '',
      expectRole: '',
      expectCity: '',
      availability: '',
    },
    education: [
      {
        id: 'edu_1',
        school: '',
        degree: '',
        major: '',
        fullTime: '',
        start: '',
        end: '',
        rank: '',
      },
    ],
    internships: [],
    projects: [],
    awards: [],
    extras: { skills: '', awards: '', summary: '' },
    dirty: true,
  }
}

export function overwriteFromExtracted(candidateId: string, extracted: ExtractedResumeForm): EditableResumeForm {
  const next = applyExtractedResume(emptyResumeForm(candidateId), extracted)
  return { ...next, dirty: true, savedAt: undefined }
}

export function applyExtractedResume(base: EditableResumeForm, extracted: ExtractedResumeForm): EditableResumeForm {
  const pick = (current: string, next: string | undefined) => filled(next) || current
  const education = extracted.education
    .filter((row) => filled(row.school) || filled(row.major))
    .map((row, index) => ({
      id: `edu_extract_${index + 1}`,
      school: row.school,
      degree: row.degree,
      major: row.major,
      fullTime: row.fullTime || '是',
      start: row.start,
      end: row.end,
      rank: row.rank,
    }))
  const internships = extracted.internships
    .filter((row) => filled(row.organization) || filled(row.description) || filled(row.title))
    .map((row, index) => ({
      id: newExperienceId(`intern_${index}`),
      organization: row.organization,
      title: row.title,
      role: row.role,
      start: row.start,
      end: row.end,
      description: row.description,
    }))
  const projects = extracted.projects
    .filter((row) => filled(row.title) || filled(row.description) || filled(row.organization))
    .map((row, index) => ({
      id: newExperienceId(`proj_${index}`),
      organization: row.organization,
      title: row.title,
      role: row.role,
      start: row.start,
      end: row.end,
      description: row.description,
    }))
  const awards = (extracted.awards ?? [])
    .filter((row) => filled(row.name) || filled(row.description))
    .map((row, index) => ({
      id: newExperienceId(`award_${index}`),
      name: row.name,
      issuer: row.issuer,
      date: row.date,
      description: row.description,
    }))
  const extrasAwards = awards.length ? syncAwardText(awards) : pick(base.extras.awards, extracted.extras.awards)
  return {
    ...base,
    basic: {
      name: pick(base.basic.name, extracted.basic.name),
      gender: pick(base.basic.gender, extracted.basic.gender),
      birthday: pick(base.basic.birthday, extracted.basic.birthday),
      ethnicity: pick(base.basic.ethnicity, extracted.basic.ethnicity),
      politics: pick(base.basic.politics, extracted.basic.politics),
      phone: pick(base.basic.phone, extracted.basic.phone),
      email: pick(base.basic.email, extracted.basic.email),
      idType: pick(base.basic.idType, extracted.basic.idType),
      idNo: pick(base.basic.idNo, extracted.basic.idNo),
      city: pick(base.basic.city, extracted.basic.city),
      hukou: pick(base.basic.hukou, extracted.basic.hukou),
    },
    intention: {
      projectType: pick(base.intention.projectType, extracted.intention.projectType),
      expectRole: pick(base.intention.expectRole, extracted.intention.expectRole),
      expectCity: pick(base.intention.expectCity, extracted.intention.expectCity),
      availability: pick(base.intention.availability, extracted.intention.availability),
    },
    education: education.length ? education : base.education,
    internships: internships.length ? internships : base.internships,
    projects: projects.length ? projects : base.projects,
    awards: awards.length ? awards : base.awards ?? [],
    extras: {
      skills: pick(base.extras.skills, extracted.extras.skills),
      awards: extrasAwards,
      summary: pick(base.extras.summary, extracted.extras.summary),
    },
    dirty: true,
  }
}
