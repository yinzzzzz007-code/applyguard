import { useMemo, useState } from 'react'
import { GroundedExport } from '../components/GroundedExport'
import { useNavigate, useSearchParams } from 'react-router-dom'
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

function CopyRow({
  label,
  value: rawValue,
  allowed = true,
  blocked = false,
  previewCopy = false,
}: {
  label: string
  value?: string
  allowed?: boolean
  blocked?: boolean
  /** 预览复制：不要求整单可提交，也不走导出核验。 */
  previewCopy?: boolean
}) {
  const value = typeof rawValue === 'string' ? rawValue : ''
  const [copied, setCopied] = useState(false)
  const { canProceedFromClaims, canSubmitAts, validateExport } = useDemo()
  const [error, setError] = useState('')
  const empty = !value.trim()
  const safeCopyOk = allowed && canProceedFromClaims() && canSubmitAts()
  const canCopy = !empty && (previewCopy || safeCopyOk)

  return (
    <div className={`copy-row${blocked ? ' blocked-row' : ''}`}>
      <span className="copy-label">{label}</span>
      <span className={`${empty ? 'muted copy-value' : 'copy-value'}${blocked && !empty ? ' copy-value-blocked' : ''}`}>
        {empty ? '未填写' : value}
        {blocked && !empty ? <span className="muted"> · 已阻断（可复制参考，不可当作已通过）</span> : null}
      </span>
      <button
        type="button"
        className="btn secondary copy-btn"
        disabled={!canCopy}
        onClick={() => {
          if (previewCopy || blocked) {
            void copyToClipboard(value)
              .then(() => {
                setCopied(true)
                setError('')
                window.setTimeout(() => setCopied(false), 1200)
              })
              .catch(() => setError('复制失败，请检查浏览器剪贴板权限。'))
            return
          }
          void validateExport()
            .then(async (valid) => {
              if (!valid) {
                setError('证据状态已改变或无法连接后端，请返回重新核验和确认。')
                return
              }
              await copyToClipboard(value)
              setCopied(true)
              setError('')
              window.setTimeout(() => setCopied(false), 1200)
            })
            .catch(() => setError('复制失败，请检查浏览器剪贴板权限。'))
        }}
      >
        {copied ? '已复制' : '复制'}
      </button>
      {error && (
        <span className="danger-text" role="alert">
          {error}
        </span>
      )}
    </div>
  )
}

function buildCopyPack(
  form: EditableResumeForm | null,
  workflow: WorkflowResponse,
  claimDecisions: Record<string, LocalClaimDecision>,
  _fieldDecisions: Record<string, LocalFieldDecision>,
  copyReady: boolean,
): string {
  const lines: string[] = [
    copyReady ? '申请护栏 · 可复制填写稿' : '申请护栏 · 预览填写稿（含已阻断内容，仅供参考）',
    '',
  ]
  if (!copyReady) {
    lines.push('说明：红色 /【已阻断】标记的内容尚未通过核验，复制不等于可提交。', '')
  }
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
        lines.push(
          `${index + 1}. ${award.name}${award.issuer ? ` · ${award.issuer}` : ''}${award.date ? ` · ${award.date}` : ''}`,
        )
        if (award.description) lines.push(`说明：${award.description}`)
      })
      lines.push('')
    }
    lines.push('【经历与技能】请优先使用下方核验通过的陈述；本地编辑的经历描述和技能未重新核验。', '')
  } else {
    lines.push('【个人信息】未从经历库读到表单，请先回到经历库保存。', '')
  }

  const jd = workflow.parsed_jd
  lines.push('【应聘岗位】')
  lines.push(`岗位：${jd.title === 'UNKNOWN' ? '未知岗位' : jd.title}`)
  lines.push(`公司：${jd.company === 'UNKNOWN' ? '未知公司' : jd.company}`)
  if (workflow.target_job) {
    lines.push(`收藏岗位版本：${workflow.target_job.id} · v${workflow.target_job.version}`)
    if (workflow.target_job.url) lines.push(`岗位来源：${workflow.target_job.url}`)
  }
  lines.push('')

  lines.push('【拟填网申字段】')
  for (const field of workflow.ats_form_mapping.fields) {
    const control = workflow.field_controls.find((item) => item.field_id === field.field_id)
    const action = control?.action ?? field.action
    const blockedSources = field.source_claim_ids.filter(
      (id) => workflow.claim_verification.find((item) => item.claim_id === id)?.state === 'BLOCKED',
    )
    const mark = blockedSources.length ? `【含已阻断陈述 ${blockedSources.length} 条】` : ''
    lines.push(`${mark}${zhText(field.label)}：${field.value || '无'} · ${zhLookup(ZH_ACTION, action)}`)
  }
  if (workflow.ats_form_mapping.unmapped_fields.length) {
    lines.push(
      `未映射、须本人填写：${workflow.ats_form_mapping.unmapped_fields.map((id) => zhText(id)).join('、')}`,
    )
  }
  lines.push('')

  lines.push('【可粘贴陈述】')
  for (const claim of workflow.resume_claims) {
    const decision = claimDecisions[claim.claim_id]
    if (decision?.decision === 'reject' || decision?.freshness === 'rejected') continue
    const state = workflow.claim_verification.find((item) => item.claim_id === claim.claim_id)?.state
    const mark = state === 'BLOCKED' ? '【已阻断】 ' : ''
    lines.push(`- ${mark}${claim.text}`)
  }

  return lines.filter((line, i, all) => !(line === '' && all[i - 1] === '')).join('\n').trim()
}

