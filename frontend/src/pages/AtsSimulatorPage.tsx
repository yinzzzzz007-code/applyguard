import { Link, useNavigate } from 'react-router-dom'
import { ClaimBadge, EmptyState, LevelBadge, RiskBadge } from '../components/States'
import { useDemo } from '../context/DemoContext'
import {
  buildCheckNotices,
  buildSummaryClaimRows,
  claimsNeedEvidenceCheck,
  collectTechDetails,
  findSummaryField,
  isWorkflowBlocked,
  riskLabel,
} from '../atsCheckView'
import { ZH_ACTION, ZH_MAPPER, zhLookup, zhText } from '../i18n'

export function AtsSimulatorPage() {
  const navigate = useNavigate()
  const {
    workflow,
    resumeForm,
    fieldDecisions,
    setFieldDecision,
    atsFieldAcksComplete,
  } = useDemo()

  if (!workflow) {
    return (
      <section className="panel">
        <header className="panel-head">
          <h2>申请内容检查</h2>
        </header>
        <EmptyState
          title="无申请检查数据"
          detail="请先完成岗位分析与陈述核验。分析草稿会保存在本机后端，源头变更后需重新分析。"
          actionLabel="去岗位说明"
          onAction={() => navigate('/jd')}
        />
      </section>
    )
  }

  const mapping = workflow.ats_form_mapping
  const controls = Object.fromEntries(
    (workflow.field_controls ?? []).map((c) => [c.field_id, c]),
  )
  const blockedWorkflow = isWorkflowBlocked(workflow)
  const needsEvidence = claimsNeedEvidenceCheck(workflow)
  const acksComplete = atsFieldAcksComplete()
  const summaryField = findSummaryField(workflow)
  const summaryControl = summaryField ? controls[summaryField.field_id] : undefined
  const { rows: summaryRows, summaryOnlyReason } = buildSummaryClaimRows(workflow, resumeForm)
  const { actionable, details } = buildCheckNotices(workflow)
  const techDetails = collectTechDetails(workflow)
  const jdFallbackReason = workflow.step_trace.find((step) => step.step === 'JD Parser')?.fallback_reason
  const offlineRules =
    !jdFallbackReason &&
    (workflow.component_modes?.requested_parse_mode === 'OFFLINE' ||
      !workflow.component_modes?.requested_parse_mode)

  const selfFillControls = (workflow.field_controls ?? []).filter(
    (control) => !mapping.fields.some((field) => field.field_id === control.field_id),
  )

  const statusTitle = blockedWorkflow
    ? '当前不可作为可提交内容'
    : needsEvidence
      ? '有经历仍需核对依据'
      : !acksComplete
        ? '还有信息需要本人确认'
        : '检查通过，可进入确认页'

  const statusDetail = blockedWorkflow
    ? needsEvidence
      ? '存在缺少依据或已阻断的经历。请先回陈述核验处理，再决定是否继续。'
      : '整单已阻断。可以只读查看确认页，但不会解除阻断，也不能当作可提交。'
    : needsEvidence
      ? '部分陈述仍待复核。建议先核对经历与材料。'
      : !acksComplete
        ? '演示表单中仍有须本人填写或确认的项。勾选“我理解”只表示已知悉，不算已填写。'
        : '拟填内容与风险检查未发现阻断项。进入确认页后仍可复制填写稿，最终提交由本人完成。'

  const primaryToClaims = blockedWorkflow || needsEvidence

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>申请内容检查</h2>
        <p>核对准备填写的内容，并补充缺失的信息。本页使用演示表单。</p>
      </header>

      <article className={`profile-card ${blockedWorkflow ? 'callout danger' : needsEvidence || !acksComplete ? 'callout warn' : 'callout ok'}`}>
        <div className="item-head">
          <h3>当前状态和下一步</h3>
          <span>
            <RiskBadge level={workflow.risk_result.risk_level} />{' '}
            <span className="tag">{zhLookup(ZH_ACTION, workflow.risk_result.action)}</span>
          </span>
        </div>
        <p>
          <strong>{statusTitle}</strong>
        </p>
        <p>{statusDetail}</p>
        <p className="muted">
          一致性：{zhLookup(ZH_ACTION, mapping.consistency_state)} · 映射方式：
          {zhLookup(ZH_MAPPER, workflow.component_modes?.ats_form_mapper, '固定映射')}
        </p>
        <div className="btn-row">
          {primaryToClaims ? (
            <button type="button" className="btn primary" onClick={() => navigate('/claims')}>
              去核对经历
            </button>
          ) : (
            <button
              type="button"
              className="btn primary"
              disabled={!acksComplete}
              onClick={() => navigate('/confirm')}
            >
              进入确认页
            </button>
          )}
          <button type="button" className="btn secondary" onClick={() => navigate('/confirm?view=1')}>
            查看确认页
          </button>
        </div>
        {blockedWorkflow && (
          <p className="muted">查看确认页为只读预览，无需勾选“我理解”，也不会解除阻断。</p>
        )}
        {!primaryToClaims && !acksComplete && (
          <p className="muted">完成下方「需要本人填写」确认后，即可进入确认页。</p>
        )}
      </article>

      <div className="stack">
        <h3>候选人摘要</h3>
        <p className="muted">按来源经历查看核验状态。完整拟填内容默认折叠。</p>

        {summaryOnlyReason && (
          <div className="callout warn">
            <p>{summaryOnlyReason}</p>
            {summaryField && (
              <p className="muted">摘要状态：{zhLookup(ZH_ACTION, summaryControl?.action ?? summaryField.action)}</p>
            )}
          </div>
        )}

        {summaryRows.map((row) => (
          <article
            key={row.claimId}
            className={
              row.state === 'BLOCKED'
                ? 'item-block claim blocked'
                : row.state === 'NEEDS_REVIEW'
                  ? 'item-block claim needs'
                  : 'item-block'
            }
          >
            <div className="item-head">
              <h3>{row.title}</h3>
              {row.state === 'UNKNOWN' ? (
                <span className="badge muted">无核验结果</span>
              ) : (
                <ClaimBadge status={row.state} />
              )}
            </div>
            <p>{row.reason}</p>
            {row.pinpoint && <p className="warn-text">{row.pinpoint}</p>}
            {row.linkToClaim ? (
              <p>
                <Link to={`/claims#${row.claimId}`}>前往陈述核验中的对应句子</Link>
              </p>
            ) : (
              <p className="muted">现有结果只能说明摘要侧问题，无法可靠跳到某一句。</p>
            )}
          </article>
        ))}

        {summaryField && (
          <details>
            <summary>完整拟填内容、来源编号与管控等级</summary>
            <div className="item-block">
              <p>
                <strong>拟填值：</strong>
                {summaryField.value || '无'}
              </p>
              <p>
                <strong>来源陈述编号：</strong>
                {summaryField.source_claim_ids.length
                  ? summaryField.source_claim_ids.map((id) => id.replace(/^claim_/, '陈述·')).join('；')
                  : '无'}
              </p>
              <p>
                <LevelBadge level={summaryControl?.level ?? 'L0'} />{' '}
                <span className="tag">{zhLookup(ZH_ACTION, summaryControl?.action ?? summaryField.action)}</span>
              </p>
              {(summaryControl?.action ?? summaryField.action) === 'BLOCKED' ? (
                <div className="action-pad">
                  <p className="danger-text">已阻断：不可自动填充，也不可用确认绕过为可提交内容。</p>
                  <label className="check-line">
                    <input
                      type="checkbox"
                      checked={!!fieldDecisions[summaryField.field_id]?.acknowledgedBlocked}
                      onChange={(e) =>
                        setFieldDecision(summaryField.field_id, {
                          acknowledgedBlocked: e.target.checked,
                          confirmed: false,
                        })
                      }
                    />
                    我理解该字段保持阻止 / 不作为已具备内容提交（模拟）
                  </label>
                </div>
              ) : null}
              {(summaryControl?.action ?? summaryField.action) !== 'BLOCKED' &&
              (summaryControl?.level === 'L2' ||
                summaryControl?.action === 'REQUIRES_CONFIRMATION' ||
                summaryField.action === 'REQUIRES_CONFIRMATION') ? (
                <div className="action-pad">
                  <label className="check-line">
                    <input
                      type="checkbox"
                      checked={!!fieldDecisions[summaryField.field_id]?.confirmed}
                      onChange={(e) =>
                        setFieldDecision(summaryField.field_id, { confirmed: e.target.checked })
                      }
                    />
                    我已核对该字段拟填值与来源
                  </label>
                </div>
              ) : null}
            </div>
            {mapping.fields
              .filter((field) => field.field_id !== summaryField.field_id)
              .map((field) => {
                const control = controls[field.field_id]
                const decision = fieldDecisions[field.field_id]
                const action = control?.action ?? field.action
                const level = control?.level ?? 'L0'
                return (
                  <div className="item-block" key={field.field_id}>
                    <div className="item-head">
                      <h3>{zhText(field.label)}</h3>
                      <span>
                        <LevelBadge level={level} />{' '}
                        <span className="tag">{zhLookup(ZH_ACTION, action)}</span>
                      </span>
                    </div>
                    <p>
                      <strong>拟填值：</strong>
                      {field.value || '无'}
                    </p>
                    <p className="muted">
                      来源：
                      {field.source_claim_ids.length
                        ? field.source_claim_ids.map((id) => id.replace(/^claim_/, '陈述·')).join('；')
                        : '无'}
                    </p>
                    {action === 'BLOCKED' ? (
                      <label className="check-line">
                        <input
                          type="checkbox"
                          checked={!!decision?.acknowledgedBlocked}
                          onChange={(e) =>
                            setFieldDecision(field.field_id, {
                              acknowledgedBlocked: e.target.checked,
                              confirmed: false,
                            })
                          }
                        />
                        我理解该字段保持阻止 / 不作为已具备内容提交（模拟）
                      </label>
                    ) : null}
                    {action !== 'BLOCKED' &&
                    (level === 'L2' || level === 'L3' || action === 'REQUIRES_CONFIRMATION') ? (
                      <label className="check-line">
                        <input
                          type="checkbox"
                          checked={!!decision?.confirmed}
                          onChange={(e) =>
                            setFieldDecision(field.field_id, { confirmed: e.target.checked })
                          }
                        />
                        我已核对该字段拟填值与来源
                      </label>
                    ) : null}
                  </div>
                )
              })}
          </details>
        )}
      </div>

      <div className="stack">
        <h3>需要本人填写</h3>
        {selfFillControls.length === 0 ? (
          <p className="muted">当前演示表单没有须本人另行填写的未映射项。</p>
        ) : (
          selfFillControls.map((control) => {
            const decision = fieldDecisions[control.field_id]
            const label =
              control.field_id === 'work_authorization' ? '工作许可' : zhText(control.field_id)
            return (
              <article key={control.field_id} className="item-block">
                <div className="item-head">
                  <h3>{label}</h3>
                  <span className="badge warn">待本人填写</span>
                </div>
                <p className="muted">
                  {control.field_id === 'work_authorization'
                    ? '该字段来自演示表单固定模板，系统不会从简历推断。'
                    : '演示表单未映射项，须由本人提供。'}
                </p>
                <p className="warn-text">状态：待本人填写。勾选“我理解”只表示已知悉，不表示已填写完成。</p>
                <p className="muted">本系统暂无该字段的独立填写入口；请在真实网申中自行填写。</p>
                {control.action !== 'BLOCKED' && (
                  <label className="check-line">
                    <input
                      type="checkbox"
                      checked={!!decision?.confirmed}
                      onChange={(e) =>
                        setFieldDecision(control.field_id, { confirmed: e.target.checked })
                      }
                    />
                    我理解需本人填写并确认（模拟，不提交）
                  </label>
                )}
              </article>
            )
          })
        )}
      </div>

      <div className="stack">
        <h3>其他检查结果</h3>
        <p className="muted">优先展示需要处理的问题；重复提醒已合并。</p>

        {workflow.component_modes?.jd_parser === 'RULE_FALLBACK' && (
          <div className="callout warn">
            <strong>{offlineRules ? '离线解析：' : '回退提示：'}</strong>
            {offlineRules
              ? '岗位要求由规则提取，请与原文核对。'
              : jdFallbackReason
                ? '模型解析未通过，已用规则结果继续。'
                : '模型未启用，已用规则结果继续。'}
            {jdFallbackReason && !offlineRules ? ` ${zhText(jdFallbackReason)}` : ''}
          </div>
        )}

        {actionable.length === 0 ? (
          <div className="callout ok">没有额外需要优先处理的检查项。</div>
        ) : (
          actionable.map((notice) => {
            if (notice.kind === 'offline') {
              return (
                <div className="callout warn" key={notice.key}>
                  <p>
                    <strong>离线提醒</strong>
                    {notice.count > 1 ? `（已合并 ${notice.count} 条）` : ''}
                  </p>
                  <p>{notice.message}</p>
                </div>
              )
            }
            if (notice.kind === 'uncovered') {
              return (
                <details className="callout warn" key={notice.key}>
                  <summary>
                    <strong>{notice.message}</strong>
                  </summary>
                  <ul>
                    {notice.requirements.map((requirement) => (
                      <li key={requirement.id}>
                        <div>
                          {requirement.text}
                          <span className="muted">（{requirement.id.replace(/^req_0*/, '要求 ')}）</span>
                        </div>
                        <p className="muted">{requirement.note}</p>
                      </li>
                    ))}
                  </ul>
                  <p className="muted">
                    只对照现有填写与经历是否写到；学历、专业等个人信息以本人填写为准，不要求另附材料。明细也可在{' '}
                    <Link to="/match">证据匹配</Link> 查看。
                  </p>
                </details>
              )
            }
            return (
              <div
                className={`callout ${notice.severity === 'ERROR' ? 'danger' : 'warn'}`}
                key={notice.key}
              >
                <p>{notice.message}</p>
                {notice.mitigation && <p className="muted">{notice.mitigation}</p>}
              </div>
            )
          })
        )}

        <details>
          <summary>处理详情</summary>
          <div className="item-block">
            <h4>固定映射与技术信息</h4>
            <ul className="ats-summary">
              {techDetails.map((line) => (
                <li key={line}>{line}</li>
              ))}
              {!techDetails.length && <li className="muted">无额外技术信息</li>}
            </ul>
            {details.length > 0 && (
              <>
                <h4>已归入摘要 / 待填项的提示</h4>
                <ul>
                  {details.map((notice) =>
                    notice.kind === 'detail' || notice.kind === 'action' ? (
                      <li key={notice.key}>
                        [{zhLookup({ WARNING: '警告', ERROR: '错误' }, notice.severity)}] {notice.message}
                        {notice.mitigation ? `（${notice.mitigation}）` : ''}
                      </li>
                    ) : null,
                  )}
                </ul>
              </>
            )}
            <h4>完整检查记录</h4>
            <ul>
              {workflow.risk_result.risks.map((risk) => (
                <li key={risk.risk_id}>
                  [{zhLookup({ WARNING: '警告', ERROR: '错误' }, risk.severity)}] {riskLabel(risk)}
                </li>
              ))}
            </ul>
          </div>
        </details>
      </div>

      {!acksComplete && !blockedWorkflow && (
        <div className="callout warn">
          实际进入确认操作前，请完成须确认字段的勾选。仅查看确认页不必勾选。
        </div>
      )}
      {acksComplete && blockedWorkflow && (
        <div className="callout warn">
          字段确认已完成。整单仍为已阻断：确认页可以只读查看，但不能当作可提交。
        </div>
      )}

      <div className="btn-row end">
        <button type="button" className="btn secondary" onClick={() => navigate('/claims')}>
          回退陈述核验
        </button>
        {primaryToClaims ? (
          <button type="button" className="btn primary" onClick={() => navigate('/claims')}>
            去核对经历
          </button>
        ) : (
          <button
            type="button"
            className="btn primary"
            disabled={!acksComplete}
            onClick={() => navigate('/confirm')}
          >
            进入确认页
          </button>
        )}
        <button type="button" className="btn secondary" onClick={() => navigate('/confirm?view=1')}>
          查看确认页
        </button>
      </div>
    </section>
  )
}
