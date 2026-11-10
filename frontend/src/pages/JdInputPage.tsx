import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getApiClient, SAMPLE_JD, type WorkflowParseMode } from '../api/client'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useDemo } from '../context/DemoContext'
import { ZH_EXEC, ZH_MAPPER, ZH_PARSER, ZH_WORKFLOW, zhLookup, zhText } from '../i18n'
import { jobsRequest, type Opportunity } from '../api/jobs'
import { invalidateRestoredWorkflow } from '../resume/reviewSession'
import { canPrepareJob } from '../jobs'

export function JdInputPage() {
  const [params] = useSearchParams()
  const { activeJobId, workflow, setActiveJobId } = useDemo()
  const jobId = params.get('job') || activeJobId
  useEffect(() => {
    if (jobId && (!workflow || workflow.target_job?.id === jobId)) setActiveJobId(jobId)
  }, [jobId, workflow, setActiveJobId])
  return <JdInputSession key={jobId ?? 'manual'} jobId={jobId} />
}

function JdInputSession({ jobId }: { jobId: string | null }) {
  const navigate = useNavigate()
  const [, setParams] = useSearchParams()
  const [target, setTarget] = useState<Opportunity | null>(null)
  const [targetError, setTargetError] = useState('')
  const [loadingTarget, setLoadingTarget] = useState(Boolean(jobId))
  const { jdRawInput, setJdRawInput, setWorkflow, scenario, workflow, resumeForm, setResumeForm, reviewDrafts, setActiveJobId, invalidateWorkflow } = useDemo()
  const [loadingResume, setLoadingResume] = useState(scenario === 'live' && !resumeForm)
  const [resumeError, setResumeError] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'empty' | 'error' | 'success'>(
    workflow ? 'success' : 'idle',
  )
  const [errorMsg, setErrorMsg] = useState('')
  const [backendHint, setBackendHint] = useState('')
  const [lastParseMode, setLastParseMode] = useState<WorkflowParseMode | null>(null)
  const [parseMode, setParseMode] = useState<WorkflowParseMode>('offline')
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
  const [targetRevision, setTargetRevision] = useState(0)
  useEffect(() => {
    const reload = () => setTargetRevision(value => value + 1)
    window.addEventListener('applyguard:jobs-changed', reload)
    return () => window.removeEventListener('applyguard:jobs-changed', reload)
  }, [])
  useEffect(() => {
    let cancelled = false
    if (jobId) void jobsRequest<{ job: Opportunity }>(`/${encodeURIComponent(jobId)}`).then(({ job }) => {
      if (cancelled) return
      if (!canPrepareJob(job)) throw new Error('岗位已关闭、已归档或为参考快照，请重新选择。')
      setTargetError(''); setTarget(job); setJdRawInput(job.workflow_jd_text)
    }).catch((e) => { if (!cancelled) setTargetError(e.message) }).finally(() => { if (!cancelled) setLoadingTarget(false) })
    return () => { cancelled = true }
  }, [jobId, setJdRawInput, targetRevision])
  useEffect(() => {
    if (target && workflow?.target_job?.id === target.id &&
        workflow.target_job.content_hash !== target.content_hash && !workflow.requires_reverification) {
      invalidateWorkflow()
    }
  }, [target, workflow, invalidateWorkflow])

  const changeInput = (text: string) => {
    if (Object.keys(reviewDrafts).length) {setErrorMsg('请先返回简历审查保存或取消暂存修改，再更换岗位。');return}
    requestId.current += 1; setJdRawInput(text); setStatus('idle')
  }
  const detachTarget = () => {
    if (!window.confirm('解除收藏岗位关联并保留岗位原文？后续分析将作为手写岗位处理。')) return
    setActiveJobId(null)
    setParams({}, { replace: true })
    invalidateWorkflow()
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
      if (Object.keys(reviewDrafts).length) {setErrorMsg('请先返回简历审查保存或取消暂存修改，再重新分析。');return}
      const sameJob = workflow && (target
        ? workflow.target_job?.id === target.id
        : workflow.parsed_jd.source_text.trim() === jdRawInput.trim())
      if (!sameJob && workflow?.resume_claims.length &&
          !window.confirm('分析新的岗位说明会替换当前申请的正文。继续分析？')) return
      if (parseMode === 'dynamic' &&
          !window.confirm('将岗位原文及用于匹配的经历发送给后端配置的模型服务。继续使用模型？')) return
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
          return
        }
        setBackendHint(`${health.data?.service} ${health.data?.version} · ${health.data?.status}`)
      }

      const res = await getApiClient().runWorkflow(jdRawInput, {
        parseMode,
        applicationId: sameJob ? workflow.application_id : undefined,
        resumeDraft: resumeForm,
        targetJob: target ? { id: target.id, content_hash: target.content_hash } : undefined,
      })
      if (thisRequest !== requestId.current) return
      if (res.empty && res.error?.code === 'EMPTY_JD') {
        setErrorMsg(res.error.message)
        setStatus('empty')
        return
      }
      if (res.error) {
        setErrorMsg(res.error.message)
        setStatus('error')
        return
      }
      if (!res.data) {
        setStatus('empty')
        return
      }
      const next = sameJob && workflow.resume_claims.length
        ? invalidateRestoredWorkflow({ ...res.data, resume_claims: workflow.resume_claims,
          claim_verification: workflow.claim_verification, review_session: workflow.review_session },
          '已保留已写正文，请根据本次岗位版本重新核验。')
        : res.data
      setWorkflow(next)
      setActiveJobId(target?.id ?? null)
      setStatus('success')
    },
    [jdRawInput, resumeForm, scenario, setWorkflow, target, reviewDrafts, workflow, setActiveJobId],
  )

  return (
    <section className="panel">
      <header className="panel-head">
        <h2>岗位说明</h2>
        <p>
          粘贴招聘原文，查看哪些经历适合这个岗位。之后再检查每条表述的材料支持。
        </p>
      </header>
      <p><Link className="btn secondary" to="/jobs">从岗位雷达选择岗位</Link></p>
      {Object.keys(reviewDrafts).length > 0 && <p className="callout warn">审核页有暂存修改，请先 <Link to="/resume">返回保存修改</Link>。保存前不能重新分析或更换岗位。</p>}
      {errorMsg && status !== 'error' && status !== 'empty' && <p role="alert" className="danger-text">{errorMsg}</p>}
      {loadingTarget && <LoadingState label="正在载入收藏岗位…" />}
      {loadingResume && <LoadingState label="正在读取本机经历…" />}
      {resumeError && <ErrorState message={resumeError} onFallback={() => navigate('/vault')} fallbackLabel="检查经历库" />}
      {jobId && !loadingResume && !resumeForm && <p className="callout warn">收藏岗位需先使用自己的经历。请先 <Link to="/">导入简历</Link> 或在经历库保存草稿。</p>}
      {targetError && <ErrorState message={targetError} onFallback={() => navigate('/jobs')} fallbackLabel="返回岗位雷达" />}
      {targetError && jobId && <button type="button" className="text-action" onClick={detachTarget}>解除岗位关联</button>}
      {target && <div className="callout">
        <strong>{target.title} · {target.company} · v{target.version}</strong>
        <p>已关联收藏岗位。要手动编辑原文，请先解除关联。</p>
        {workflow?.target_job?.id === target.id && workflow.target_job.content_hash !== target.content_hash &&
          <p role="status">岗位已更新，请重新分析新版。已写正文会保留。</p>}
        <button type="button" className="text-action" onClick={detachTarget}>解除岗位关联</button>
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
        readOnly={Boolean(jobId)}
        disabled={loadingTarget || Boolean(targetError) || status === 'loading'}
        onChange={(e) => changeInput(e.target.value)}
        placeholder="至少 20 个字符…"
      />

      <label className="field-label" htmlFor="jd-parse-mode">岗位解析方式</label>
      <select id="jd-parse-mode" value={parseMode} disabled={status === 'loading'} onChange={e => setParseMode(e.target.value as WorkflowParseMode)}>
        <option value="offline">本地规则</option><option value="dynamic">AI 解析（需要配置模型）</option>
      </select>
      <p className="muted">{parseMode === 'offline' ? '岗位解析、经历匹配和材料核验均在本机进行。仅在你主动请求 AI 润色并确认后，才会发送相关内容。' : '岗位正文和参与匹配的经历可能发送给配置的模型服务。'}</p>
      <div className="btn-row">
        <button type="button" className="btn secondary" disabled={Boolean(jobId) || loadingTarget || status === 'loading'} onClick={() => changeInput(SAMPLE_JD)}>
          填入示例岗位
        </button>
        <button type="button" className="btn secondary" disabled={Boolean(jobId) || loadingTarget || status === 'loading'} onClick={() => changeInput('')}>
          清空
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={status === 'loading' || loadingTarget || loadingResume || Boolean(targetError) || Boolean(resumeError) || Boolean(jobId && !resumeForm)}
          onClick={() => void run(parseMode)}
        >
          {status === 'loading' ? '正在分析岗位…' : scenario.startsWith('prerecorded') ? '加载演示结果' : '分析岗位并匹配经历'}
        </button>
      </div>

      {backendHint && <details className="processing-details"><summary>连接详情</summary><p>{backendHint}</p></details>}
      {status === 'loading' && <LoadingState label="正在运行工作流…" />}
      {status === 'error' && (
        <ErrorState
          message={errorMsg}
          onRetry={() => void run(lastParseMode ?? 'offline')}
          onFallback={() => navigate('/vault')}
          fallbackLabel="回退经历库"
        />
      )}
      {status === 'empty' && (
        <EmptyState
          title="岗位说明为空或无效"
          detail={errorMsg || '请输入有效岗位说明。不会显示假成功结果。'}
          actionLabel="填入示例"
          onAction={jobId ? undefined : () => changeInput(SAMPLE_JD)}
        />
      )}
      {status === 'success' && workflow && (
        <div className="item-block">
          <h3>已识别 {workflow.parsed_jd.requirements.length} 项岗位要求</h3>
          <p>匹配结果已准备好，请继续检查相关经历与依据。</p>
          <details className="processing-details"><summary>查看处理详情</summary><p>
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
          </p></details>
          <p className="muted">
            解析岗位：{workflow.parsed_jd.title === 'UNKNOWN' ? '未知岗位' : workflow.parsed_jd.title}{' '}
            @ {workflow.parsed_jd.company === 'UNKNOWN' ? '未知公司' : workflow.parsed_jd.company} · 要求{' '}
            {workflow.parsed_jd.requirements.length} 条
          </p>
          {ruleParsed && (
            <div className="callout warn">
              {offlineRules ? (
                <p className="muted">
                  离线规则保留明确列出的任职要求和加分项。无法判定的条目请对照原文人工核对。
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