export function HumanConfirmationPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const viewOnly = searchParams.get('view') === '1' || searchParams.get('view') === 'readonly'
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
          <p>尚未完成申请内容检查。</p>
        </header>
        <button type="button" className="btn primary" onClick={() => navigate('/vault')}>
          回到经历库
        </button>
      </section>
    )
  }

  const allowed = workflow.human_confirmation.allowed_actions
  const blocked = workflow.risk_result.action === 'BLOCKED' || workflow.workflow_status === 'BLOCKED'
  const readOnlyView = viewOnly || blocked
  const previewCopy = blocked || viewOnly || !copyReady
  const canConfirm = !readOnlyView && allowed.includes('CONFIRM') && !blocked && copyReady
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
  const hasBlockedClaim = workflow.claim_verification.some((item) => item.state === 'BLOCKED')

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>人工确认</h2>
        <p>
          把经历库里的个人信息和拟填内容汇总在这里，方便复制到招聘网站网申。本页只做本地模拟，不会真实投递。
        </p>
      </header>

      {readOnlyView && (
        <div className="callout warn">
          {blocked ? (
            <>
              <p>
                <strong>只是预览，申请仍被阻断。</strong>
                打开本页、勾选或复制，都不会把状态改成「可提交」。
              </p>
              <p className="muted">
                只有核验状态为「已阻断」的陈述会标红底。待复核或其他内容可正常查看、复制，不等于已通过。
              </p>
            </>
          ) : (
            <p>当前为只读查看。实际确认仍须满足原有核验与字段确认规则；仅「已阻断」项标红，可复制参考。</p>
          )}
        </div>
      )}

      <div className="profile-card">
        <p>
          数据来源：{dataSourceLabel} · 应聘 {parsedTitle} @ {parsedCompany} · 汇总风险{' '}
          <RiskBadge level={workflow.risk_result.risk_level} />
        </p>
        <p>{zhText(workflow.human_confirmation.reason)}</p>
        <p className="muted">允许操作：{allowed.map((a) => zhLookup(ZH_ACTION, a)).join('、')}</p>
        {workflow.target_job && (
          <p className="muted">关联收藏岗位版本：v{workflow.target_job.version} · 修改后需重新核验。</p>
        )}
      </div>

      <div className="item-block copy-sheet">
        <div className="item-head">
          <h3>填写稿（可复制）</h3>
          <button
            type="button"
            className="btn primary"
            disabled={!copyPack.trim()}
            onClick={() => {
              if (previewCopy) {
                void copyToClipboard(copyPack)
                  .then(() => {
                    setPackCopied(true)
                    setHistoryError('')
                    window.setTimeout(() => setPackCopied(false), 1500)
                  })
                  .catch(() => setHistoryError('复制失败，请检查浏览器剪贴板权限。'))
                return
              }
              void validateExport()
                .then(async (valid) => {
                  if (!valid) {
                    setHistoryError('证据状态已改变或无法连接后端，请重新核验。')
                    return
                  }
                  await copyToClipboard(copyPack)
                  setPackCopied(true)
                  window.setTimeout(() => setPackCopied(false), 1500)
                })
                .catch(() => setHistoryError('复制失败，请检查浏览器剪贴板权限。'))
            }}
          >
            {packCopied ? '已复制全部' : previewCopy ? '复制预览稿' : '一键复制全部'}
          </button>
        </div>
        <p className="muted">
          单项也可复制。证件号若未填则不会进入全文稿。
          {hasBlockedClaim
            ? ' 文中【已阻断】只标真正被阻断的句子；复制不等于可提交。'
            : ' 本地编辑的经历和技能未重新核验。'}
        </p>
        <textarea
          className="jd-input copy-pack"
          rows={12}
          aria-label="可复制的模拟填写稿"
          readOnly
          value={copyPack}
        />
      </div>

      {form ? (
        <>
          <div className="item-block">
            <h3>个人信息</h3>
            <CopyRow label="姓名" value={form.basic.name} previewCopy={previewCopy} />
            <CopyRow label="性别" value={form.basic.gender} previewCopy={previewCopy} />
            <CopyRow label="出生日期" value={form.basic.birthday} previewCopy={previewCopy} />
            <CopyRow label="民族" value={form.basic.ethnicity} previewCopy={previewCopy} />
            <CopyRow label="政治面貌" value={form.basic.politics} previewCopy={previewCopy} />
            <CopyRow label="手机号码" value={form.basic.phone} previewCopy={previewCopy} />
            <CopyRow label="电子邮箱" value={form.basic.email} previewCopy={previewCopy} />
            <CopyRow label="证件类型" value={form.basic.idType} previewCopy={previewCopy} />
            <CopyRow label="证件号码" value={form.basic.idNo} previewCopy={previewCopy} />
            <CopyRow label="现居住地" value={form.basic.city} previewCopy={previewCopy} />
            <CopyRow label="户口所在地" value={form.basic.hukou} previewCopy={previewCopy} />
          </div>
          <div className="item-block">
            <h3>求职意向</h3>
            <CopyRow label="招聘项目" value={form.intention.projectType} previewCopy={previewCopy} />
            <CopyRow label="期望职位" value={form.intention.expectRole} previewCopy={previewCopy} />
            <CopyRow label="期望城市" value={form.intention.expectCity} previewCopy={previewCopy} />
            <CopyRow label="到岗时间" value={form.intention.availability} previewCopy={previewCopy} />
          </div>
          {form.education.map((edu) => (
            <div key={edu.id} className="item-block">
              <h3>教育经历</h3>
              <CopyRow label="学校" value={edu.school} previewCopy={previewCopy} />
              <CopyRow label="学历" value={edu.degree} previewCopy={previewCopy} />
              <CopyRow label="专业" value={edu.major} previewCopy={previewCopy} />
              <CopyRow label="是否全日制" value={edu.fullTime} previewCopy={previewCopy} />
              <CopyRow label="在读时间" value={`${edu.start} ～ ${edu.end}`} previewCopy={previewCopy} />
              <CopyRow label="说明" value={edu.rank} allowed={false} previewCopy={previewCopy} />
            </div>
          ))}
          {form.internships.map((entry, index) => (
            <div key={entry.id} className="item-block">
              <h3>实习 {index + 1}</h3>
              <p className="muted">本地编辑的经历尚未重新核验；可复制参考，但不标为已阻断。</p>
              <CopyRow label="组织" value={entry.organization} previewCopy />
              <CopyRow label="职位" value={entry.title} previewCopy />
              <CopyRow label="角色" value={entry.role} previewCopy />
              <CopyRow label="时间" value={`${entry.start} ～ ${entry.end}`} previewCopy />
              <CopyRow label="描述" value={entry.description} previewCopy />
            </div>
          ))}
          {form.projects.map((entry, index) => (
            <div key={entry.id} className="item-block">
              <h3>项目 {index + 1}</h3>
              <p className="muted">本地编辑的经历尚未重新核验；可复制参考，但不标为已阻断。</p>
              <CopyRow label="组织" value={entry.organization} previewCopy />
              <CopyRow label="名称" value={entry.title} previewCopy />
              <CopyRow label="角色" value={entry.role} previewCopy />
              <CopyRow label="时间" value={`${entry.start} ～ ${entry.end}`} previewCopy />
              <CopyRow label="描述" value={entry.description} previewCopy />
            </div>
          ))}
          {(form.awards ?? []).map((award, index) => (
            <div key={award.id} className="item-block">
              <h3>获奖 / 竞赛 {index + 1}</h3>
              <CopyRow label="奖项名称" value={award.name} previewCopy={previewCopy} />
              <CopyRow label="颁发单位" value={award.issuer} previewCopy={previewCopy} />
              <CopyRow label="获奖时间" value={award.date} previewCopy={previewCopy} />
              <CopyRow label="说明" value={award.description} previewCopy={previewCopy} />
            </div>
          ))}
          <div className="item-block">
            <h3>技能与补充</h3>
            <p className="muted">这些本地文字尚未重新核验；可复制参考，但不标为已阻断。</p>
            <CopyRow label="技能" value={form.extras.skills} previewCopy />
            <CopyRow label="自我说明" value={form.extras.summary} previewCopy />
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
        {workflow.ats_form_mapping.fields.map((field) => {
          const control = workflow.field_controls.find((item) => item.field_id === field.field_id)
          const action = control?.action ?? field.action
          const blockedSources = field.source_claim_ids.filter(
            (id) => workflow.claim_verification.find((item) => item.claim_id === id)?.state === 'BLOCKED',
          )
          return (
            <div key={field.field_id}>
              {blockedSources.length > 0 && (
                <p className="muted">
                  该字段因其中 {blockedSources.length} 条陈述已阻断而不可作为已通过内容；请看下方标红的具体句子。
                </p>
              )}
              <CopyRow
                label={`${zhText(field.label)}（${zhLookup(ZH_ACTION, action)}）`}
                value={field.value}
                previewCopy={
                  previewCopy ||
                  action === 'BLOCKED' ||
                  !copyableField(workflow, claimDecisions, fieldDecisions, field)
                }
              />
            </div>
          )
        })}
        {workflow.ats_form_mapping.unmapped_fields.map((id) => (
          <CopyRow
            key={id}
            label={`${zhText(id)}（须本人填写）`}
            value=""
            previewCopy={previewCopy}
          />
        ))}
      </div>

      <div className="item-block">
        <h3>可粘贴陈述</h3>
        {workflow.resume_claims.map((claim) => {
          const decision = claimDecisions[claim.claim_id]
          if (decision?.decision === 'reject' || decision?.freshness === 'rejected') return null
          const state =
            workflow.claim_verification.find((v) => v.claim_id === claim.claim_id)?.state ?? 'NEEDS_REVIEW'
          const claimBlocked = state === 'BLOCKED'
          return (
            <div key={claim.claim_id} className="copy-claim">
              <p>
                <ClaimBadge status={state} />{' '}
                {zhLookup(ZH_DECISION, decision?.decision ?? '', '未处理')} ·{' '}
                {zhLookup(ZH_FRESHNESS, decision?.freshness ?? 'as_returned')}
                {claimBlocked ? (
                  <span className="danger-text">
                    {' '}
                    · {zhText(workflow.claim_verification.find((v) => v.claim_id === claim.claim_id)?.explanation)}
                  </span>
                ) : null}
              </p>
              <CopyRow
                label="陈述"
                value={claim.text}
                blocked={claimBlocked}
                previewCopy={previewCopy || claimBlocked || !copyableClaim(workflow, claimDecisions, claim.claim_id)}
              />
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

      {!readOnlyView && (
        <>
          <label className="field-label" htmlFor="note">
            模拟确认备注
          </label>
          <GroundedExport />
          <textarea
            id="note"
            className="jd-input"
            rows={3}
            value={confirmationNote}
            onChange={(e) => setConfirmationNote(e.target.value)}
          />
        </>
      )}
      {readOnlyView && (
        <div className="callout">
          <p className="muted">只读预览不提供确认备注编辑。返回申请内容检查后，仍按原规则确认。</p>
          <GroundedExport />
        </div>
      )}

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
          回退申请内容检查
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
              void validateExport().then((valid) => {
                if (valid) finishSimulation('SIMULATED_CONFIRMED')
                else setHistoryError('证据状态已改变或无法连接后端，请重新核验。')
              })
            }}
          >
            模拟确认（非投递）
          </button>
        )}
      </div>
    </section>
  )
}
