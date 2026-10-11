import type {
  ApiResult,
  CareerVaultSeed,
  DemoScenario,
  EditableResumeForm,
  ResumeParseResult,
  WorkflowResponse,
} from './types'

const DEFAULT_CANDIDATE = 'cand_demo_001'
const MIN_JD_LEN = 20

export const SAMPLE_JD =
  '后端开发实习生。岗位职责：使用 Python 编写接口服务、补充自动化测试，并使用版本协作。加分项：有数据处理相关项目经验。'

let activeScenario: DemoScenario = 'live'

export function getActiveScenario(): DemoScenario {
  return activeScenario
}

export function setActiveScenario(scenario: DemoScenario): void {
  activeScenario = scenario
}

function apiBase(): string {
  // Vite dev proxy uses '' → /api and /health; override with VITE_API_BASE if needed
  return (import.meta.env.VITE_API_BASE as string | undefined) ?? ''
}

async function readJson(res: Response): Promise<unknown> {
  const text = await res.text()
  try {
    return text ? JSON.parse(text) : {}
  } catch {
    return { error: { code: 'INVALID_JSON', message: text || 'Non-JSON response' } }
  }
}

function toApiError(payload: unknown, httpStatus: number): ApiResult<never>['error'] {
  const err = (payload as { error?: { code?: string; message?: string; details?: unknown[]; trace_id?: string } })
    ?.error
  const message =
    err?.message ||
    (httpStatus === 0
      ? '无法连接后端。请确认已在隔离环境安装依赖并运行 python -m backend.app（127.0.0.1:8000）。'
      : `请求失败（HTTP ${httpStatus}）`)
  const code = err?.code || (httpStatus === 0 ? 'NETWORK_ERROR' : `HTTP_${httpStatus}`)
  const retryable =
    httpStatus === 0 || httpStatus >= 500 || code === 'NETWORK_ERROR' || code === 'INTERNAL_ERROR'
  return {
    code,
    message,
    details: err?.details,
    trace_id: err?.trace_id,
    retryable,
  }
}

export type WorkflowParseMode = 'offline' | 'dynamic'

export interface ApiClient {
  getHealth(): Promise<ApiResult<{ status: string; service: string; version: string }>>
  getCareerVault(): Promise<ApiResult<CareerVaultSeed>>
  parseResumePdf(file: File): Promise<ApiResult<ResumeParseResult>>
  getResumeDraft(): Promise<ApiResult<EditableResumeForm>>
  saveResumeDraft(form: EditableResumeForm): Promise<ApiResult<{ saved: boolean; saved_at?: string; notice?: string }>>
  runWorkflow(
    jdText: string,
    options?: { parseMode?: WorkflowParseMode },
  ): Promise<ApiResult<WorkflowResponse>>
}

export class ApplyGuardApiClient implements ApiClient {
  async getHealth(): Promise<ApiResult<{ status: string; service: string; version: string }>> {
    try {
      const res = await fetch(`${apiBase()}/health`)
      const body = await readJson(res)
      if (!res.ok) return { error: toApiError(body, res.status) }
      return { data: body as { status: string; service: string; version: string } }
    } catch {
      return { error: toApiError(null, 0) }
    }
  }

  async getCareerVault(): Promise<ApiResult<CareerVaultSeed>> {
    try {
      // Same fictional seed as backend data/career-vault.seed.json (no vault HTTP API yet)
      const res = await fetch(`${import.meta.env.BASE_URL}data/career-vault.seed.json`)
      if (!res.ok) {
        return {
          error: {
            code: 'VAULT_LOAD_FAILED',
            message: '无法加载经历库种子数据。',
            retryable: true,
          },
        }
      }
      const data = (await res.json()) as CareerVaultSeed
      if (!data.experiences?.length) return { empty: true, data }
      return { data }
    } catch {
      return {
        error: {
          code: 'VAULT_LOAD_FAILED',
          message: '经历库种子加载失败。',
          retryable: true,
        },
      }
    }
  }

