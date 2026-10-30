import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getApiClient, SAMPLE_JD, type WorkflowParseMode } from '../api/client'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { ZH_EXEC, ZH_MAPPER, ZH_PARSER, ZH_WORKFLOW, zhLookup, zhText } from '../i18n'
import { jobsRequest, type Opportunity } from '../api/jobs'
import { canPrepareJob } from '../jobs'

export function JdInputPage() {
  const [params] = useSearchParams()
  const jobId = params.get('job')
  return <JdInputSession key={jobId ?? 'manual'} jobId={jobId} />
}

function JdInputSession({ jobId }: { jobId: string | null }) {
  const navigate = useNavigate()
  const [, setParams] = useSearchParams()
  const [target, setTarget] = useState<Opportunity | null>(null)
  const [targetError, setTargetError] = useState('')
  const [loadingTarget, setLoadingTarget] = useState(Boolean(jobId))
  const { jdRawInput, setJdRawInput, setWorkflow, scenario, workflow, resumeForm, setResumeForm } = useDemo()
  const [loadingResume, setLoadingResume] = useState(scenario === 'live' && !resumeForm)
  const [resumeError, setResumeError] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'empty' | 'error' | 'success'>(
    workflow ? 'success' : 'idle',
  )
  const [errorMsg, setErrorMsg] = useState('')
  const [backendHint, setBackendHint] = useState('')
  const [lastParseMode, setLastParseMode] = useState<WorkflowParseMode | null>(null)
  const requestId = useRef(0)
  useEffect(() => {
    if (resumeForm || scenario !== 'live') return
    let cancelled = false
    void getApiClient().getResumeDraft().then((result) => {
      if (cancelled) return
      if (result.data) setResumeForm(result.data)
      if (result.error) setResumeError(result.error.message)
      setLoadingResume(false)
    })
    return () => { cancelled = true }
  }, [resumeForm, scenario, setResumeForm])
  useEffect(() => { requestId.current += 1; return () => { requestId.current += 1 } }, [jdRawInput, resumeForm, scenario, workflow])
  useEffect(() => {
    let cancelled = false
    if (jobId) void jobsRequest<{ job: Opportunity }>(`/${encodeURIComponent(jobId)}`).then(({ job }) => {
      if (cancelled) return
      if (!canPrepareJob(job)) throw new Error('岗位已关闭、已归档或为参考快照，请重新选择。')
      setTarget(job); setJdRawInput(job.workflow_jd_text)
    }).catch((e) => { if (!cancelled) setTargetError(e.message) }).finally(() => { if (!cancelled) setLoadingTarget(false) })
    return () => { cancelled = true }
  }, [jobId, setJdRawInput])
  const changeInput = (text: string) => {
    requestId.current += 1; setJdRawInput(text); setStatus('idle')
    if (jobId) { setTarget(null); setParams({}, { replace: true }) }
  }
  const jdFallbackReason = workflow?.step_trace.find((step) => step.step === 'JD Parser')?.fallback_reason
  const requestedMode = workflow?.component_modes?.requested_parse_mode
  const ruleParsed = workflow?.component_modes?.jd_parser === 'RULE_FALLBACK'
  const offlineRules = ruleParsed && !jdFallbackReason && (requestedMode === 'OFFLINE' || !requestedMode)
  const executionLabel = offlineRules
    ? '离线规则解析'
    : ruleParsed && jdFallbackReason
      ? '模型失败后规则回退'
      : zhLookup(ZH_EXEC, workflow?.execution_mode)

  const run = useCallback(
    async (parseMode: WorkflowParseMode = 'offline') => {
      const thisRequest = ++requestId.current
      setStatus('loading')
      setErrorMsg('')
      setBackendHint('')
      setLastParseMode(parseMode)

      if (scenario === 'live') {
        const health = await getApiClient().getHealth()
        if (thisRequest !== requestId.current) return
        if (health.error) {
          setErrorMsg(health.error.message)
          setStatus('error')
          setWorkflow(null)
          return
        }
        setBackendHint(`${health.data?.service} ${health.data?.version} · ${health.data?.status}`)
      }

      const res = await getApiClient().runWorkflow(jdRawInput, {
        parseMode,
        resumeDraft: resumeForm,
        targetJob: target ? { id: target.id, content_hash: target.content_hash } : undefined,
      })
      if (thisRequest !== requestId.current) return
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
    [jdRawInput, resumeForm, scenario, setWorkflow, target],
  )

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>岗位说明</h2>
        <p>
          粘贴目标岗位，找出与经历匹配的要求。岗位解析可使用离线规则；SAG 单独按服务端配置启用，启用后会发送相关材料给模型服务。
        </p>
      </header>
      <p><Link className="btn secondary" to="/jobs">从岗位雷达选择岗位</Link></p>
      {loadingTarget && <LoadingState label="正在载入收藏岗位…" />}
      {loadingResume && <LoadingState label="正在读取本机经历…" />}
      {resumeError && <ErrorState message={resumeError} onFallback={() => navigate('/vault')} fallbackLabel="检查经历库" />}
      {jobId && !loadingResume && !resumeForm && <p className="callout warn">收藏岗位需先使用自己的经历。请先 <Link to="/">导入简历</Link> 或在经历库保存草稿。</p>}
      {targetError && <ErrorState message={targetError} onFallback={() => navigate('/jobs')} fallbackLabel="返回岗位雷达" />}
      {target && <div className="callout">
        <strong>{target.title} · {target.company} · v{target.version}</strong>
        <p>已关联收藏岗位。修改原文会解除关联；岗位更新后需重新载入并校验。</p>
        {target.url && <a href={target.url} target="_blank" rel="noreferrer">核对招聘原文 ↗</a>}
      </div>}

      <label className="field-label" htmlFor="jd-input">
        岗位说明
      </label>
      <textarea
        id="jd-input"
        className="jd-input"
        rows={10}
        value={jdRawInput}
        disabled={loadingTarget || Boolean(targetError) || status === 'loading'}
        onChange={(e) => changeInput(e.target.value)}
        placeholder="至少 20 个字符…"
      />

      <div className="btn-row">
        <button type="button" className="btn secondary" disabled={loadingTarget || status === 'loading'} onClick={() => changeInput(SAMPLE_JD)}>
          填入示例岗位
        </button>
        <button type="button" className="btn secondary" disabled={loadingTarget || status === 'loading'} onClick={() => changeInput('')}>
          清空
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={status === 'loading' || loadingTarget || loadingResume || Boolean(targetError) || Boolean(resumeError) || Boolean(jobId && !resumeForm)}
          onClick={() => void run('offline')}
        >
          {scenario.startsWith('prerecorded') ? '加载预录工作流' : '运行离线工作流'}
        </button>
        {scenario === 'live' && (
          <button
            type="button"
            className="btn secondary"
            disabled={status === 'loading' || loadingTarget || loadingResume || Boolean(targetError) || Boolean(resumeError) || Boolean(jobId && !resumeForm)}
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
            {executionLabel} · 解析：
            {offlineRules ? '离线规则' : zhLookup(ZH_PARSER, workflow.component_modes?.jd_parser, '—')} · 网申映射：
            {zhLookup(ZH_MAPPER, workflow.component_modes?.ats_form_mapper, '—')}
            {requestedMode ? (
              <>
                {' '}
                · 请求：{requestedMode === 'DYNAMIC' ? '模型解析' : '离线规则'}
              </>
            ) : null}
          </p>
          <p className="muted">
            解析岗位：{workflow.parsed_jd.title === 'UNKNOWN' ? '未知岗位' : workflow.parsed_jd.title}{' '}
            @ {workflow.parsed_jd.company === 'UNKNOWN' ? '未知公司' : workflow.parsed_jd.company} · 要求{' '}
            {workflow.parsed_jd.requirements.length} 条
          </p>
          {ruleParsed && (
            <div className="callout warn">
              {offlineRules ? (
                <p className="muted">
                  本次主动选择离线解析，只提取规则能识别的要求；结果可能少于岗位原文，建议逐条核对。
                </p>
              ) : (
                <p className="muted">
                  {jdFallbackReason
                    ? `模型解析未通过，已改用规则结果。原因：${zhText(jdFallbackReason)}`
                    : '模型路径未启用，已用规则结果继续。请检查后端模型密钥配置。'}
                </p>
              )}
            </div>
          )}
          {requestedMode === 'DYNAMIC' &&
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
          岗位可离线解析；使用模型解析、SAG检索或原子事实核验需先在后端配置密钥。
        </p>
      )}
    </section>
  )
}
