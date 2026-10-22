import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ClaimBadge, RiskBadge } from '../components/States'
import { useDemo } from '../context/DemoContext'
import type { EditableResumeForm, LocalClaimDecision, LocalFieldDecision, WorkflowResponse } from '../api/types'
import { normalizeResumeForm } from '../resume/formModel'
import { copyableClaim, copyableField } from '../copyRules'
import { saveApplicationHistory, type HistoryOutcome } from '../history'
import { ZH_ACTION, ZH_DECISION, ZH_FRESHNESS, ZH_MAPPER, ZH_PARSER, ZH_STATUS, ZH_STEP, zhLookup, zhText } from '../i18n'

function storedResumeForm(): EditableResumeForm | null {
  try {
    const raw = sessionStorage.getItem('applyguard.resumeForm')
    return raw ? normalizeResumeForm(JSON.parse(raw) as EditableResumeForm) : null
  } catch {
    return null
  }
}

function copyToClipboard(text: string): Promise<void> {
  return navigator.clipboard.writeText(text)
}

function CopyRow({ label, value, allowed = true }: { label: string; value: string; allowed?: boolean }) {
  const [copied, setCopied] = useState(false)
  const { canProceedFromClaims, canSubmitAts, validateExport } = useDemo()
  const [error, setError] = useState('')
  const empty = !value.trim()
  return (
    <div className="copy-row">
      <span className="copy-label">{label}</span>
      <span className={empty ? 'muted copy-value' : 'copy-value'}>{empty ? '未填写' : value}</span>
      <button
        type="button"
        className="btn secondary copy-btn"
        disabled={empty || !allowed || !canProceedFromClaims() || !canSubmitAts()}
        onClick={() => {
          void validateExport().then(async (valid) => {
            if (!valid) { setError('证据状态已改变或无法连接后端，请返回重新核验和确认。'); return }
            await copyToClipboard(value)
            setCopied(true)
            setError('')
            window.setTimeout(() => setCopied(false), 1200)
          }).catch(() => setError('复制失败，请检查浏览器剪贴板权限。'))
        }}
      >
        {copied ? '已复制' : '复制'}
      </button>
      {error && <span className="danger-text" role="alert">{error}</span>}
    </div>
  )
}

function buildCopyPack(
  form: EditableResumeForm | null,
  workflow: WorkflowResponse,
  claimDecisions: Record<string, LocalClaimDecision>,
  fieldDecisions: Record<string, LocalFieldDecision>,
  copyReady: boolean,
): string {
  if (!copyReady) return '当前申请尚未通过全部核验与确认，不生成可复制填写稿。'
  const lines: string[] = ['申请护栏 · 可复制填写稿', '']
  if (form) {
    const b = form.basic
    const i = form.intention
    lines.push('【个人信息】')
    lines.push(`姓名：${b.name}`)
    lines.push(`性别：${b.gender}`)
    lines.push(`出生日期：${b.birthday}`)
    lines.push(`民族：${b.ethnicity}`)
    lines.push(`政治面貌：${b.politics}`)
    lines.push(`手机号码：${b.phone}`)
    lines.push(`电子邮箱：${b.email}`)
    lines.push(`证件类型：${b.idType}`)
    if (b.idNo.trim()) lines.push(`证件号码：${b.idNo}`)
    lines.push(`现居住地：${b.city}`)
    lines.push(`户口所在地：${b.hukou}`)
    lines.push('')
    lines.push('【求职意向】')
    lines.push(`招聘项目：${i.projectType}`)
    lines.push(`期望职位：${i.expectRole}`)
    lines.push(`期望城市：${i.expectCity}`)
    lines.push(`到岗时间：${i.availability}`)
    lines.push('')
    if (form.education.length) {
      lines.push('【教育经历】')
      form.education.forEach((edu, index) => {
        lines.push(`${index + 1}. ${edu.school} · ${edu.degree} · ${edu.major}`)
        lines.push(`时间：${edu.start} ～ ${edu.end} · 全日制：${edu.fullTime}`)
      })
      lines.push('')
    }
    if (form.awards?.length) {
      lines.push('【获奖 / 竞赛】')
      form.awards.forEach((award, index) => {
        lines.push(`${index + 1}. ${award.name}${award.issuer ? ` · ${award.issuer}` : ''}${award.date ? ` · ${award.date}` : ''}`)
        if (award.description) lines.push(`说明：${award.description}`)
      })
      lines.push('')
    }
    lines.push('【经历与技能】请仅使用下方核验通过的陈述；本地编辑的经历描述和技能未重新核验。', '')
  } else {
    lines.push('【个人信息】未从经历库读到表单，请先回到经历库保存。', '')
  }

  const jd = workflow.parsed_jd
  lines.push('【应聘岗位】')
  lines.push(`岗位：${jd.title === 'UNKNOWN' ? '未知岗位' : jd.title}`)
  lines.push(`公司：${jd.company === 'UNKNOWN' ? '未知公司' : jd.company}`)
  lines.push('')

  lines.push('【拟填网申字段】')
  for (const field of workflow.ats_form_mapping.fields) {
    if (!copyableField(workflow, claimDecisions, fieldDecisions, field)) continue
    const action = zhLookup(ZH_ACTION, field.action)
    lines.push(`${zhText(field.label)}：${field.value || '无'} · ${action}`)
  }
  if (workflow.ats_form_mapping.unmapped_fields.length) {
    lines.push(
      `未映射、须本人填写：${workflow.ats_form_mapping.unmapped_fields.map((id) => zhText(id)).join('、')}`,
    )
  }
  lines.push('')

  lines.push('【可粘贴陈述】')
  for (const claim of workflow.resume_claims) {
    if (copyableClaim(workflow, claimDecisions, claim.claim_id)) lines.push(`- ${claim.text}`)
  }

  return lines.filter((line, i, all) => !(line === '' && all[i - 1] === '')).join('\n').trim()
}

