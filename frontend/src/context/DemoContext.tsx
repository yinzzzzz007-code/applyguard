import {
  createContext,
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
    return '在线 · 离线规则'
  }
  if (scenario === 'error') return '错误演示（无成功响应）'
  return '尚未运行工作流'
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [scenario, setScenarioState] = useState<DemoScenario>(getActiveScenario())
  const [step, setStep] = useState<FlowStep>('vault')
  const [jdRawInput, setJdRawInput] = useState(SAMPLE_JD)
  const [workflow, setWorkflowState] = useState<WorkflowResponse | null>(null)
  const [resumeForm, setResumeForm] = useState<EditableResumeForm | null>(null)
  const [claimDecisions, setClaimDecisions] = useState<Record<string, LocalClaimDecision>>({})
  const [fieldDecisions, setFieldDecisions] = useState<Record<string, LocalFieldDecision>>({})
  const [confirmationNote, setConfirmationNote] = useState('')
  const [simulatedConfirmed, setSimulatedConfirmed] = useState(false)

  const setWorkflow = useCallback((w: WorkflowResponse | null) => {
    setWorkflowState(w)
    setClaimDecisions({})
    setFieldDecisions({})
    setSimulatedConfirmed(false)
    setConfirmationNote('')
  }, [])

  const patchWorkflow = useCallback(
    (patch: Partial<WorkflowResponse> | ((w: WorkflowResponse) => WorkflowResponse)) => {
      setWorkflowState((prev) => {
        if (!prev) return prev
        return typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
      })
    },
    [],
  )

  const setScenario = useCallback(
    (s: DemoScenario) => {
      setScenarioInClient(s)
      setScenarioState(s)
      setStep('vault')
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
    if (!workflow?.claim_verification.length) return false
    for (const v of workflow.claim_verification) {
      const d = claimDecisions[v.claim_id]
      if (v.state === 'BLOCKED') {
        // Cannot confirm-around BLOCKED; must reject/exclude
        if (d?.decision === 'confirm') return false
        if (d?.decision !== 'reject') return false
      }
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
    if (!workflow) return false
    if (workflow.workflow_status === 'BLOCKED') return false
    if (workflow.risk_result.action === 'BLOCKED') return false
    if (!workflow.human_confirmation.allowed_actions.includes('CONFIRM')) return false
    return atsFieldAcksComplete()
  }, [workflow, atsFieldAcksComplete])

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
