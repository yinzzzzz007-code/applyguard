import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiClient, SAMPLE_JD, type WorkflowParseMode } from '../api/client'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { ZH_EXEC, ZH_MAPPER, ZH_PARSER, ZH_WORKFLOW, zhLookup } from '../i18n'

export function JdInputPage() {
  const navigate = useNavigate()
  const { jdRawInput, setJdRawInput, setWorkflow, scenario, workflow } = useDemo()
  const [status, setStatus] = useState<'idle' | 'loading' | 'empty' | 'error' | 'success'>(
    workflow ? 'success' : 'idle',
  )
  const [errorMsg, setErrorMsg] = useState('')
  const [backendHint, setBackendHint] = useState('')
  const [lastParseMode, setLastParseMode] = useState<WorkflowParseMode | null>(null)

  const run = useCallback(
    async (parseMode: WorkflowParseMode = 'offline') => {
      setStatus('loading')
      setErrorMsg('')
      setBackendHint('')
      setLastParseMode(parseMode)

      if (scenario === 'live') {
        const health = await getApiClient().getHealth()
        if (health.error) {
          setErrorMsg(health.error.message)
          setStatus('error')
          setWorkflow(null)
          return
        }
        setBackendHint(`${health.data?.service} ${health.data?.version} · ${health.data?.status}`)
      }

      const res = await getApiClient().runWorkflow(jdRawInput, { parseMode })
      if (res.empty && res.error?.code === 'EMPTY_JD') {
        setErrorMsg(res.error.message)
        setStatus('empty')
        setWorkflow(null)
        return
      }
      if (res.error) {
        setErrorMsg(res.error.message)
        setStatus('error')
        setWorkflow(null)
        return
      }
      if (!res.data) {
        setStatus('empty')
        setWorkflow(null)
        return
      }
      setWorkflow(res.data)
      setStatus('success')
    },
    [jdRawInput, scenario, setWorkflow],
  )

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>岗位说明</h2>
        <p>
          默认用离线规则解析岗位文本（不调用模型）。点「运行模型工作流」才会走模型；密钥只放在后端环境里，不会进浏览器。没配密钥时仍会规则回退。预录场景加载本地样例，不冒充本次实时计算。
        </p>
      </header>

      <label className="field-label" htmlFor="jd-input">
        岗位说明
      </label>
      <textarea
        id="jd-input"
        className="jd-input"
        rows={10}
        value={jdRawInput}
        onChange={(e) => setJdRawInput(e.target.value)}
        placeholder="至少 20 个字符…"
      />

      <div className="btn-row">
        <button type="button" className="btn secondary" onClick={() => setJdRawInput(SAMPLE_JD)}>
          填入示例岗位
        </button>
        <button type="button" className="btn secondary" onClick={() => setJdRawInput('')}>
          清空（测空输入）
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={status === 'loading'}
          onClick={() => void run('offline')}
        >
          {scenario.startsWith('prerecorded') ? '加载预录工作流' : '运行离线工作流'}
        </button>
        {scenario === 'live' && (
          <button
            type="button"
            className="btn secondary"
            disabled={status === 'loading'}
            onClick={() => void run('dynamic')}
            title="需要后端已配置模型密钥"
          >
            运行模型工作流
          </button>
        )}
      </div>

      {backendHint && <p className="muted">健康检查：{backendHint}</p>}
      {status === 'loading' && <LoadingState label="正在运行工作流…" />}
      {status === 'error' && (
        <ErrorState
          message={errorMsg}
          onRetry={() => void run(lastParseMode ?? 'offline')}
          onFallback={() => navigate('/')}
          fallbackLabel="回退经历库"
        />
      )}
      {status === 'empty' && (
        <EmptyState
          title="岗位说明为空或无效"
          detail={errorMsg || '请输入有效岗位说明。不会显示假成功结果。'}
          actionLabel="填入示例"
          onAction={() => setJdRawInput(SAMPLE_JD)}
        />
      )}
      {status === 'success' && workflow && (
        <div className="item-block">
          <h3>工作流已返回</h3>
          <p>
            状态：<strong>{zhLookup(ZH_WORKFLOW, workflow.workflow_status)}</strong> · 执行方式：
            {zhLookup(ZH_EXEC, workflow.execution_mode)} · 解析：
            {zhLookup(ZH_PARSER, workflow.component_modes?.jd_parser, '—')} · 网申映射：
            {zhLookup(ZH_MAPPER, workflow.component_modes?.ats_form_mapper, '—')}
            {lastParseMode ? (
              <>
                {' '}
                · 请求：{lastParseMode === 'dynamic' ? '模型解析' : '离线规则'}
              </>
            ) : null}
          </p>
          <p className="muted">
            解析岗位：{workflow.parsed_jd.title === 'UNKNOWN' ? '未知岗位' : workflow.parsed_jd.title}{' '}
            @ {workflow.parsed_jd.company === 'UNKNOWN' ? '未知公司' : workflow.parsed_jd.company} · 要求{' '}
            {workflow.parsed_jd.requirements.length} 条
          </p>
          {workflow.component_modes?.jd_parser === 'RULE_FALLBACK' && (
            <div className="callout warn">
              <p>
                岗位解析处于<strong>规则回退</strong>
                （不是页面坏了）。工作流仍会成功返回，用规则结果继续演示。
              </p>
              {lastParseMode === 'dynamic' ? (
                <p className="muted">
                  {(() => {
                    const reason = workflow.step_trace.find((s) => s.fallback_reason)?.fallback_reason
                    if (!reason) {
                      return '原因：后端未加载到模型密钥（改完配置后需重启后端）。'
                    }
                    if (reason.includes('not grounded') || reason.includes('JDParseError')) {
                      return '原因：模型有返回，但条目未能通过原文核对。已尽量保留可核对的中文词条。'
                    }
                    return '原因：模型调用失败后回退。常见：密钥无效、模型名不对、网络超时或输出被截断。'
                  })()}
                </p>
              ) : (
                <p className="muted">预录回退场景会标明模型超时原因，见步骤轨迹。</p>
              )}
            </div>
          )}
          {lastParseMode === 'dynamic' &&
            (workflow.component_modes?.jd_parser === 'MODEL' ||
              workflow.component_modes?.jd_parser === 'MODEL_SPAN_REPAIRED') && (
              <div className="callout">
                本次岗位解析走了模型路径（{zhLookup(ZH_PARSER, workflow.component_modes.jd_parser)}）。
              </div>
            )}
          <div className="btn-row end">
            <button type="button" className="btn primary" onClick={() => navigate('/match')}>
              下一步：证据匹配
            </button>
          </div>
        </div>
      )}
      {status === 'idle' && (
        <p className="muted tip">
          离线可直接演示；模型路径需先在启动后端的环境里配好密钥，再点「运行模型工作流」。
        </p>
      )}
    </section>
  )
}
