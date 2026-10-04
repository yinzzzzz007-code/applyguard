import { useNavigate } from 'react-router-dom'
import { EmptyState, LevelBadge, RiskBadge } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { ZH_ACTION, ZH_MAPPER, zhLookup, zhText } from '../i18n'

export function AtsSimulatorPage() {
  const navigate = useNavigate()
  const { workflow, fieldDecisions, setFieldDecision, atsFieldAcksComplete } = useDemo()

  if (!workflow) {
    return (
      <section className="panel">
        <header className="panel-head">
        <h2>网申模拟</h2>
        </header>
        <EmptyState
          title="无网申数据"
          detail="请先完成工作流。"
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
  const claimsById = Object.fromEntries(workflow.resume_claims.map((c) => [c.claim_id, c]))
  const blockedWorkflow = workflow.workflow_status === 'BLOCKED' || workflow.risk_result.action === 'BLOCKED'

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>网申模拟</h2>
        <p>
          对照拟填字段、管控等级与风险结果。这是本地模拟表，不是真实网站扫描，也不会实际提交。
        </p>
      </header>

      <div className="profile-card">
        <p>
          目标：网申模拟器 · 一致性：{zhLookup(ZH_ACTION, mapping.consistency_state)} · 汇总风险{' '}
          <RiskBadge level={workflow.risk_result.risk_level} /> · 动作{' '}
          {zhLookup(ZH_ACTION, workflow.risk_result.action)}
        </p>
        <p className="muted">
          映射方式：{zhLookup(ZH_MAPPER, workflow.component_modes?.ats_form_mapper, '固定映射')}
        </p>
      </div>

      {blockedWorkflow && (
        <div className="callout danger">
          工作流或风险结果为已阻断：不能当作可提交。仅可回退编辑或取消。
        </div>
      )}

      {workflow.component_modes?.jd_parser === 'RULE_FALLBACK' && (
        <div className="callout warn">
          <strong>回退提示：</strong>岗位解析为规则回退。
          {workflow.step_trace.find((s) => s.fallback_reason)?.fallback_reason
            ? ` ${zhText(workflow.step_trace.find((s) => s.fallback_reason)!.fallback_reason!)}`
            : ''}
        </div>
      )}

      <div className="stack">
        {mapping.fields.map((f) => {
          const control = controls[f.field_id]
          const level = control?.level ?? 'L0'
          const action = control?.action ?? f.action
          const d = fieldDecisions[f.field_id]
          return (
            <article key={f.field_id} className="item-block">
              <div className="item-head">
                <h3>{zhText(f.label)}</h3>
                <span>
                  <LevelBadge level={level} />{' '}
                  <span className="tag">{zhLookup(ZH_ACTION, action)}</span>
                </span>
              </div>
              <p>
                <strong>拟填值：</strong>
                {f.value}
              </p>
              <p>
                <strong>来源陈述：</strong>
                {f.source_claim_ids.length
                  ? f.source_claim_ids
                      .map(
                        (id) =>
                          `${id.replace(/^claim_/, '陈述·')}${claimsById[id] ? `（${claimsById[id].text.slice(0, 48)}…）` : ''}`,
                      )
                      .join('；')
                  : '无'}
              </p>
              {control?.show_sources && (
                <p className="muted">展示来源 · {zhLookup({ L0: '一级', L1: '二级', L2: '三级', L3: '四级' }, level)}</p>
              )}

              {action === 'BLOCKED' ? (
                <div className="action-pad">
                  <p className="danger-text">
                    已阻断：不可自动填充，也不可用确认绕过为可提交内容。
                  </p>
                  <label className="check-line">
                    <input
                      type="checkbox"
                      checked={!!d?.acknowledgedBlocked}
                      onChange={(e) =>
                        setFieldDecision(f.field_id, {
                          acknowledgedBlocked: e.target.checked,
                          confirmed: false,
                        })
                      }
                    />
                    我理解该字段保持阻止 / 不作为已具备内容提交（模拟）
                  </label>
                </div>
              ) : null}

              {action !== 'BLOCKED' && (level === 'L2' || action === 'REQUIRES_CONFIRMATION') ? (
                <div className="action-pad">
                  <p className="warn-text">
                    {level === 'L3'
                      ? '四级敏感 / 须确认：需用户本人确认，系统不推断。'
                      : '三级 / 须确认：必须查看原因并人工确认。'}
                  </p>
                  <label className="check-line">
                    <input
                      type="checkbox"
                      checked={!!d?.confirmed}
                      onChange={(e) =>
                        setFieldDecision(f.field_id, { confirmed: e.target.checked })
                      }
                    />
                    {level === 'L3'
                      ? '我确认将自行提供该敏感信息（模拟勾选，不提交）'
                      : '我已核对该字段拟填值与来源'}
                  </label>
                </div>
              ) : null}
            </article>
          )
        })}
      </div>

      {(workflow.field_controls ?? [])
        .filter((c) => !mapping.fields.some((f) => f.field_id === c.field_id))
        .map((control) => {
          const d = fieldDecisions[control.field_id]
          return (
            <article key={control.field_id} className="item-block">
              <div className="item-head">
                <h3>未映射字段：{zhText(control.field_id)}</h3>
                <span>
                  <LevelBadge level={control.level} />{' '}
                  <span className="tag">{zhLookup(ZH_ACTION, control.action)}</span>
                </span>
              </div>
              <p className="warn-text">无拟填值；不得从简历推断，须由用户本人提供。</p>
              {control.action !== 'BLOCKED' && (
                <label className="check-line">
                  <input
                    type="checkbox"
                    checked={!!d?.confirmed}
                    onChange={(e) =>
                      setFieldDecision(control.field_id, { confirmed: e.target.checked })
                    }
                  />
                  我理解需本人填写并确认（模拟，不提交）
                </label>
              )}
            </article>
          )
        })}

      <div className="callout">
        <h4>提交前风险检查</h4>
        <ul>
          {workflow.risk_result.risks.map((r) => (
            <li key={r.risk_id}>
              [{zhLookup({ WARNING: '警告', ERROR: '错误' }, r.severity)}] {zhText(r.message)} →{' '}
              {zhLookup(ZH_ACTION, r.recommended_action)}（{zhText(r.mitigation)}）
            </li>
          ))}
        </ul>
      </div>

      {!atsFieldAcksComplete() && (
        <div className="callout warn">
          请勾选：所有已阻断字段「保持阻止」，以及须确认的敏感字段「本人确认」。勾完后可进入人工确认页。
        </div>
      )}
      {atsFieldAcksComplete() && blockedWorkflow && (
        <div className="callout warn">
          字段确认已完成。整单仍为已阻断：下一页可以查看，但不能当作可提交。
        </div>
      )}

      <div className="btn-row end">
        <button type="button" className="btn secondary" onClick={() => navigate('/claims')}>
          回退陈述核验
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={!atsFieldAcksComplete()}
          onClick={() => navigate('/confirm')}
        >
          {blockedWorkflow ? '进入人工确认（查看，不可提交）' : '进入人工确认（模拟）'}
        </button>
      </div>
    </section>
  )
}