  async parseResumePdf(file: File): Promise<ApiResult<ResumeParseResult>> {
    if (file.size > 5 * 1024 * 1024) {
      return {
        error: { code: 'VALIDATION_ERROR', message: 'PDF 不能超过 5MB。', retryable: false },
      }
    }
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      return {
        error: { code: 'VALIDATION_ERROR', message: '请上传 .pdf 文件。', retryable: false },
      }
    }
    try {
      const pdf_base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => {
          const raw = String(reader.result ?? '')
          const comma = raw.indexOf(',')
          resolve(comma >= 0 ? raw.slice(comma + 1) : raw)
        }
        reader.onerror = () => reject(reader.error ?? new Error('read failed'))
        reader.readAsDataURL(file)
      })
      const res = await fetch(`${apiBase()}/api/v1/resume/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, pdf_base64 }),
      })
      const body = await readJson(res)
      if (!res.ok) return { error: toApiError(body, res.status) }
      return { data: body as ResumeParseResult }
    } catch {
      return { error: toApiError(null, 0) }
    }
  }

  async getResumeDraft(): Promise<ApiResult<EditableResumeForm>> {
    try {
      const res = await fetch(`${apiBase()}/api/v1/resume/draft`)
      const body = await readJson(res)
      if (!res.ok) return { error: toApiError(body, res.status) }
      const payload = body as { exists?: boolean; form?: EditableResumeForm | null }
      if (!payload.exists || !payload.form) return { empty: true }
      return { data: payload.form }
    } catch {
      return { error: toApiError(null, 0) }
    }
  }

  async saveResumeDraft(
    form: EditableResumeForm,
  ): Promise<ApiResult<{ saved: boolean; saved_at?: string; notice?: string }>> {
    try {
      const res = await fetch(`${apiBase()}/api/v1/resume/draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const body = await readJson(res)
      if (!res.ok) return { error: toApiError(body, res.status) }
      return { data: body as { saved: boolean; saved_at?: string; notice?: string } }
    } catch {
      return { error: toApiError(null, 0) }
    }
  }

  async runWorkflow(
    jdText: string,
    options?: { parseMode?: WorkflowParseMode },
  ): Promise<ApiResult<WorkflowResponse>> {
    const scenario = activeScenario
    const parseMode: WorkflowParseMode = options?.parseMode ?? 'offline'

    if (scenario === 'error') {
      return {
        error: {
          code: 'DEMO_BACKEND_UNAVAILABLE',
          message:
            '错误演示场景：模拟后端未启动或网络失败。可重试，或切换到「正常·在线」场景并确保后端已运行。',
          retryable: true,
        },
      }
    }

    if (scenario === 'prerecorded_block' || scenario === 'prerecorded_fallback') {
      const file =
        scenario === 'prerecorded_block'
          ? 'prerecorded/unsupported_block.json'
          : 'prerecorded/timeout_fallback.json'
      try {
        const res = await fetch(`${import.meta.env.BASE_URL}${file}`)
        if (!res.ok) {
          return {
            error: {
              code: 'PRERECORD_MISSING',
              message: `预录演示数据缺失：${file}`,
              retryable: true,
            },
          }
        }
        const data = (await res.json()) as WorkflowResponse
        data._prerecorded = {
          case: scenario === 'prerecorded_block' ? 'unsupported_block' : 'timeout_fallback',
          notice:
            '预录演示数据：由 python -m demo.run_c_cases 离线生成，非本次 Live API 响应。用于展示 BLOCKED / 模型超时 Fallback。',
        }
        return { data }
      } catch {
        return {
          error: {
            code: 'PRERECORD_LOAD_FAILED',
            message: '预录演示数据加载失败。',
            retryable: true,
          },
        }
      }
    }

    // live: real backend; default offline (zero provider calls). dynamic uses backend env key.
    const trimmed = jdText.trim()
    if (!trimmed) {
      return {
        empty: true,
        error: {
          code: 'EMPTY_JD',
          message: '岗位说明为空。请粘贴至少 20 个字符的岗位说明后再运行工作流。',
          retryable: false,
        },
      }
    }
    if (trimmed.length < MIN_JD_LEN) {
      return {
        error: {
          code: 'VALIDATION_ERROR',
          message: `岗位说明至少需要 ${MIN_JD_LEN} 个字符。当前 ${trimmed.length}。`,
          retryable: false,
        },
      }
    }

    try {
      const res = await fetch(`${apiBase()}/api/v1/workflow/mock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: DEFAULT_CANDIDATE,
          jd_text: trimmed,
          parse_mode: parseMode,
          application_id: 'app_demo_001',
        }),
      })
      const body = await readJson(res)
      if (!res.ok) {
        return { error: toApiError(body, res.status) }
      }
      return { data: body as WorkflowResponse }
    } catch {
      return { error: toApiError(null, 0) }
    }
  }
}

let client: ApiClient = new ApplyGuardApiClient()

export function getApiClient(): ApiClient {
  return client
}

export function setApiClient(next: ApiClient): void {
  client = next
}

export { DEFAULT_CANDIDATE }
