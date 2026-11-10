import type { ProfileCheck } from '../api/jobs'

const status = { MATCH: '按填写信息符合', MISMATCH: '按填写信息不符', UNKNOWN: '待核对', DECLARED: '本人填写，待补证' }

export function ProfileCheckList({ checks }: { checks?: ProfileCheck[] }) {
  if (!checks?.length) return null
  return <ul className="profile-checks" aria-label="个人填写信息对照">
    {checks.map(check => <li key={check.label}><strong>{check.label}</strong>
      {' · '}{check.value || '未填写'}{' · '}{status[check.state]}</li>)}
  </ul>
}