export function HumanConfirmationPage() {
  const navigate = useNavigate()
  const {
    workflow,
    resumeForm,
    claimDecisions,
    fieldDecisions,
    canProceedFromClaims,
    canSubmitAts,
    validateExport,
    confirmationNote,
    setConfirmationNote,
    simulatedConfirmed,
    setSimulatedConfirmed,
    resetFlow,
    dataSourceLabel,
  } = useDemo()
  const [packCopied, setPackCopied] = useState(false)
  const [historyError, setHistoryError] = useState('')

  const form = resumeForm ? normalizeResumeForm(resumeForm) : storedResumeForm()
  const copyReady = canProceedFromClaims() && canSubmitAts()
  const copyPack = useMemo(
    () => (workflow ? buildCopyPack(form, workflow, claimDecisions, fieldDecisions, copyReady) : ''),
    [form, workflow, claimDecisions, fieldDecisions, copyReady],
  )

  if (!workflow) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>人工确认</h2>
          <p>尚未完成网申模拟。</p>
        </header>
        <button type="button" className="btn primary" onClick={() => navigate('/vault')}>
          回到经历库
        </button>
      </section>
    )
  }

  const allowed = workflow.human_confirmation.allowed_actions
  const blocked = workflow.risk_result.action === 'BLOCKED' || workflow.workflow_status === 'BLOCKED'
  const canConfirm = allowed.includes('CONFIRM') && !blocked && copyReady
  const finishSimulation = (outcome: HistoryOutcome) => {
    if (simulatedConfirmed) return
    if (!saveApplicationHistory(workflow, outcome)) {
      setHistoryError('本地历史保存失败，请检查浏览器存储权限。')
      return
    }
    setHistoryError('')
    setSimulatedConfirmed(true)
  }
  const parsedTitle = workflow.parsed_jd.title === 'UNKNOWN' ? '未知岗位' : workflow.parsed_jd.title
  const parsedCompany = workflow.parsed_jd.company === 'UNKNOWN' ? '未知公司' : workflow.parsed_jd.company

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>人工确认</h2>
        <p>
          把经历库里的个人信息和拟填内容汇总在这里，方便复制到招聘网站网申。本页只做本地模拟，不会真实投递。
        </p>
      </header>

      <div className="profile-card">
        <p>
          数据来源：{dataSourceLabel} · 应聘 {parsedTitle} @ {parsedCompany} · 汇总风险{' '}
          <RiskBadge level={workflow.risk_result.risk_level} />
        </p>
        <p>{zhText(workflow.human_confirmation.reason)}</p>
        <p className="muted">允许操作：{allowed.map((a) => zhLookup(ZH_ACTION, a)).join('、')}</p>
      </div>

      <div className="item-block copy-sheet">
        <div className="item-head">
          <h3>填写稿（可复制）</h3>
          <button
            type="button"
            className="btn primary"
            disabled={!copyReady}
            onClick={() => {
              void validateExport().then(async (valid) => {
                if (!valid) { setHistoryError('证据状态已改变或无法连接后端，请重新核验。'); return }
                await copyToClipboard(copyPack)
                setPackCopied(true)
                window.setTimeout(() => setPackCopied(false), 1500)
              }).catch(() => setHistoryError('复制失败，请检查浏览器剪贴板权限。'))
            }}
          >
            {packCopied ? '已复制全部' : '一键复制全部'}
          </button>
        </div>
        <p className="muted">单项也可复制。证件号若未填则不会进入全文稿；本地编辑的经历和技能不进入可复制稿。</p>
        <textarea className="jd-input copy-pack" rows={12} readOnly value={copyPack} />
      </div>

      {form ? (
        <>
          <div className="item-block">
            <h3>个人信息</h3>
            <CopyRow label="姓名" value={form.basic.name} />
            <CopyRow label="性别" value={form.basic.gender} />
            <CopyRow label="出生日期" value={form.basic.birthday} />
            <CopyRow label="民族" value={form.basic.ethnicity} />
            <CopyRow label="政治面貌" value={form.basic.politics} />
            <CopyRow label="手机号码" value={form.basic.phone} />
            <CopyRow label="电子邮箱" value={form.basic.email} />
            <CopyRow label="证件类型" value={form.basic.idType} />
            <CopyRow label="证件号码" value={form.basic.idNo} />
            <CopyRow label="现居住地" value={form.basic.city} />
            <CopyRow label="户口所在地" value={form.basic.hukou} />
          </div>
          <div className="item-block">
            <h3>求职意向</h3>
            <CopyRow label="招聘项目" value={form.intention.projectType} />
            <CopyRow label="期望职位" value={form.intention.expectRole} />
            <CopyRow label="期望城市" value={form.intention.expectCity} />
            <CopyRow label="到岗时间" value={form.intention.availability} />
          </div>
          {form.education.map((edu) => (
            <div key={edu.id} className="item-block">
              <h3>教育经历</h3>
              <CopyRow label="学校" value={edu.school} />
              <CopyRow label="学历" value={edu.degree} />
              <CopyRow label="专业" value={edu.major} />
              <CopyRow label="是否全日制" value={edu.fullTime} />
              <CopyRow label="在读时间" value={`${edu.start} ～ ${edu.end}`} />
              <CopyRow label="说明" value={edu.rank} allowed={false} />
            </div>
          ))}
          {form.internships.map((entry, index) => (
            <div key={entry.id} className="item-block">
              <h3>实习 {index + 1}</h3>
              <p className="muted">本地编辑的经历尚未重新核验，暂不可复制。</p>
              <CopyRow label="组织" value={entry.organization} allowed={false} />
              <CopyRow label="职位" value={entry.title} allowed={false} />
              <CopyRow label="角色" value={entry.role} allowed={false} />
              <CopyRow label="时间" value={`${entry.start} ～ ${entry.end}`} allowed={false} />
              <CopyRow label="描述" value={entry.description} allowed={false} />
            </div>
          ))}
          {form.projects.map((entry, index) => (
            <div key={entry.id} className="item-block">
              <h3>项目 {index + 1}</h3>
              <p className="muted">本地编辑的经历尚未重新核验，暂不可复制。</p>
              <CopyRow label="组织" value={entry.organization} allowed={false} />
              <CopyRow label="名称" value={entry.title} allowed={false} />
              <CopyRow label="角色" value={entry.role} allowed={false} />
              <CopyRow label="时间" value={`${entry.start} ～ ${entry.end}`} allowed={false} />
              <CopyRow label="描述" value={entry.description} allowed={false} />
            </div>
          ))}
          {(form.awards ?? []).map((award, index) => (
            <div key={award.id} className="item-block">
              <h3>获奖 / 竞赛 {index + 1}</h3>
              <CopyRow label="奖项名称" value={award.name} />
              <CopyRow label="颁发单位" value={award.issuer} />
              <CopyRow label="获奖时间" value={award.date} />
              <CopyRow label="说明" value={award.description} />
            </div>
          ))}
          <div className="item-block">
            <h3>技能与补充</h3>
            <p className="muted">这些本地文字尚未重新核验，暂不可复制。</p>
            <CopyRow label="技能" value={form.extras.skills} allowed={false} />
            <CopyRow label="自我说明" value={form.extras.summary} allowed={false} />
          </div>
        </>
      ) : (
        <div className="callout warn">
          未读到经历库表单。请先到经历库填写并保存，再回到本页复制。
          <div className="btn-row">
            <button type="button" className="btn secondary" onClick={() => navigate('/vault')}>
              去经历库
            </button>
          </div>
        </div>
      )}

      <div className="item-block">
        <h3>拟填网申字段</h3>
        {workflow.ats_form_mapping.fields.map((field) => (
          <CopyRow
            key={field.field_id}
            label={`${zhText(field.label)}（${zhLookup(ZH_ACTION, field.action)}）`}
            value={copyableField(workflow, claimDecisions, fieldDecisions, field) ? field.value : ''}
          />
        ))}
        {workflow.ats_form_mapping.unmapped_fields.map((id) => (
          <CopyRow key={id} label={`${zhText(id)}（须本人填写）`} value="" />
        ))}
      </div>

      <div className="item-block">
        <h3>可粘贴陈述</h3>
        {workflow.resume_claims.map((claim) => {
          const decision = claimDecisions[claim.claim_id]
          if (decision?.decision === 'reject' || decision?.freshness === 'rejected') return null
          const eligible = copyableClaim(workflow, claimDecisions, claim.claim_id)
          const text = eligible ? claim.text : ''
          return (
            <div key={claim.claim_id} className="copy-claim">
              <p>
                <ClaimBadge status={workflow.claim_verification.find((v) => v.claim_id === claim.claim_id)?.state ?? 'NEEDS_REVIEW'} />{' '}
                {zhLookup(ZH_DECISION, decision?.decision ?? '', '未处理')} ·{' '}
                {zhLookup(ZH_FRESHNESS, decision?.freshness ?? 'as_returned')}
              </p>
              <CopyRow label="陈述" value={text} />
            </div>
          )
        })}
      </div>

      <div className="item-block">
        <h3>步骤轨迹</h3>
        <ol>
          {workflow.step_trace.map((s, i) => (
            <li key={`${s.step}-${i}`}>
              {zhLookup(ZH_STEP, s.step)}：{zhLookup(ZH_STATUS, s.status)}
              {s.mode ? `（${zhLookup({ ...ZH_PARSER, ...ZH_MAPPER }, s.mode, s.mode)}）` : ''}
              {s.fallback_reason ? ` · 回退原因：${zhText(s.fallback_reason)}` : ''}
            </li>
          ))}
        </ol>
      </div>

      <div className="item-block">
        <h3>审计记录（仅本次响应，刷新即消失）</h3>
        <ul className="ats-summary">
          <li>记录编号：{workflow.audit_record.audit_id.replace(/^audit_/, '')}</li>
          <li>申请编号：{workflow.audit_record.application_id}</li>
          <li>版本：{workflow.audit_record.version}</li>
          <li>时间：{workflow.audit_record.created_at}</li>
          <li>事件：{zhText(workflow.audit_record.event)}</li>
          <li>执行者：模拟工作流</li>
          <li>追踪编号：{workflow.audit_record.trace_id?.replace(/^trace_/, '') ?? workflow.trace_id}</li>
          <li>
            决策：
            {zhLookup({ PENDING: '待处理', BLOCKED: '已阻断', CONFIRMED: '已确认' }, workflow.audit_record.decision)}
          </li>
        </ul>
      </div>

      <label className="field-label" htmlFor="note">
        模拟确认备注
      </label>
      <textarea
        id="note"
        className="jd-input"
        rows={3}
        value={confirmationNote}
        onChange={(e) => setConfirmationNote(e.target.value)}
      />

      {blocked && (
        <div className="callout danger">
          本次 <strong>不可投递</strong>。允许操作为编辑 / 取消，没有确认提交。下面只能回退改材料，或结束这场模拟。
        </div>
      )}
      {simulatedConfirmed && (
        <div className="callout ok">
          已写入<strong>本浏览器的模拟历史</strong>。未向招聘网站投递，也未写入后端申请历史。
        </div>
      )}
      {historyError && <div className="callout danger">{historyError}</div>}

      <div className="btn-row end">
        <button type="button" className="btn secondary" onClick={() => navigate('/ats')}>
          回退网申模拟
        </button>
        {allowed.includes('EDIT') && (
          <button type="button" className="btn secondary" onClick={() => navigate('/jd')}>
            编辑（回岗位说明）
          </button>
        )}
        {allowed.includes('CANCEL') && (
          <button type="button" className="btn secondary" onClick={() => resetFlow()}>
            取消并重置
          </button>
        )}
        {blocked ? (
          <button
            type="button"
            className="btn primary"
            disabled={simulatedConfirmed}
            onClick={() => {
              finishSimulation('BLOCKED_REVIEWED')
            }}
          >
            结束演示（已知悉不可投递）
          </button>
        ) : (
          <button
            type="button"
            className="btn primary"
            disabled={!canConfirm || simulatedConfirmed}
            onClick={() => {
              void validateExport().then((valid) => { if (valid) finishSimulation('SIMULATED_CONFIRMED'); else setHistoryError('证据状态已改变或无法连接后端，请重新核验。') })
            }}
          >
            模拟确认（非投递）
          </button>
        )}
      </div>
    </section>
  )
}
