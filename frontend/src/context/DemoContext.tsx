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
  SAMPLE_JD,
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

interface DemoState {
  scenario: DemoScenario
  step: FlowStep
  jdRawInput: string
  workflow: WorkflowResponse | null
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
  const [scenario, setScenarioState] = useState<DemoScenario>(getActiveScenario())
  const [step, setStep] = useState<FlowStep>('import')
  const [jdRawInput, setJdRawInput] = useState(SAMPLE_JD)
  const [workflow, setWorkflowState] = useState<WorkflowResponse | null>(null)
  const [resumeForm, setResumeForm] = useState<EditableResumeForm | null>(null)
  const [claimDecisions, setClaimDecisions] = useState<Record<string, LocalClaimDecision>>({})
  const [fieldDecisions, setFieldDecisions] = useState<Record<string, LocalFieldDecision>>({})
  const [confirmationNote, setConfirmationNote] = useState('')
  const [simulatedConfirmed, setSimulatedConfirmed] = useState(false)
  const revision = useRef(0)

  const setWorkflow = useCallback((w: WorkflowResponse | null) => {
    revision.current += 1
    setWorkflowState(w)
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

  const previousInput = useRef<string | null>(null)
  useEffect(() => {
    const { dirty: _dirty, savedAt: _savedAt, ...content } = resumeForm ?? {}
    const signature = JSON.stringify([jdRawInput, content])
    if (previousInput.current !== null && previousInput.current !== signature) setWorkflow(null)
    previousInput.current = signature
  }, [jdRawInput, resumeForm, setWorkflow])

  useEffect(() => {
    const invalidate = () => setWorkflow(null)
    const storage = (event: StorageEvent) => { if (event.key === 'applyguard.evidence.version') invalidate() }
    window.addEventListener('applyguard:evidence-changed', invalidate)
    window.addEventListener('storage', storage)
    return () => { window.removeEventListener('applyguard:evidence-changed', invalidate); window.removeEventListener('storage', storage) }
  }, [setWorkflow])

  const setScenario = useCallback(
    (s: DemoScenario) => {
      setScenarioInClient(s)
      setScenarioState(s)
      setStep('import')
      setJdRawInput(SAMPLE_JD)
      setWorkflow(null)
      setResumeForm(null)
    },
    [setWorkflow],
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
    if (!workflow?.claim_verification.length || workflow.requires_reverification) return false
    for (const v of workflow.claim_verification) {
      const d = claimDecisions[v.claim_id]
      if (v.state === 'BLOCKED') {
        // Cannot confirm-around BLOCKED; must reject/exclude
        if (d?.decision === 'confirm') return false
        if (d?.decision !== 'reject') return false
      }
      const claim = workflow.resume_claims.find((item) => item.claim_id === v.claim_id)
      if ((!claim?.evidence_ids.length || claim.evidence_ids.some((id) => id.startsWith('ev_draft_'))) && d?.decision !== 'reject') return false
      if (v.state === 'NEEDS_REVIEW') {
        if (!d?.decision) return false
        if (d.decision === 'edit' || d.freshness === 'edited_pending_reverify') {
          // Edited → pending re-verify; cannot treat as passed
          return false
        }
      }
      if (d?.freshness === 'edited_pending_reverify') return false
    }
    const hasPassable = workflow.claim_verification.some((v) => {
      const d = claimDecisions[v.claim_id]
      if (d?.decision === 'reject' || d?.freshness === 'rejected') return false
      if (d?.freshness === 'edited_pending_reverify') return false
      return v.state === 'VERIFIED' || (v.state === 'NEEDS_REVIEW' && d?.decision === 'confirm')
    })
    // All-BLOCKED demo: after every BLOCKED is rejected, allow ATS inspection
    const onlyBlocked =
      workflow.claim_verification.length > 0 &&
      workflow.claim_verification.every((v) => v.state === 'BLOCKED')
    return hasPassable || onlyBlocked
  }, [workflow, claimDecisions])
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
    if (!workflow) return '请先运行工作流。'
    const version = revision.current
    const claims = workflow.resume_claims
      .filter((claim) => claimDecisions[claim.claim_id]?.decision !== 'reject')
      .map((claim) => ({claim_id: claim.claim_id, text: claimDecisions[claim.claim_id]?.editedText ?? claim.text}))
    const res = await getApiClient().reverifyWorkflow(workflow, claims, workflow._prerecorded ? null : resumeForm)
    if (version !== revision.current) return '输入已改变，请重新核验最新内容。'
    if (res.error || !res.data) return res.error?.message ?? '重新核验失败'
    setWorkflow({...workflow, ...res.data})
    return null
  }, [workflow, claimDecisions, resumeForm, setWorkflow])

  const validateExport = useCallback(async () => {
    if (!workflow || !canSubmitAts()) return false
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
  }, [workflow, claimDecisions, resumeForm, canSubmitAts, setWorkflow])

  const dataSourceLabel = sourceLabel(scenario, workflow)

  const value = useMemo(
    () => ({
      scenario,
      step,
      jdRawInput,
      workflow,
      resumeForm,
      dataSourceLabel,
      claimDecisions,
      fieldDecisions,
      confirmationNote,
      simulatedConfirmed,
      setScenario,
      setStep,
      setJdRawInput,
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
      step,
      jdRawInput,
      workflow,
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
