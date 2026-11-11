import {
  createContext,
  useEffect,
  useRef,
  useCallback,
  useContext,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react'
import {
  getActiveScenario,
  getApiClient,
  setActiveScenario as setScenarioInClient,
} from '../api/client'
import type {
  ClaimState,
  DemoScenario,
  EditableResumeForm,
  LocalClaimDecision,
  LocalFieldDecision,
  WorkflowResponse,
} from '../api/types'
import { zhLookup } from '../i18n'
import type { FlowStep } from '../flow'
import { invalidateRestoredWorkflow, loadReviewSession, saveReviewSession } from '../resume/reviewSession'

interface DemoState {
  reviewDrafts: Record<string, string>
  setReviewDraft: (id: string, text: string | null) => void
  reviewStorageError: string
  restoredAt: string
  scenario: DemoScenario
  step: FlowStep
  jdRawInput: string
  activeJobId: string | null
  setActiveJobId: (id: string | null) => void
  invalidateWorkflow: () => void
  workflow: WorkflowResponse | null
  workflowSourceNotice: string
  resumeForm: EditableResumeForm | null
  dataSourceLabel: string
  claimDecisions: Record<string, LocalClaimDecision>
  fieldDecisions: Record<string, LocalFieldDecision>
  confirmationNote: string
  simulatedConfirmed: boolean
  setScenario: (s: DemoScenario) => void
  setStep: (s: FlowStep) => void
  setJdRawInput: (v: string) => void
  setWorkflow: (w: WorkflowResponse | null) => void
  reverifyClaims: () => Promise<string | null>
  validateExport: () => Promise<boolean>
  patchWorkflow: (patch: Partial<WorkflowResponse> | ((w: WorkflowResponse) => WorkflowResponse)) => void
  setResumeForm: Dispatch<SetStateAction<EditableResumeForm | null>>
  setClaimDecision: (claimId: string, patch: Partial<LocalClaimDecision>) => void
  setFieldDecision: (fieldId: string, patch: Partial<LocalFieldDecision>) => void
  setConfirmationNote: (v: string) => void
  setSimulatedConfirmed: (v: boolean) => void
  resetFlow: () => void
  verificationOf: (claimId: string) => ClaimState | undefined
  canProceedFromClaims: () => boolean
  atsFieldAcksComplete: () => boolean
  canSubmitAts: () => boolean
}

const DemoContext = createContext<DemoState | null>(null)

function readSession(key: string): string | null {
  try { return sessionStorage.getItem(key) } catch { return null }
}

function readUnsavedResume(): EditableResumeForm | null {
  try {
    const form = JSON.parse(readSession('applyguard.resume-edit.v1') ?? 'null')
    return form?.dirty && typeof form.candidateId === 'string' && form.basic &&
      Array.isArray(form.education) && Array.isArray(form.internships) && Array.isArray(form.projects) ? form : null
  } catch { return null }
}

function sourceLabel(scenario: DemoScenario, workflow: WorkflowResponse | null): string {
  if (workflow?._prerecorded) {
    return `预录 · ${zhLookup({ unsupported_block: '不支持阻断', timeout_fallback: '超时回退' }, workflow._prerecorded.case)}`
  }
  if (scenario === 'live' && workflow) {
    const parser = workflow.component_modes?.jd_parser
    if (parser === 'MODEL' || parser === 'MODEL_SPAN_REPAIRED') return '在线 · 模型解析'
    if (workflow.component_modes?.requested_parse_mode === 'DYNAMIC' ||
        workflow.step_trace.some((step) => step.step === 'JD Parser' && step.fallback_reason)) {
      return '在线 · 模型路径转规则'
    }
    return '在线 · 离线规则'
  }
  if (scenario === 'error') return '错误演示（无成功响应）'
  return '尚未运行工作流'
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [restored] = useState(() => loadReviewSession(sessionStorage))
  const [reviewDrafts, setReviewDrafts] = useState<Record<string,string>>(restored?.drafts ?? {})
  const [reviewStorageError, setReviewStorageError] = useState('')
  const [restoredAt, setRestoredAt] = useState(restored?.savedAt ?? '')
  const [workflowSourceNotice, setWorkflowSourceNotice] = useState('')
  const [scenario, setScenarioState] = useState<DemoScenario>(getActiveScenario())
  const [step, setStep] = useState<FlowStep>('import')
  const [jdRawInput, setJdRawInput] = useState(() => restored?.jd ?? readSession('applyguard.jd') ?? '')
  const [activeJobId, setActiveJobId] = useState(() => (readSession('applyguard.job') ?? restored?.workflow.target_job?.id) || null)
  const [workflow, setWorkflowState] = useState<WorkflowResponse | null>(restored?.workflow ?? null)
  const [resumeForm, setResumeForm] = useState<EditableResumeForm | null>(readUnsavedResume() ?? restored?.form ?? null)
  const [claimDecisions, setClaimDecisions] = useState<Record<string, LocalClaimDecision>>({})
  const [fieldDecisions, setFieldDecisions] = useState<Record<string, LocalFieldDecision>>({})
  const [confirmationNote, setConfirmationNote] = useState('')
  const [simulatedConfirmed, setSimulatedConfirmed] = useState(false)
  const revision = useRef(0)
  const activeApplication = useRef(restored?.workflow.application_id)
  const skipSourceInvalidate = useRef(Boolean(restored?.workflow))
  const backendHydrated = useRef(Boolean(restored?.workflow) || getActiveScenario() !== 'live')
  const setReviewDraft = useCallback((id: string, text: string | null) => {
    revision.current += 1
    setReviewDrafts(values => {const next = {...values}; if (text === null) delete next[id]; else next[id] = text; return next})
  }, [])

  const applyBackendDraft = useCallback(async (opts?: { replaceForm?: boolean }) => {
    const res = await getApiClient().getWorkflowDraft()
    if (res.error || !res.data?.exists || !res.data.workflow) {
      if (res.error?.code === 'NETWORK_ERROR') {
        setWorkflowSourceNotice('无法连接后端，暂不能恢复本机工作流草稿。启动后端后刷新本页。')
      }
      return false
    }
    const draft = res.data
    let next = draft.workflow!
    let notice = draft.saved_at ? `已从本机后端恢复分析草稿（${new Date(draft.saved_at).toLocaleString()}）。` : '已从本机后端恢复分析草稿。'
    if (draft.stale) {
      next = invalidateRestoredWorkflow(next, draft.stale_reason || '岗位或经历源头已变化，请重新分析。')
      notice = draft.stale_reason || notice
    }
    skipSourceInvalidate.current = true
    setJdRawInput(draft.jd || next.parsed_jd.source_text || '')
    setActiveJobId(draft.active_job_id || next.target_job?.id || null)
    if (opts?.replaceForm !== false && draft.form) setResumeForm(draft.form)
    setReviewDrafts(draft.drafts ?? {})
    activeApplication.current = next.application_id
    setWorkflowState({
      ...next,
      review_session: next.review_session ?? { startedAt: Date.now(), actions: 0, interruptions: 0, choices: {} },
    })
    setClaimDecisions({})
    setFieldDecisions({})
    setSimulatedConfirmed(false)
    setConfirmationNote('')
    setRestoredAt(draft.saved_at || '')
    setWorkflowSourceNotice(notice)
    return true
  }, [])

  useEffect(() => {
    if (backendHydrated.current) return
    backendHydrated.current = true
    if (scenario !== 'live' || workflow) return
    void applyBackendDraft()
  }, [applyBackendDraft, scenario, workflow])

  useEffect(() => {
    let active = true
    const report = (message: string) => queueMicrotask(() => {if (active) setReviewStorageError(message)})
    try {
      saveReviewSession(workflow && scenario === 'live' ? {workflow, jd: jdRawInput, form: resumeForm, drafts: reviewDrafts} : null, sessionStorage)
      sessionStorage.setItem('applyguard.jd', jdRawInput)
      sessionStorage.setItem('applyguard.job', activeJobId ?? '')
      if (resumeForm?.dirty) sessionStorage.setItem('applyguard.resume-edit.v1', JSON.stringify(resumeForm))
      else sessionStorage.removeItem('applyguard.resume-edit.v1')
      report('')
    } catch { report('浏览器暂存失败，请保留此页面并导出已保存正文，刷新可能丢失进度。') }
    return () => {active = false}
  }, [workflow, jdRawInput, resumeForm, reviewDrafts, scenario, activeJobId])

  useEffect(() => {
    if (scenario !== 'live' || !workflow || workflow._prerecorded) return
    const analyzedJd = workflow.parsed_jd?.source_text?.trim()
    if (!analyzedJd) return
    const timer = window.setTimeout(() => {
      void getApiClient().saveWorkflowDraft({
        workflow,
        jd: analyzedJd,
        active_job_id: activeJobId,
        job_content_hash: workflow.target_job?.content_hash ?? null,
        resume_saved_at: resumeForm?.savedAt ?? null,
        form: resumeForm,
        drafts: reviewDrafts,
      }).then((res) => {
        if (res.error && res.error.code === 'NETWORK_ERROR') {
          setWorkflowSourceNotice('分析仍在本页，但未能写入后端草稿；请确认本地后端已启动。')
        }
      })
    }, 450)
    return () => window.clearTimeout(timer)
  }, [workflow, activeJobId, resumeForm, reviewDrafts, scenario])

  useEffect(() => {
    if (!Object.keys(reviewDrafts).length && !reviewStorageError && !resumeForm?.dirty) return
    const warn = (event: BeforeUnloadEvent) => {event.preventDefault(); event.returnValue = ''}
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [reviewDrafts, reviewStorageError, resumeForm?.dirty])

  const setWorkflow = useCallback((w: WorkflowResponse | null) => {
    revision.current += 1
    if (activeApplication.current !== w?.application_id || !w) setReviewDrafts({})
    activeApplication.current = w?.application_id
    setRestoredAt('')
    if (w) setWorkflowSourceNotice('')
    let startedAt=Date.now()
    try {const imported=Number(sessionStorage.getItem('applyguard.review.importStartedAt'));if (imported > 0 && imported <= startedAt) startedAt=imported} catch { /* optional local timing */ }
    setWorkflowState(w ? {...w,review_session:w.review_session ?? {startedAt,actions:0,interruptions:0,choices:{}}} : null)
    setClaimDecisions({})
    setFieldDecisions({})
    setSimulatedConfirmed(false)
    setConfirmationNote('')
  }, [])

  const patchWorkflow = useCallback(
    (patch: Partial<WorkflowResponse> | ((w: WorkflowResponse) => WorkflowResponse)) => {
      revision.current += 1
      setWorkflowState((prev) => {
        if (!prev) return prev
        const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
        return { ...next, requires_reverification: true }
      })
      setClaimDecisions({})
      setFieldDecisions({})
      setSimulatedConfirmed(false)
    },
    [],
  )

  const invalidateWorkflow = useCallback((reason = '岗位或经历材料有变动，请重新核验当前草稿。') => {
    revision.current += 1
    setWorkflowState(previous => previous ? invalidateRestoredWorkflow(previous, reason) : previous)
    setWorkflowSourceNotice(reason)
    setClaimDecisions({})
    setFieldDecisions({})
    setSimulatedConfirmed(false)
    setConfirmationNote('')
  }, [])

  const previousInput = useRef<string | null>(null)
  useEffect(() => {
    const { dirty: _dirty, savedAt: _savedAt, ...content } = resumeForm ?? {}
    const signature = JSON.stringify([jdRawInput, content])
    if (skipSourceInvalidate.current) {
      skipSourceInvalidate.current = false
      previousInput.current = signature
      return
    }
    if (previousInput.current !== null && previousInput.current !== signature) {
      invalidateWorkflow('岗位或经历源头已修改，已作废旧核验结果；证据匹配等页需重新分析后再继续。')
    }
    previousInput.current = signature
  }, [jdRawInput, resumeForm, invalidateWorkflow])

  useEffect(() => {
    const invalidate = () => invalidateWorkflow('证明材料或收藏岗位有变动，请重新分析后再继续。')
    const storage = (event: StorageEvent) => { if (event.key === 'applyguard.evidence.version') invalidate() }
    window.addEventListener('applyguard:evidence-changed', invalidate)
    window.addEventListener('applyguard:jobs-changed', invalidate)
    window.addEventListener('storage', storage)
    return () => { window.removeEventListener('applyguard:evidence-changed', invalidate); window.removeEventListener('applyguard:jobs-changed', invalidate); window.removeEventListener('storage', storage) }
  }, [invalidateWorkflow])

  const setScenario = useCallback(
    (s: DemoScenario) => {
      setScenarioInClient(s)
      setScenarioState(s)
      setStep('import')
      setJdRawInput('')
      setActiveJobId(null)
      setWorkflow(null)
      setResumeForm(null)
      setWorkflowSourceNotice('')
      if (s === 'live') {
        backendHydrated.current = true
        void applyBackendDraft({ replaceForm: true })
      }
    },
    [setWorkflow, applyBackendDraft],
  )

  const resetFlow = useCallback(() => {
    setScenario(scenario)
  }, [scenario, setScenario])

  const setClaimDecision = useCallback(
    (claimId: string, patch: Partial<LocalClaimDecision>) => {
      revision.current += 1
      setClaimDecisions((prev) => {
        const current = prev[claimId] ?? {
          claim_id: claimId,
          decision: null,
          freshness: 'as_returned' as const,
        }
        const next = { ...current, ...patch, claim_id: claimId }
        if (patch.editedText != null || patch.decision === 'edit') {
          next.freshness = 'edited_pending_reverify'
        }
        if (patch.decision === 'reject') {
          next.freshness = 'rejected'
        }
        return { ...prev, [claimId]: next }
      })
    },
    [],
  )

  const setFieldDecision = useCallback(
    (fieldId: string, patch: Partial<LocalFieldDecision>) => {
      revision.current += 1
      setFieldDecisions((prev) => {
        const current = prev[fieldId] ?? {
          field_id: fieldId,
          confirmed: false,
          acknowledgedBlocked: false,
        }
        return { ...prev, [fieldId]: { ...current, ...patch, field_id: fieldId } }
      })
    },
    [],
  )

  const verificationOf = useCallback(
    (claimId: string) => workflow?.claim_verification.find((v) => v.claim_id === claimId)?.state,
    [workflow],
  )

  const canProceedFromClaims = useCallback(() => {
    if (Object.keys(reviewDrafts).length || !workflow?.claim_verification.length || workflow.requires_reverification) return false
    for (const v of workflow.claim_verification) {
      const d = claimDecisions[v.claim_id]
      const claim = workflow.resume_claims.find((item) => item.claim_id === v.claim_id)
      const personal = workflow.grounding?.results[v.claim_id]?.verification_scope === 'personal'
      if (d?.decision === 'edit' || d?.freshness === 'edited_pending_reverify') return false
      if (d?.decision === 'reject' || d?.freshness === 'rejected') continue

      // 辅助确认：已知悉可能不匹配，仍可继续；不把缺证据标成“已核验通过”。
      if (d?.decision === 'confirm' && (v.state === 'BLOCKED' || v.state === 'NEEDS_REVIEW')) continue

      if (v.state === 'BLOCKED' || v.state === 'NEEDS_REVIEW') return false

      if (v.state === 'VERIFIED') {
        if (workflow.grounding) {
          const report = workflow.grounding
          const result = report.results[v.claim_id]
          const groundedOk = report.mode === 'sag_atomic'
            && (!report.error || personal)
            && result?.state === 'VERIFIED'
            && result.final_text === claim?.text
          if (!groundedOk) return false
        }
        if (!personal && !claim?.evidence_ids.length) return false
        if (!personal && claim?.evidence_ids.some((id) => id.startsWith('ev_draft_'))) return false
        continue
      }
      return false
    }
    const hasPassable = workflow.claim_verification.some((v) => {
      const d = claimDecisions[v.claim_id]
      if (d?.decision === 'reject' || d?.freshness === 'rejected') return false
      if (d?.freshness === 'edited_pending_reverify') return false
      return v.state === 'VERIFIED'
        || ((v.state === 'NEEDS_REVIEW' || v.state === 'BLOCKED') && d?.decision === 'confirm')
    })
    const onlyBlockedHandled =
      workflow.claim_verification.length > 0 &&
      workflow.claim_verification.every((v) => {
        if (v.state !== 'BLOCKED') return false
        const d = claimDecisions[v.claim_id]
        return d?.decision === 'reject' || d?.decision === 'confirm' || d?.freshness === 'rejected'
      })
    return hasPassable || onlyBlockedHandled
  }, [workflow, claimDecisions, reviewDrafts])
  const atsFieldAcksComplete = useCallback(() => {
    if (!workflow) return false
    const controls = workflow.field_controls ?? []
    for (const control of controls) {
      const d = fieldDecisions[control.field_id]
      if (control.action === 'BLOCKED') {
        if (!d?.acknowledgedBlocked) return false
        if (d.confirmed) return false
        continue
      }
      if (control.level === 'L3' || control.level === 'L2' || control.action === 'REQUIRES_CONFIRMATION') {
        if (!d?.confirmed) return false
      }
    }
    return true
  }, [workflow, fieldDecisions])

  const canSubmitAts = useCallback(() => {
    if (!workflow || workflow.requires_reverification || !canProceedFromClaims()) return false
    if (workflow.workflow_status === 'BLOCKED') return false
    if (workflow.risk_result.action === 'BLOCKED') return false
    if (!workflow.human_confirmation.allowed_actions.includes('CONFIRM')) return false
    return atsFieldAcksComplete()
  }, [workflow, atsFieldAcksComplete, canProceedFromClaims])

  const reverifyClaims = useCallback(async () => {
    if (Object.keys(reviewDrafts).length) return '审核页仍有暂存修改，请返回保存或取消后再核验。'
    if (!workflow) return '请先运行工作流。'
    if (!workflow._prerecorded && (workflow.parsed_jd.source_text.trim() !== jdRawInput.trim() ||
        (workflow.target_job?.id ?? null) !== activeJobId)) return '岗位或关联已改变，请先在岗位说明重新分析。'
    const version = revision.current
    const claims = workflow.resume_claims
      .filter((claim) => claimDecisions[claim.claim_id]?.decision !== 'reject')
      .map((claim) => ({claim_id: claim.claim_id, text: claimDecisions[claim.claim_id]?.editedText ?? claim.text}))
    const res = await getApiClient().reverifyWorkflow(workflow, claims, workflow._prerecorded ? null : resumeForm)
    if (version !== revision.current) return '输入已改变，请重新核验最新内容。'
    if (res.error || !res.data) return res.error?.message ?? '重新核验失败'
    setWorkflow({...workflow, ...res.data})
    return null
  }, [workflow, claimDecisions, resumeForm, setWorkflow, reviewDrafts, jdRawInput, activeJobId])

  const validateExport = useCallback(async () => {
    if (!workflow || !canSubmitAts() || (!workflow._prerecorded && (
        workflow.parsed_jd.source_text.trim() !== jdRawInput.trim() || (workflow.target_job?.id ?? null) !== activeJobId))) return false
    const version = revision.current
    const claims = workflow.resume_claims.filter((claim) => claimDecisions[claim.claim_id]?.decision !== 'reject')
      .map((claim) => ({claim_id: claim.claim_id, text: claim.text}))
    const res = await getApiClient().reverifyWorkflow(workflow, claims, workflow._prerecorded ? null : resumeForm)
    if (version !== revision.current || res.error || !res.data) return false
    const next = res.data
    const signature = (value: Partial<WorkflowResponse>) => JSON.stringify([
      value.resume_claims?.map((c) => [c.claim_id, c.text, c.evidence_ids]),
      value.claim_verification?.map((v) => [v.claim_id, v.state]),
      value.ats_form_mapping?.fields, value.field_controls,
    ])
    if (next.workflow_status === 'BLOCKED' || signature(next) !== signature(workflow)) {
      setWorkflow({...workflow, ...next})
      return false
    }
    return true
  }, [workflow, claimDecisions, resumeForm, canSubmitAts, setWorkflow, jdRawInput, activeJobId])

  const dataSourceLabel = sourceLabel(scenario, workflow)

  const value = useMemo(
    () => ({
      scenario,
      reviewDrafts, setReviewDraft, reviewStorageError, restoredAt,
      step,
      jdRawInput, activeJobId, invalidateWorkflow,
      workflow,
      workflowSourceNotice,
      resumeForm,
      dataSourceLabel,
      claimDecisions,
      fieldDecisions,
      confirmationNote,
      simulatedConfirmed,
      setScenario,
      setStep,
      setJdRawInput, setActiveJobId,
      setWorkflow,
      patchWorkflow,
      reverifyClaims,
      validateExport,
      setResumeForm,
      setClaimDecision,
      setFieldDecision,
      setConfirmationNote,
      setSimulatedConfirmed,
      resetFlow,
      verificationOf,
      canProceedFromClaims,
      atsFieldAcksComplete,
      canSubmitAts,
    }),
    [
      scenario,
      reviewDrafts, setReviewDraft, reviewStorageError, restoredAt,
      step,
      jdRawInput, activeJobId, invalidateWorkflow,
      workflow,
      workflowSourceNotice,
      resumeForm,
      dataSourceLabel,
      claimDecisions,
      fieldDecisions,
      confirmationNote,
      simulatedConfirmed,
      setScenario,
      setWorkflow,
      patchWorkflow,
      reverifyClaims,
      validateExport,
      setClaimDecision,
      setFieldDecision,
      resetFlow,
      verificationOf,
      canProceedFromClaims,
      atsFieldAcksComplete,
      canSubmitAts,
    ],
  )

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>
}

export function useDemo(): DemoState {
  const ctx = useContext(DemoContext)
  if (!ctx) throw new Error('useDemo must be used within DemoProvider')
  return ctx
}
