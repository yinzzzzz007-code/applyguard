import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fileToBase64, getApiClient } from '../api/client'
import type {
  AwardEvidenceFields,
  CareerVaultSeed,
  EditableResumeForm,
  EvidenceRecord,
  EvidenceSourceFile,
  EvidenceSpan,
  EvidenceWorkspace,
  ResumeMatchItem,
  ResumeMatchReport,
} from '../api/types'
import { EvidenceMaterialLibrary } from '../components/EvidenceMaterialLibrary'
import { materialName, orderedEvidenceSpans } from '../evidence/materials'
import { EvidenceMatchBoard } from '../components/EvidenceMatchBoard'
import { useDemo } from '../context/DemoContext'
import {
  buildResumeFormFromVault,
  newExperienceId,
  normalizeResumeForm,
  syncAwardText,
} from '../resume/formModel'

const ALLOWED = new Set([
  '.jpg',
  '.jpeg',
  '.png',
  '.webp',
  '.gif',
  '.pdf',
  '.doc',
  '.docx',
  '.md',
  '.markdown',
  '.ocr.json',
])

function extOf(name: string): string {
  const lower = name.toLowerCase()
  if (lower.endsWith('.ocr.json')) return '.ocr.json'
  const i = lower.lastIndexOf('.')
  return i >= 0 ? lower.slice(i) : ''
}

function isAllowed(name: string): boolean {
  return ALLOWED.has(extOf(name))
}

function alreadyRecognized(f: EvidenceSourceFile): boolean {
  if (f.state === 'FAILED' || f.state === 'PARSING' || f.state === 'PENDING') return false
  if (f.recognition_saved) return true
  if ((f.span_count ?? 0) > 0) return true
  return f.state === 'INDEXED' || f.state === 'NEEDS_REVIEW'
}

/** Skip dotfiles and any path under a `.`-prefixed (hidden) folder. */
function isHiddenPath(relativePath: string): boolean {
  return relativePath
    .replace(/\\/g, '/')
    .split('/')
    .some((part) => part.startsWith('.') && part !== '.' && part !== '..')
}

type PendingFile = { relative_path: string; file: File; unsupported?: boolean }

async function collectFromDirectoryHandle(
  handle: FileSystemDirectoryHandle,
  prefix = '',
): Promise<PendingFile[]> {
  const out: PendingFile[] = []
  // for-await over directory entries
  for await (const [name, entry] of (handle as unknown as {
    entries: () => AsyncIterableIterator<[string, FileSystemHandle]>
  }).entries()) {
    // Do not descend into hidden folders (.git, .venv, .cursor, …)
    if (name.startsWith('.')) continue
    const rel = prefix ? `${prefix}/${name}` : name
    if (entry.kind === 'directory') {
      out.push(...(await collectFromDirectoryHandle(entry as FileSystemDirectoryHandle, rel)))
    } else if (entry.kind === 'file') {
      if (isHiddenPath(rel)) continue
      const file = await (entry as FileSystemFileHandle).getFile()
      out.push({ relative_path: rel.replace(/\\/g, '/'), file, unsupported: !isAllowed(rel) })
    }
  }
  return out
}

const matchKey = (row: ResumeMatchItem) => `${row.target_type}:${row.target_id}`

const WS_STORAGE_KEY = 'applyguard.evidence.workspaceId'
const MATCH_STORAGE_PREFIX = 'applyguard.evidence.matchReport.'

function loadStoredWorkspaceId(): string {
  try {
    return localStorage.getItem(WS_STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function saveStoredWorkspaceId(id: string) {
  try {
    if (id) localStorage.setItem(WS_STORAGE_KEY, id)
    else localStorage.removeItem(WS_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

function loadStoredMatch(wsId: string): ResumeMatchReport | null {
  if (!wsId) return null
  try {
    const raw = localStorage.getItem(MATCH_STORAGE_PREFIX + wsId)
    return raw ? (JSON.parse(raw) as ResumeMatchReport) : null
  } catch {
    return null
  }
}

function saveStoredMatch(wsId: string, report: ResumeMatchReport | null) {
  if (!wsId) return
  try {
    if (report) localStorage.setItem(MATCH_STORAGE_PREFIX + wsId, JSON.stringify(report))
    else localStorage.removeItem(MATCH_STORAGE_PREFIX + wsId)
  } catch {
    /* ignore */
  }
}

function PreviewPane({
  file,
  spans,
  highlightText,
}: {
  file: EvidenceSourceFile
  spans: EvidenceSpan[]
  highlightText?: string
}) {
  const api = getApiClient()
  const url = api.evidencePreviewUrl(file.file_id)
  const isImage = (file.media_type || '').startsWith('image/')
  const hit = highlightText
    ? spans.find((s) => s.raw_text.includes(highlightText))
    : spans.find((s) => /二等奖|一等奖|三等奖/.test(s.raw_text))

  if (isImage) {
    return (
      <div className="evidence-preview-frame">
        <div className="evidence-preview-image-wrap">
          <img src={url} alt={file.relative_path} className="evidence-preview-image" />
          {hit?.bbox && hit.bbox.length === 4 ? (
            <div
              className="evidence-bbox"
              style={{
                left: `${hit.bbox[0] * 100}%`,
                top: `${hit.bbox[1] * 100}%`,
                width: `${(hit.bbox[2] - hit.bbox[0]) * 100}%`,
                height: `${(hit.bbox[3] - hit.bbox[1]) * 100}%`,
              }}
              title={hit.raw_text}
            />
          ) : null}
        </div>
        {file.conversion_note ? <p className="muted">{file.conversion_note}</p> : null}
      </div>
    )
  }

  if (file.media_type === 'application/pdf' || file.relative_path.toLowerCase().endsWith('.pdf')) {
    return (
      <div className="evidence-preview-frame">
        <iframe title={file.relative_path} src={url} className="evidence-preview-iframe" />
        {file.conversion_note ? <p className="warn-text">{file.conversion_note}</p> : null}
        {hit ? (
          <p className="muted">
            定位：第 {hit.page ?? '?'} 页 · {hit.raw_text.slice(0, 80)}
          </p>
        ) : null}
      </div>
    )
  }

  return (
    <div className="evidence-preview-frame">
      <pre className="evidence-text-preview">
        {spans.map((s) => (
          <span
            key={s.span_id}
            className={
              highlightText && s.raw_text.includes(highlightText) ? 'evidence-line-hit' : undefined
            }
          >
            {s.line_start != null ? `${s.line_start}| ` : ''}
            {s.raw_text}
            {'\n'}
          </span>
        ))}
      </pre>
      <p className="muted">
        <a href={url} target="_blank" rel="noreferrer">
          下载原件
        </a>
        {file.conversion_note ? ` · ${file.conversion_note}` : ''}
      </p>
    </div>
  )
}

export function EvidenceWorkspacePage() {
  const api = getApiClient()
  const { resumeForm, setResumeForm } = useDemo()
  const [params] = useSearchParams()
  const linkTargetType = params.get('target_type') || 'award'
  const linkTargetId = params.get('target_id') || ''
  const openEvidenceId = params.get('evidence_id') || ''
  const supplementInputRef = useRef<HTMLInputElement | null>(null)
  const [supplementTarget, setSupplementTarget] = useState<ResumeMatchItem | null>(null)
  const [addKind, setAddKind] = useState<'internship' | 'project' | 'award'>('award')
  const [addLabel, setAddLabel] = useState('')
  const [addOrg, setAddOrg] = useState('')

  const [workspaces, setWorkspaces] = useState<EvidenceWorkspace[]>([])
  const [workspaceId, setWorkspaceId] = useState(() => loadStoredWorkspaceId())
  const [pending, setPending] = useState<PendingFile[]>([])
  const [files, setFiles] = useState<EvidenceSourceFile[]>([])
  const [evidenceList, setEvidenceList] = useState<EvidenceRecord[]>([])
  const [selectedEvidenceId, setSelectedEvidenceId] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewContext, setPreviewContext] = useState<'match' | 'library'>('match')
  const [libraryFileId, setLibraryFileId] = useState('')
  const [detailRevision, setDetailRevision] = useState(0)
  const directoryInputRef = useRef<HTMLInputElement | null>(null)
  const uploadInputRef = useRef<HTMLInputElement | null>(null)
  const [selectedMatchKey, setSelectedMatchKey] = useState(() => linkTargetId ? `${linkTargetType}:${linkTargetId}` : '')
  const [previewError, setPreviewError] = useState('')
  const [detail, setDetail] = useState<EvidenceRecord | null>(null)
  const [fields, setFields] = useState<AwardEvidenceFields>({})
  const [draftSavedAt, setDraftSavedAt] = useState('')
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [importProgress, setImportProgress] = useState<{
    phase: 'read' | 'upload' | 'refresh'
    current: number
    total: number
    label: string
  } | null>(null)
  const [matchReport, setMatchReport] = useState<ResumeMatchReport | null>(null)
  const autoMatchedForDraft = useRef('')
  const fieldsSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activeEvidenceRef = useRef('')
  const pendingFieldDraft = useRef<{ id: string; fields: AwardEvidenceFields; workspace: string } | null>(null)
  const fieldSaveQueue = useRef<Promise<boolean>>(Promise.resolve(true))
  const [fieldSaveError, setFieldSaveError] = useState('')
  const [vaultSeed, setVaultSeed] = useState<CareerVaultSeed | null>(null)
  const [vaultSourceHint, setVaultSourceHint] = useState('')
  const [claimProbe, setClaimProbe] = useState('')
  const [claimResult, setClaimResult] = useState('')
  const [skipAlreadyRecognized, setSkipAlreadyRecognized] = useState(true)

  // 经历库是唯一出发源：已保存草稿优先；勿用「脏种子稿」盖住磁盘草稿。
  useEffect(() => {
    let cancelled = false
    void (async () => {
      const [vaultRes, draftRes] = await Promise.all([
        api.getCareerVault(),
        api.getResumeDraft(),
      ])
      if (cancelled) return
      const seed = vaultRes.data ?? null
      setVaultSeed(seed)

      let hint = ''
      setResumeForm((prev) => {
        // Only keep memory edits if user already had a saved vault and is mid-edit
        if (prev?.dirty && prev.savedAt && prev.candidateId) {
          hint = '经历库未保存编辑'
          return normalizeResumeForm(prev)
        }
        if (draftRes.data) {
          hint = '本机已保存的经历库草稿'
          const fromDisk = normalizeResumeForm(draftRes.data)
          return { ...fromDisk, dirty: false }
        }
        if (prev?.savedAt && prev.candidateId) {
          hint = '经历库当前编辑稿'
          return normalizeResumeForm(prev)
        }
        try {
          const raw = sessionStorage.getItem('applyguard.resumeForm')
          if (raw) {
            const parsed = JSON.parse(raw) as EditableResumeForm
            if (parsed.candidateId && parsed.savedAt) {
              hint = '浏览器会话中的经历库'
              return normalizeResumeForm({ ...parsed, dirty: false })
            }
          }
        } catch {
          /* ignore */
        }
        if (seed) {
          hint = '种子数据（请先到经历库填写并保存）'
          return { ...buildResumeFormFromVault(seed), dirty: true, savedAt: undefined }
        }
        hint = ''
        return prev
      })
      if (!cancelled) {
        setVaultSourceHint(hint)
        // Drop stale match cache from older seed runs
        setMatchReport(null)
        autoMatchedForDraft.current = ''
        const ws = loadStoredWorkspaceId()
        if (ws) saveStoredMatch(ws, null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [api, setResumeForm])

  const vaultPayload = useMemo(() => {
    // Always prefer the filled 经历库 form once loaded — never silently mix with seed.
    if (resumeForm) {
      return {
        awards: (resumeForm.awards ?? [])
          .filter((a) => a.name.trim())
          .map((a) => ({
            award_id: a.id,
            name: a.name,
            issuer: a.issuer,
            date: a.date,
            description: a.description,
          })),
        internships: (resumeForm.internships ?? [])
          .filter((e) => e.organization.trim() || e.title.trim())
          .map((e) => ({
            id: e.id,
            organization: e.organization,
            title: e.title,
            role: e.role,
            description: e.description,
            start: e.start,
            end: e.end,
          })),
        projects: (resumeForm.projects ?? [])
          .filter((e) => e.organization.trim() || e.title.trim())
          .map((e) => ({
            id: e.id,
            organization: e.organization,
            title: e.title,
            role: e.role,
            description: e.description,
            start: e.start,
            end: e.end,
          })),
        source: (resumeForm.savedAt || !resumeForm.dirty ? 'draft' : 'editing') as
          | 'draft'
          | 'editing'
          | 'seed',
      }
    }

    const seedInternships = (vaultSeed?.experiences ?? [])
      .filter((e) => e.experience_id === 'exp_ml_evaluation')
      .map((e) => ({
        id: e.experience_id,
        organization: e.organization,
        title: e.title ?? e.role,
        role: e.role,
        description: [e.summary, ...(e.responsibilities ?? [])].filter(Boolean).join('\n'),
        start: e.start_date,
        end: e.end_date,
      }))
    const seedProjects = (vaultSeed?.experiences ?? [])
      .filter((e) => e.experience_id !== 'exp_ml_evaluation')
      .map((e) => ({
        id: e.experience_id,
        organization: e.organization,
        title: e.title ?? e.role,
        role: e.role,
        description: [e.summary, ...(e.responsibilities ?? [])].filter(Boolean).join('\n'),
        start: e.start_date,
        end: e.end_date,
      }))
    return {
      awards: (vaultSeed?.awards ?? []).map((a) => ({
        award_id: a.award_id,
        name: a.name,
        issuer: a.issuer,
        date: a.date,
        description: a.description,
      })),
      internships: seedInternships,
      projects: seedProjects,
      source: 'seed' as const,
    }
  }, [resumeForm, vaultSeed])

  const vaultItemCount =
    vaultPayload.awards.length + vaultPayload.internships.length + vaultPayload.projects.length

  // Build rows FROM 经历库 entries, then attach latest match status (vault-first).
  // Always keep label/kind from 经历库 — never reuse stale seed labels from cached match.
  const vaultRows = useMemo(() => {
    const byId = new Map<string, ResumeMatchItem>(
      (matchReport?.results ?? []).map((r) => [`${r.target_type}:${r.target_id}`, r]),
    )
    const rows: ResumeMatchItem[] = []
    for (const item of vaultPayload.internships) {
      const key = `internship:${item.id}`
      const hit = byId.get(key)
      const label = [item.organization, item.title].filter(Boolean).join(' · ') || item.id
      rows.push(
        hit
          ? { ...hit, target_type: 'internship', target_id: item.id, kind: '实习', label }
          : {
              target_type: 'internship',
              target_id: item.id,
              kind: '实习',
              label,
              status: 'UNCHECKED',
              score: 0,
              notes: ['尚未对照'],
              action: '点「一键对照经历库」开始匹配证据',
              candidate_fields: {},
            },
      )
    }
    for (const item of vaultPayload.projects) {
      const key = `project:${item.id}`
      const hit = byId.get(key) ?? byId.get(`experience:${item.id}`)
      const label = [item.organization, item.title].filter(Boolean).join(' · ') || item.id
      rows.push(
        hit
          ? { ...hit, target_type: 'project', target_id: item.id, kind: '项目', label }
          : {
              target_type: 'project',
              target_id: item.id,
              kind: '项目',
              label,
              status: 'UNCHECKED',
              score: 0,
              notes: ['尚未对照'],
              action: '点「一键对照经历库」开始匹配证据',
              candidate_fields: {},
            },
      )
    }
    for (const item of vaultPayload.awards) {
      const key = `award:${item.award_id}`
      const hit = byId.get(key)
      const label = item.name
      rows.push(
        hit
          ? { ...hit, target_type: 'award', target_id: item.award_id, kind: '获奖/竞赛', label }
          : {
              target_type: 'award',
              target_id: item.award_id,
              kind: '获奖/竞赛',
              label,
              status: 'UNCHECKED',
              score: 0,
              notes: ['尚未对照'],
              action: '点「一键对照经历库」开始匹配证据',
              candidate_fields: {},
            },
      )
    }
    return rows
  }, [vaultPayload, matchReport])

  const activeMatch = vaultRows.find((row) => matchKey(row) === selectedMatchKey)
  const activeMatchEvidenceId = activeMatch?.evidence_id
  useEffect(() => {
    if (previewContext === 'match' && activeMatchEvidenceId && !openEvidenceId) setSelectedEvidenceId(activeMatchEvidenceId)
  }, [activeMatchEvidenceId, openEvidenceId, previewContext])

  const evidenceExcerpt = useMemo(() => {
    if (!detail || detail.evidence_id !== activeMatch?.evidence_id) return undefined
    const terms = activeMatch.label.split(/\s*·\s*/).filter((term) => term.length > 2)
    const spans = detail.spans ?? []
    const hit = spans.find((span) => terms.some((term) => span.raw_text.toLowerCase().includes(term.toLowerCase())))
    const raw = hit?.raw_text || detail.file?.ocr_text_preview || spans[0]?.raw_text || ''
    const index = terms.map((term) => raw.toLowerCase().indexOf(term.toLowerCase())).find((value) => value >= 0) ?? 0
    const start = Math.max(0, index - 50)
    const text = (start > 0 ? '…' : '') + raw.slice(start, start + 300) + (raw.length > start + 300 ? '…' : '')
    return { evidenceId: detail.evidence_id, text }
  }, [detail, activeMatch])

  const coverage = useMemo(() => {
    const results = vaultRows
    const total = results.length
    const linked = results.filter((r) => r.status === 'LINKED').length
    const pending = results.filter(
      (r) => r.status === 'MATCHED' || r.status === 'NEEDS_CONFIRM',
    ).length
    const conflict = results.filter((r) => r.status === 'CONFLICT').length
    const missing = results.filter((r) => r.status === 'MISSING').length
    const unchecked = results.filter((r) => r.status === 'UNCHECKED').length
    const unmatched = missing + conflict + unchecked
    return { total, linked, pending, conflict, missing, unmatched, unchecked }
  }, [vaultRows])

  const ensureDraftForm = useCallback(() => {
    if (resumeForm) return resumeForm
    if (vaultSeed) {
      const built = { ...buildResumeFormFromVault(vaultSeed), dirty: true as const }
      setResumeForm(built)
      return built
    }
    return null
  }, [resumeForm, vaultSeed, setResumeForm])

  const refreshLists = useCallback(
    async (wsId: string) => {
      if (!wsId) return
      const [f, e] = await Promise.all([
        api.listEvidenceFiles(wsId),
        api.listWorkspaceEvidence(wsId),
      ])
      if (loadStoredWorkspaceId() !== wsId) return
      if (f.data) {
        const visible = f.data.filter((item) => !isHiddenPath(item.relative_path))
        const hiddenN = f.data.length - visible.length
        setFiles(visible)
        if (hiddenN > 0) {
          setMessage(`已清理 ${hiddenN} 个位于「.」开头隐藏路径下的旧导入（如 .codex-plugins / .git）。`)
        }
      }
      if (e.data) setEvidenceList(e.data)
    },
    [api],
  )

  const loadWorkspaces = useCallback(async () => {
    const res = await api.listEvidenceWorkspaces()
    const list = res.data ?? []
    setWorkspaces(list)
    const stored = loadStoredWorkspaceId()
    if (stored && list.some((w) => w.workspace_id === stored)) {
      if (workspaceId !== stored) setWorkspaceId(stored)
      return
    }
    if (!workspaceId && list[0]) {
      setWorkspaceId(list[0].workspace_id)
    }
  }, [api, workspaceId])

  useEffect(() => {
    void loadWorkspaces()
  }, [loadWorkspaces])

  useEffect(() => {
    saveStoredWorkspaceId(workspaceId)
    if (workspaceId) void refreshLists(workspaceId)
  }, [workspaceId, refreshLists])

  useEffect(() => {
    if (openEvidenceId) {
      setSelectedEvidenceId(openEvidenceId)
      setPreviewOpen(true)
    }
  }, [openEvidenceId])

  // Ignore late responses when users move quickly between evidence pairs.
  useEffect(() => {
    let cancelled = false
    setDetail(null)
    setPreviewError('')
    setDraftSavedAt('')
    setFieldSaveError('')
    activeEvidenceRef.current = selectedEvidenceId
    if (!selectedEvidenceId) return
    void api.getEvidence(selectedEvidenceId).then((res) => {
      if (cancelled) return
      if (res.data) {
            setDetail({ ...res.data, spans: orderedEvidenceSpans(res.data.spans || []) })
        setFields({ ...res.data.normalized_fields })
        setDraftSavedAt(res.data.reviewed_at || '')
      } else setPreviewError(res.error?.message || '无法加载证据，请重新打开。')
    })
    return () => { cancelled = true }
  }, [api, selectedEvidenceId, detailRevision])

  // Capture the file ID with each draft; serialize saves before confirming a review.
  const flushFieldDraft = useCallback(() => {
    if (fieldsSaveTimer.current) clearTimeout(fieldsSaveTimer.current)
    const draft = pendingFieldDraft.current
    if (!draft) return fieldSaveQueue.current
    pendingFieldDraft.current = null
    fieldSaveQueue.current = fieldSaveQueue.current.then(async () => {
      const res = await api.reviewEvidence(draft.id, {
        normalized_fields: draft.fields, review_state: 'UNREVIEWED',
      })
      if (activeEvidenceRef.current === draft.id) {
        if (res.data) {
          setDraftSavedAt(new Date().toISOString())
          setFieldSaveError('')
        } else setFieldSaveError(res.error?.message || '草稿保存失败，请重试。')
      }
      if (res.data) await refreshLists(draft.workspace)
      return !!res.data
    })
    return fieldSaveQueue.current
  }, [api, refreshLists])

  const editEvidenceField = (key: keyof AwardEvidenceFields, value: string) => {
    const next = { ...fields, [key]: value }
    setFields(next)
    setDraftSavedAt('')
    pendingFieldDraft.current = { id: selectedEvidenceId, fields: next, workspace: workspaceId }
    if (fieldsSaveTimer.current) clearTimeout(fieldsSaveTimer.current)
    fieldsSaveTimer.current = setTimeout(() => void flushFieldDraft(), 600)
  }

  useEffect(() => () => { void flushFieldDraft() }, [flushFieldDraft])

  const openPreview = (evidenceId: string) => {
    void flushFieldDraft()
    setPreviewContext('match')
    setSelectedEvidenceId(evidenceId)
    setPreviewOpen(true)
  }

  const selectMatch = useCallback((row: ResumeMatchItem) => {
    void flushFieldDraft()
    setPreviewContext('match')
    setLibraryFileId('')
    setSelectedMatchKey(matchKey(row))
    setSelectedEvidenceId(row.evidence_id || '')
    setPreviewOpen(false)
    setClaimResult('')
  }, [flushFieldDraft])

  const sourceDetails = useMemo(() => {
    const entries: Record<string, { label: string; value: string }[]> = {}
    vaultPayload.awards.forEach((item) => {
      entries[`award:${item.award_id}`] = [
        { label: '颁发方', value: item.issuer || '' },
        { label: '日期', value: item.date || '' },
        { label: '描述', value: item.description || '' },
      ]
    })
    for (const [type, items] of [['internship', vaultPayload.internships], ['project', vaultPayload.projects]] as const) {
      items.forEach((item) => {
        entries[`${type}:${item.id}`] = [
          { label: '组织', value: item.organization || '' },
          { label: '角色', value: item.role || '' },
          { label: '时间', value: [item.start, item.end].filter(Boolean).join(' — ') },
          { label: '描述', value: item.description || '' },
        ]
      })
    }
    return entries
  }, [vaultPayload])

  const closePreview = () => {
    setPreviewOpen(false)
  }

  const stats = useMemo(() => {
    const supported = pending.filter((p) => !p.unsupported)
    const unsupported = pending.filter((p) => p.unsupported)
    const byExt: Record<string, number> = {}
    supported.forEach((p) => {
      const e = extOf(p.relative_path) || '(none)'
      byExt[e] = (byExt[e] || 0) + 1
    })
    const existingByPath = new Map(files.map((f) => [f.relative_path.replace(/\\/g, '/'), f]))
    let wouldSkip = 0
    if (skipAlreadyRecognized) {
      for (const p of supported) {
        if (p.relative_path.toLowerCase().endsWith('.ocr.json')) continue
        const ex = existingByPath.get(p.relative_path.replace(/\\/g, '/'))
        if (ex && alreadyRecognized(ex) && ex.size === p.file.size) wouldSkip += 1
      }
    }
    return { supported, unsupported, byExt, wouldSkip }
  }, [pending, files, skipAlreadyRecognized])

  const pickDirectory = async () => {
    setMessage('')
    const w = window as Window & {
      showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>
    }
    if (typeof w.showDirectoryPicker === 'function') {
      try {
        const handle = await w.showDirectoryPicker()
        const collected = await collectFromDirectoryHandle(handle)
        setPreviewContext('library')
        setPending(collected)
        setMessage(
          `已枚举 ${collected.length} 个文件（已跳过 . 开头的隐藏文件夹），确认后开始导入。`,
        )
        return
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        directoryInputRef.current?.click()
      }
    } else {
      directoryInputRef.current?.click()
    }
  }

  const onMultiFiles = (list: FileList | null) => {
    if (!list?.length) return
    setPreviewContext('library')
    const next: PendingFile[] = Array.from(list)
      .map((file) => ({
        relative_path: (file.webkitRelativePath || file.name).replace(/\\/g, '/'),
        file,
        unsupported: !isAllowed(file.name) && !isAllowed(file.webkitRelativePath || file.name),
      }))
      .filter((item) => !isHiddenPath(item.relative_path))
    const skippedHidden = list.length - next.length
    setPending(next)
    if (skippedHidden > 0) {
      setMessage(`已跳过 ${skippedHidden} 个位于隐藏文件夹（.开头）下的文件。`)
    }
  }

  const ensureWorkspace = async (): Promise<string | null> => {
    if (workspaceId) return workspaceId
    setBusy('创建工作区…')
    const created = await api.createEvidenceWorkspace('本地证据工作区')
    setBusy('')
    if (created.error || !created.data) {
      setMessage(created.error?.message || '创建工作区失败')
      return null
    }
    setWorkspaces((prev) => [created.data!, ...prev])
    setWorkspaceId(created.data.workspace_id)
    saveStoredWorkspaceId(created.data.workspace_id)
    return created.data.workspace_id
  }

  const importPending = async () => {
    const ws = await ensureWorkspace()
    if (!ws) return
    const batch = stats.supported
    if (!batch.length) {
      setMessage('没有可导入的支持类型文件。')
      return
    }
    setBusy('导入并解析中…')
    setMessage('')

    // Pair OCR sidecars with their images; import one primary file (plus sidecar) at a time for progress.
    const byPath = new Map(
      batch.map((item) => [item.relative_path.replace(/\\/g, '/'), item] as const),
    )
    const MAX_UPLOAD_BYTES = 6 * 1024 * 1024
    const primaries = batch.filter((item) => !item.relative_path.toLowerCase().endsWith('.ocr.json'))
    const existingByPath = new Map(files.map((f) => [f.relative_path.replace(/\\/g, '/'), f]))
    const skippedHuge = primaries.filter((item) => item.file.size > MAX_UPLOAD_BYTES)
    const skippedKnown: PendingFile[] = []
    const uploadList = primaries.filter((item) => {
      if (item.file.size > MAX_UPLOAD_BYTES) return false
      if (!skipAlreadyRecognized) return true
      const rel = item.relative_path.replace(/\\/g, '/')
      const ex = existingByPath.get(rel)
      if (ex && alreadyRecognized(ex) && ex.size === item.file.size) {
        skippedKnown.push(item)
        return false
      }
      return true
    })
    if (!uploadList.length) {
      setBusy('')
      if (skippedKnown.length) {
        setMessage(
          `已全部跳过：${skippedKnown.length} 个文件本机已有识别结果（未重跑 OCR）。取消勾选「跳过已识别」可强制重新上传。`,
        )
        setPending([])
      } else {
        setMessage(`没有可导入文件（${skippedHuge.length} 个超过 6MB 已跳过）。`)
      }
      return
    }
    const totalSteps = Math.max(1, uploadList.length * 2) // read + upload per file
    let step = 0
    let okCount = 0
    let failCount = skippedHuge.length
    let reusedCount = skippedKnown.length
    let firstFail = skippedHuge[0]
      ? `${skippedHuge[0].relative_path} 超过 6MB，已跳过`
      : ''
    let firstEvidence = ''
    const allResults: EvidenceSourceFile[] = []

    try {
      for (const item of uploadList) {
        const rel = item.relative_path.replace(/\\/g, '/')
        step += 1
        setImportProgress({
          phase: 'read',
          current: step,
          total: totalSteps,
          label: `读取 ${rel}`,
        })
        const payload: Array<{ relative_path: string; content_base64: string }> = [
          { relative_path: rel, content_base64: await fileToBase64(item.file) },
        ]
        const side =
          byPath.get(`${rel}.ocr.json`) ||
          byPath.get(`${rel.split('/').pop()}.ocr.json`)
        if (side && side.file.size <= MAX_UPLOAD_BYTES) {
          payload.push({
            relative_path: side.relative_path.replace(/\\/g, '/'),
            content_base64: await fileToBase64(side.file),
          })
        }

        step += 1
        setImportProgress({
          phase: 'upload',
          current: step,
          total: totalSteps,
          label: `解析 ${rel}`,
        })
        const res = await api.importEvidenceFiles(ws, payload)
        if (res.error || !res.data) {
          failCount += 1
          const hint =
            res.error?.code === 'NETWORK_ERROR'
              ? '后端连接被重置。请确认 python -m backend.app 仍在运行，然后重试；勿一次选整个大仓库。'
              : res.error?.message || '导入失败'
          if (!firstFail) firstFail = hint
          continue
        }
        allResults.push(...res.data.files)
        const failed = res.data.files.filter((f) => f.state === 'FAILED' && !f.sidecar)
        const skipped = res.data.files.filter((f) => f.skipped_reparse && !f.sidecar)
        const ok = res.data.files.filter(
          (f) => f.state !== 'FAILED' && !f.sidecar && !f.skipped_reparse,
        )
        okCount += ok.length
        reusedCount += skipped.length
        failCount += failed.length
        if (!firstFail && failed[0]?.parse_error) firstFail = failed[0].parse_error
        if (!firstEvidence) {
          firstEvidence = res.data.files.find((f) => f.evidence_id)?.evidence_id || ''
        }
        // Refresh list incrementally so file status updates while importing
        await refreshLists(ws)
      }

      setImportProgress({
        phase: 'refresh',
        current: totalSteps,
        total: totalSteps,
        label: '刷新文件列表…',
      })
      await refreshLists(ws)
      const summary =
        `导入完成：新识别 ${okCount}，复用已有 ${reusedCount}，失败 ${failCount}` +
        (firstFail ? `（例：${firstFail}）` : '')
      setMessage(summary)
      setPending([])
      if (firstEvidence) setSelectedEvidenceId(firstEvidence)
      else {
        const ev = allResults.find((f) => f.evidence_id)?.evidence_id
        if (ev) setSelectedEvidenceId(ev)
      }
      // After import, auto-match against 经历库 when entries exist
      if (vaultItemCount > 0 && (okCount > 0 || reusedCount > 0)) {
        setBusy('导入完成，正在对照经历库…')
        const match = await api.matchResumeEvidence(ws, {
          awards: vaultPayload.awards,
          internships: vaultPayload.internships,
          projects: vaultPayload.projects,
        })
        if (match.data) {
          setMatchReport(match.data)
          saveStoredMatch(ws, match.data)
          setMessage(
            `${summary}。识别结果已在本机；已自动对照经历库（缺证据 ${match.data.summary.MISSING ?? 0}，待确认 ${match.data.summary.NEEDS_CONFIRM ?? 0}）。`,
          )
        }
      } else if (okCount > 0 || reusedCount > 0) {
        setMessage(`${summary}。OCR/解析结果保存在本机工作区，刷新后仍可查看，无需重跑。`)
      }
    } finally {
      setBusy('')
      setImportProgress(null)
    }
  }

  const reparseOne = async (fileId: string) => {
    setBusy('正在重新识别当前材料…')
    await flushFieldDraft()
    setMessage('')
    const res = await api.reparseEvidenceFile(fileId)
    setBusy('')
    if (res.error || !res.data) {
      setMessage(res.error?.message || '重新识别失败')
      return
    }
    if (workspaceId) await refreshLists(workspaceId)
    if (res.data.evidence_id) {
      setSelectedEvidenceId(res.data.evidence_id)
      setDetailRevision((value) => value + 1)
    }
    if (res.data.state === 'FAILED' || res.data.parse_error) {
      setMessage(
        `重新识别未得到可用文本：${res.data.parse_error || res.data.notice || '未知原因'}`,
      )
      return
    }
    const preview = res.data.ocr_text_preview || ''
    setMessage(
      (res.data.notice || '已重新识别（未重新上传）') +
        (preview ? ` · 摘要：${preview.slice(0, 80)}` : ''),
    )
  }

  const confirmReview = async () => {
    if (!selectedEvidenceId) return
    setBusy('提交核对…')
    await flushFieldDraft()
    const res = await api.reviewEvidence(selectedEvidenceId, {
      normalized_fields: fields,
      review_state: 'REVIEWED',
      span_ids: detail?.spans?.map((s) => s.span_id),
    })
    setBusy('')
    if (res.error || !res.data) {
      setMessage(res.error?.message || '核对失败')
      return
    }
    setDetail({ ...res.data, spans: orderedEvidenceSpans(res.data.spans || []) })
    setFields({ ...res.data.normalized_fields })
    setDraftSavedAt(res.data.reviewed_at || new Date().toISOString())
    setMessage('已确认证据并保存到本机。OCR 原文仍保留，界面字段为人工确认版本。')
    if (workspaceId) {
      await refreshLists(workspaceId)
      await runMatchVault()
    }
  }

  const linkToTarget = async () => {
    if (!selectedEvidenceId || !linkTargetId) {
      setMessage('请从经历库奖项进入本页（带 target_id），或在下方手动填写关联目标。')
      return
    }
    setBusy('建立关联…')
    const res = await api.createEvidenceLink({
      target_type: linkTargetType,
      target_id: linkTargetId,
      evidence_id: selectedEvidenceId,
    })
    setBusy('')
    if (res.error || !res.data) {
      setMessage(res.error?.message || '关联失败（需先完成核对）')
      return
    }
    setMessage(
      `已关联 ${linkTargetType}:${linkTargetId} → ${selectedEvidenceId}（${res.data.link_state}）`,
    )
  }

  const runClaimCheck = async () => {
    if (!selectedEvidenceId || !claimProbe.trim()) return
    setBusy('检查陈述…')
    const res = await api.checkClaimEvidence(claimProbe, selectedEvidenceId)
    setBusy('')
    if (res.error || !res.data) {
      setClaimResult(res.error?.message || '检查失败')
      return
    }
    setClaimResult(
      `${({ VERIFIED: '可支持', CONFLICT: '存在冲突', STALE: '材料已过期', NEEDS_REVIEW: '需先核对' } as Record<string, string>)[res.data.status] || res.data.status}` +
        (res.data.reasons.length ? `：${res.data.reasons.join('；')}` : '（相对本地证据可支持）'),
    )
  }

  const deleteWs = async () => {
    if (!workspaceId) return
    if (!window.confirm('删除工作区将清除本机副本与索引，关联 Claim/奖项将失去该来源。继续？')) {
      return
    }
    const res = await api.deleteEvidenceWorkspace(workspaceId)
    if (res.error || !res.data) {
      setMessage(res.error?.message || '删除失败，请重试。')
      return
    }
    setMessage(res.data.notice || '已删除')
    setSelectedEvidenceId('')
    setLibraryFileId('')
    setPreviewOpen(false)
    saveStoredMatch(workspaceId, null)
    saveStoredWorkspaceId('')
    setWorkspaceId('')
    setFiles([])
    setEvidenceList([])
    setDetail(null)
    setMatchReport(null)
    await loadWorkspaces()
  }

  const runMatchVault = async () => {
    const ws = workspaceId || (await ensureWorkspace())
    if (!ws) return
    if (!files.length) {
      setMessage('请先导入证据文件夹，再对照经历库。')
      return
    }
    if (!vaultItemCount) {
      setMessage('经历库里还没有实习 / 项目 / 获奖。请先到经历库填写，再回来对照。')
      return
    }
    setBusy('正在对照经历库与本地证据…')
    setMessage('')
    const res = await api.matchResumeEvidence(ws, {
      awards: vaultPayload.awards,
      internships: vaultPayload.internships,
      projects: vaultPayload.projects,
    })
    setBusy('')
    if (res.error || !res.data) {
      setMessage(res.error?.message || '对照失败')
      return
    }
    setMatchReport(res.data)
    saveStoredMatch(ws, res.data)
    setMessage(res.data.notice || '对照完成')
  }

  // 草稿与文件就绪后自动对照一次；列表始终以经历库条目为轴
  useEffect(() => {
    if (vaultPayload.source === 'seed') return
    if (!workspaceId || !files.length || !vaultItemCount) return
    const signature = `${resumeForm?.savedAt || 'edit'}|${vaultItemCount}|${workspaceId}`
    if (autoMatchedForDraft.current === signature) return
    if (matchReport?.results?.length) {
      autoMatchedForDraft.current = signature
      return
    }
    autoMatchedForDraft.current = signature
    void runMatchVault()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vaultPayload.source, vaultItemCount, workspaceId, files.length, resumeForm?.savedAt])

  const confirmLinkMatch = async (row: ResumeMatchItem) => {
    if (!row.evidence_id) return
    setBusy('确认关联…')
    await flushFieldDraft()
    // Use the actual evidence fields (including the current edit), never stale match-report fields.
    if (fieldsSaveTimer.current) clearTimeout(fieldsSaveTimer.current)
    const current = await api.getEvidence(row.evidence_id)
    if (!current.data || current.error) {
      setBusy('')
      setMessage(current.error?.message || '读取证据失败，请重试。')
      return
    }
    const fieldsToUse = detail?.evidence_id === row.evidence_id && selectedEvidenceId === row.evidence_id
      ? fields : current.data.normalized_fields
    if (current.data.review_state !== 'REVIEWED'
      || JSON.stringify(fieldsToUse) !== JSON.stringify(current.data.normalized_fields)) {
      const reviewed = await api.reviewEvidence(row.evidence_id, {
        normalized_fields: fieldsToUse,
        review_state: 'REVIEWED',
      })
      if (reviewed.error || !reviewed.data) {
        setBusy('')
        setMessage(reviewed.error?.message || '核对保存失败')
        return
      }
      if (selectedEvidenceId === row.evidence_id) {
            setDetail({ ...reviewed.data, spans: orderedEvidenceSpans(reviewed.data.spans || []) })
        setFields({ ...reviewed.data.normalized_fields })
      }
    }
    const linked = await api.createEvidenceLink({
      target_type: row.target_type,
      target_id: row.target_id,
      evidence_id: row.evidence_id,
      link_state: 'ACTIVE',
    })
    setBusy('')
    if (linked.error || !linked.data) {
      setMessage(linked.error?.message || '关联失败')
      return
    }
    await runMatchVault()
    setMessage(`已关联：「${row.label}」 ↔ 「${row.relative_path || '所选证据'}」。可继续处理下一条。`)
  }

  const rejectMatch = async (row: ResumeMatchItem) => {
    if (!row.evidence_id) return
    setBusy('标记不符合…')
    const res = await api.createEvidenceLink({
      target_type: row.target_type,
      target_id: row.target_id,
      evidence_id: row.evidence_id,
      link_state: 'REJECTED',
    })
    setBusy('')
    if (res.error || !res.data) {
      setMessage(res.error?.message || '标记失败')
      return
    }
    setMessage(`已标记不符合：${row.label} ✕ ${row.relative_path || row.evidence_id}，将推荐下一候选`)
    closePreview()
    setSelectedEvidenceId('')
    await runMatchVault()
    setMessage(`已排除「${row.relative_path || '此材料'}」与「${row.label}」的关联，候选已更新。`)
  }

  const unlinkMatch = async (row: ResumeMatchItem) => {
    setBusy('取消关联…')
    const res = await api.removeEvidenceLink({
      target_type: row.target_type,
      target_id: row.target_id,
      evidence_id: row.evidence_id || undefined,
    })
    setBusy('')
    if (res.error) {
      setMessage(res.error.message)
      return
    }
    await runMatchVault()
    setMessage(`已取消关联：${row.label}`)
  }

  const deleteVaultItem = (row: ResumeMatchItem) => {
    if (!window.confirm(`从经历库删除「${row.label}」？不会删除已导入的证据文件。`)) return
    const base = ensureDraftForm()
    if (!base) {
      setMessage('无法编辑：缺少经历库数据')
      return
    }
    setResumeForm((prev) => {
      const form = prev ?? base
      if (row.target_type === 'award') {
        const awards = (form.awards ?? []).filter((a) => a.id !== row.target_id)
        return {
          ...form,
          awards,
          extras: { ...form.extras, awards: syncAwardText(awards) },
          dirty: true,
        }
      }
      if (row.target_type === 'internship') {
        return {
          ...form,
          internships: form.internships.filter((e) => e.id !== row.target_id),
          dirty: true,
        }
      }
      if (row.target_type === 'project' || row.target_type === 'experience') {
        return {
          ...form,
          projects: form.projects.filter((e) => e.id !== row.target_id),
          dirty: true,
        }
      }
      return form
    })
    void api
      .removeEvidenceLink({ target_type: row.target_type, target_id: row.target_id })
      .catch(() => undefined)
    setMessage(`已删除经历库条目：${row.label}`)
    window.setTimeout(() => void runMatchVault(), 50)
  }

  const addVaultItem = () => {
    const label = addLabel.trim()
    if (!label) {
      setMessage('请填写名称后再添加')
      return
    }
    const base = ensureDraftForm()
    if (!base) {
      setMessage('无法添加：缺少经历库数据，请先打开经历库页加载种子')
      return
    }
    setResumeForm((prev) => {
      const form = prev ?? base
      if (addKind === 'award') {
        const awards = [
          ...(form.awards ?? []),
          {
            id: newExperienceId('award'),
            name: label,
            issuer: addOrg.trim(),
            date: '',
            description: '',
          },
        ]
        return {
          ...form,
          awards,
          extras: { ...form.extras, awards: syncAwardText(awards) },
          dirty: true,
        }
      }
      if (addKind === 'internship') {
        return {
          ...form,
          internships: [
            ...form.internships,
            {
              id: newExperienceId('intern'),
              organization: addOrg.trim() || label,
              title: label,
              role: '',
              start: '',
              end: '',
              description: '',
            },
          ],
          dirty: true,
        }
      }
      return {
        ...form,
        projects: [
          ...form.projects,
          {
            id: newExperienceId('proj'),
            organization: addOrg.trim() || label,
            title: label,
            role: '',
            start: '',
            end: '',
            description: '',
          },
        ],
        dirty: true,
      }
    })
    setAddLabel('')
    setAddOrg('')
    setMessage(`已添加${addKind === 'award' ? '获奖' : addKind === 'internship' ? '实习' : '项目'}：${label}`)
    window.setTimeout(() => void runMatchVault(), 50)
  }

  const startSupplement = (row: ResumeMatchItem) => {
    setSupplementTarget(row)
    window.setTimeout(() => supplementInputRef.current?.click(), 0)
  }

  const onSupplementFiles = async (list: FileList | null) => {
    const row = supplementTarget
    setSupplementTarget(null)
    if (!list?.length || !row) return
    const ws = workspaceId || (await ensureWorkspace())
    if (!ws) return
    setBusy(`正在为「${row.label}」补充证据…`)
    const payload = []
    for (const file of Array.from(list)) {
      if (file.size > 6 * 1024 * 1024) continue
      const rel = (file.webkitRelativePath || file.name).replace(/\\/g, '/')
      if (isHiddenPath(rel) || !isAllowed(rel)) continue
      payload.push({ relative_path: rel, content_base64: await fileToBase64(file) })
    }
    if (!payload.length) {
      setBusy('')
      setMessage('没有可导入的支持文件')
      return
    }
    const res = await api.importEvidenceFiles(ws, payload)
    setBusy('')
    if (res.error || !res.data) {
      setMessage(res.error?.message || '补充导入失败')
      return
    }
    await refreshLists(ws)
    setMessage(`已为「${row.label}」补充 ${res.data.files.filter((f) => !f.sidecar).length} 个文件，正在重新对照…`)
    await runMatchVault()
  }

  const renderEvidenceEditor = (expanded = false) => (
    <details className="relation-field-editor" open={expanded || undefined}>
      <summary>核对 / 修正识别字段</summary>
      <p className="material-helper">以下为奖项类字段，其他材料可留空。请按原件填写；确认核对后，再到经历对照区建立关联。</p>
          <div className="resume-fields">
            {(
              [
                ['recipient', '获奖人'],
                ['award_name', '奖项名称'],
                ['grade', '等级'],
                ['issuer', '颁发方'],
                ['date', '日期'],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="resume-field">
                {label}
                <input
                  className="resume-input"
                  disabled={!!busy || detail?.evidence_id !== selectedEvidenceId}
                  value={fields[key] || ''}
                  onChange={(e) => editEvidenceField(key, e.target.value)}
                />
              </label>
            ))}
          </div>
          {fieldSaveError && <p role="alert" className="danger-text">{fieldSaveError} <button type="button" className="linkish" onClick={() => {
            pendingFieldDraft.current = { id: selectedEvidenceId, fields, workspace: workspaceId }
            void flushFieldDraft()
          }}>重试保存</button></p>}
          {draftSavedAt ? (
            <p className="muted">最近保存：{new Date(draftSavedAt).toLocaleString('zh-CN')}</p>
          ) : (
            <p className="muted">修改会自动保存为草稿；核对无误后点击「确认材料已核对」。</p>
          )}
          <div className="btn-row">
            <button type="button" className="btn primary" disabled={!!busy || !detail || detail.evidence_id !== selectedEvidenceId} onClick={() => void confirmReview()}>
              确认材料已核对
            </button>
          </div>

    </details>
  )

  const renderPreview = () => (
    <div className="relation-preview">
      <div className="evidence-preview-dock-head">
        <strong>证据原件</strong>
        <button type="button" className="btn secondary" onClick={closePreview}>收起原件</button>
      </div>
      {previewError ? <p role="alert">{previewError}</p> : detail?.evidence_id === selectedEvidenceId && detail.file ? <>
        <p className="relation-file-caption">{detail.file.relative_path}</p>
        <PreviewPane file={detail.file} spans={detail.spans ?? []} highlightText={fields.grade || undefined} />
        {renderEvidenceEditor()}
      </> : <p role="status">正在加载当前证据…</p>}
    </div>
  )

  return (
    <section className="panel evidence-workspace">
      <header className="panel-head">
        <h2>本地证据工作区</h2>
        <p>
          选一条经历，核对右侧对应材料，再确认关联。每次操作只针对当前显示的这一对记录。
        </p>
        <p>
          <Link to="/vault">去经历库编辑</Link>
          {' · '}
          可对照{' '}
          <strong>
            实习 {vaultPayload.internships.length} · 项目 {vaultPayload.projects.length} · 获奖{' '}
            {vaultPayload.awards.length}
          </strong>
          {' · '}
          数据来源：
          <strong>
            {vaultSourceHint ||
              (vaultPayload.source === 'seed'
                ? '种子数据'
                : vaultPayload.source === 'editing'
                  ? '经历库未保存编辑'
                  : '本机草稿')}
          </strong>
        </p>
        {vaultPayload.source === 'seed' ? (
          <p className="warn-text">
            当前仍是种子数据。请先到经历库填写并点「保存」，再回这里对照；或确认后端草稿可读。
          </p>
        ) : null}
      </header>

      {busy ? <p className="muted" role="status">{busy}</p> : null}
      {message ? <div className="callout" role="status">{message}</div> : null}

      <div className="evidence-match-banner">
        <div>
          <h3>经历 ↔ 证明材料</h3>
          <p className="muted">
            已导入 {files.length} 份材料 · 已关联 {coverage.linked}/{coverage.total} 条经历 · 待处理 {coverage.total - coverage.linked} 条
          </p>
        </div>
        <div className="btn-row">
        <a className="btn secondary" href="#evidence-relations">开始核对 ↓</a>
        <a className="btn secondary" href="#evidence-files">导入 / 管理材料</a>
        <button
          type="button"
          className="btn primary"
          disabled={!!importProgress || !!busy}
          onClick={() => void runMatchVault()}
        >
          一键对照经历库
        </button>
        </div>
      </div>

      <details className="relation-add"><summary>＋ 添加一条经历</summary>
      <div className="evidence-add-bar">
        <select
          className="resume-input resume-select"
          value={addKind}
          onChange={(e) => setAddKind(e.target.value as 'internship' | 'project' | 'award')}
        >
          <option value="award">获奖/竞赛</option>
          <option value="project">项目</option>
          <option value="internship">实习</option>
        </select>
        <input
          className="resume-input"
          placeholder={addKind === 'award' ? '奖项名称' : '标题'}
          value={addLabel}
          onChange={(e) => setAddLabel(e.target.value)}
        />
        <input
          className="resume-input"
          placeholder={addKind === 'award' ? '颁发方（可选）' : '组织（可选）'}
          value={addOrg}
          onChange={(e) => setAddOrg(e.target.value)}
        />
        <button type="button" className="btn secondary" onClick={addVaultItem}>
          添加条目
        </button>
      </div>

      </details>
      <input
        ref={supplementInputRef}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          void onSupplementFiles(e.target.files)
          e.target.value = ''
        }}
      />

      <EvidenceMatchBoard key={`matches:${workspaceId}`} rows={vaultRows} selectedKey={selectedMatchKey} busy={!!busy || !!importProgress}
        sourceDetails={sourceDetails} evidenceExcerpt={evidenceExcerpt} onSelect={selectMatch}
        onConfirm={(row) => void confirmLinkMatch(row)} onReject={(row) => void rejectMatch(row)}
        onUnlink={(row) => void unlinkMatch(row)} onSupplement={startSupplement}
        onDelete={deleteVaultItem} onMatch={() => void runMatchVault()}
        renderEvidence={(row) => row.evidence_id ? (
          previewContext === 'match' && previewOpen && selectedEvidenceId === row.evidence_id ? renderPreview() :
          <button type="button" className="btn secondary relation-preview-button" onClick={() => openPreview(row.evidence_id!)}>查看 B 的原件与识别字段</button>
        ) : null}
      />

      <EvidenceMaterialLibrary key={`materials:${workspaceId}`} files={files} rows={vaultRows}
        selectedFileId={previewContext === 'library' ? libraryFileId : ''}
        workspaceName={workspaces.find((workspace) => workspace.workspace_id === workspaceId)?.name || ''}
        busy={!!busy || !!importProgress}
        onSelect={(file) => {
          void flushFieldDraft()
          setMessage('')
          setPreviewContext('library')
          setLibraryFileId(file.file_id)
          setSelectedEvidenceId(file.evidence_id || evidenceList.find((entry) => entry.primary_file_id === file.file_id)?.evidence_id || '')
          setPreviewOpen(false)
          setClaimResult('')
          setClaimProbe('')
        }}
        onFocusRow={(row) => {
          selectMatch(row)
          document.getElementById('evidence-relations')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }}
        onSearch={async (query) => {
          if (!workspaceId) return { matches: [], error: '请先导入材料。' }
          const result = await api.searchEvidence(query, workspaceId)
          return { matches: result.data || [], error: result.error?.message }
        }}
        imports={<div className="btn-row">
          <button type="button" className="btn primary" disabled={!!busy} onClick={() => uploadInputRef.current?.click()}>＋ 添加文件</button>
          <button type="button" className="btn secondary" disabled={!!busy} onClick={() => void pickDirectory()}>导入文件夹</button>
          <input ref={uploadInputRef} type="file" multiple hidden accept=".jpg,.jpeg,.png,.webp,.gif,.pdf,.doc,.docx,.md,.markdown,.json" onChange={(event) => {
            onMultiFiles(event.target.files); event.target.value = ''
          }} />
          <input ref={directoryInputRef} type="file" multiple hidden
            // @ts-expect-error webkitdirectory is supported by Chromium folder inputs
            webkitdirectory="" onChange={(event) => { onMultiFiles(event.target.files); event.target.value = '' }} />
        </div>}
        notice={<>
          {busy && <p className="material-local-notice" role="status">{busy}</p>}
          {message && previewContext === 'library' && <p className="material-local-notice" role="status">{message}</p>}
          {pending.length > 0 ? (
            <div className="callout">
              <p>
                将导入 <strong>{stats.supported.length}</strong> 个支持文件
                {stats.unsupported.length
                  ? `，跳过 ${stats.unsupported.length} 个不支持类型`
                  : ''}
                {stats.wouldSkip
                  ? `；其中约 ${stats.wouldSkip} 个本机已有识别，将直接复用`
                  : ''}
                。
              </p>
              <ul className="muted">
                {Object.entries(stats.byExt).map(([k, n]) => (
                  <li key={k}>
                    {k} × {n}
                  </li>
                ))}
              </ul>
              <label className="evidence-skip-label">
                <input
                  type="checkbox"
                  checked={skipAlreadyRecognized}
                  onChange={(e) => setSkipAlreadyRecognized(e.target.checked)}
                />
                跳过已识别文件（默认开启，避免重复 OCR）
              </label>
              <button
                type="button"
                className="btn primary"
                disabled={!!busy || !!importProgress}
                onClick={() => void importPending()}
              >
                {importProgress ? '导入中…' : '开始导入与识别'}
              </button>
              <button type="button" className="btn secondary" disabled={!!busy || !!importProgress} onClick={() => setPending([])}>取消这批导入</button>
            </div>
          ) : null}

          {importProgress ? (
            <div className="evidence-progress" aria-live="polite">
              <div className="evidence-progress-meta">
                <span>
                  {importProgress.phase === 'read'
                    ? '读取文件'
                    : importProgress.phase === 'upload'
                      ? '上传并解析'
                      : '收尾'}
                  ：{importProgress.label}
                </span>
                <span className="muted">
                  {importProgress.current}/{importProgress.total}
                </span>
              </div>
              <div
                className="evidence-progress-bar"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={importProgress.total}
                aria-valuenow={importProgress.current}
              >
                <span
                  style={{
                    width: `${Math.max(
                      4,
                      Math.round((importProgress.current / importProgress.total) * 100),
                    )}%`,
                  }}
                />
              </div>
              <p className="muted evidence-progress-hint">
                正在处理，请稍候；已识别文件会跳过 OCR。列表会随每个文件完成而更新。
              </p>
            </div>
          ) : null}
        </>}
        settings={<div className="material-settings-body">
          <label className="resume-field">当前工作区
            <select className="resume-input" value={workspaceId} disabled={!!busy} onChange={(event) => {
              void flushFieldDraft()
              const id = event.target.value
              setSelectedMatchKey(''); setSelectedEvidenceId(''); setLibraryFileId(''); setPreviewOpen(false)
              setPreviewContext('match'); setPending([]); setFiles([]); setEvidenceList([]); setClaimResult('')
              setWorkspaceId(id); saveStoredWorkspaceId(id); setMatchReport(loadStoredMatch(id))
            }}>
              <option value="" disabled>导入时自动创建</option>
              {workspaces.map((workspace) => <option key={workspace.workspace_id} value={workspace.workspace_id}>{workspace.name}</option>)}
            </select>
          </label>
          <p>文件首次导入时会自动准备工作区，无需手动创建。</p>
          <button type="button" className="btn ghost-danger" disabled={!workspaceId || !!busy} onClick={() => void deleteWs()}>删除此工作区…</button>
        </div>}
        renderDetail={(file, tab) => {
          const currentDetail = detail?.evidence_id === selectedEvidenceId && detail?.primary_file_id === file.file_id ? detail : null
          const waiting = !!selectedEvidenceId && !currentDetail && !previewError
          return <>
            {previewError && <p role="alert" className="danger-text">{previewError} <button type="button" className="linkish" onClick={() => setDetailRevision((value) => value + 1)}>重试</button></p>}
            {tab === 'original' && <PreviewPane file={file} spans={currentDetail?.spans || []} />}
            {tab === 'text' && (waiting ? <p role="status">正在读取识别文字…</p> : currentDetail?.spans?.some((span) => span.raw_text.trim()) ?
              <div className="material-transcript">{currentDetail.spans.map((span) => <p key={span.span_id}>{span.raw_text}</p>)}</div> :
              <div className="material-empty"><strong>暂无识别文字</strong><p>仍可查看原件并人工核对。识别功能就绪后，可点击下方「重新识别」。</p></div>)}
            {tab === 'fields' && (waiting ? <p role="status">正在读取核对字段…</p> : currentDetail ? renderEvidenceEditor(true) : <p className="material-helper">该文件尚未生成可核对条目，请先重新识别。</p>)}
            <div className="material-detail-actions">
              <span>版本 {file.version} · {file.span_count || 0} 个文字片段</span>
              <button type="button" className="btn secondary" disabled={!!busy} onClick={() => void reparseOne(file.file_id)}>重新识别</button>
            </div>
            {file.parse_error && <details className="material-diagnostics"><summary>识别问题详情</summary><p>{file.parse_error}</p></details>}
            {currentDetail && <details className="material-check-tool"><summary>辅助检查：材料能否支持某句话？</summary>
              <p>只检查当前文件「{materialName(file.relative_path)}」，不会自动建立关联。</p>
              <label className="resume-field">需要核对的陈述<textarea className="resume-input" rows={3} placeholder="输入一句需要这份材料支持的描述" value={claimProbe} onChange={(event) => { setClaimProbe(event.target.value); setClaimResult('') }} /></label>
              <button type="button" className="btn secondary" disabled={!!busy || !claimProbe.trim()} onClick={() => void runClaimCheck()}>检查这句话</button>
              {claimResult && <p role="status">{claimResult}</p>}
            </details>}
            {linkTargetId && currentDetail && <details className="material-check-tool"><summary>关联到带入的经历</summary>
              <p>{vaultRows.find((row) => row.target_type === linkTargetType && row.target_id === linkTargetId)?.label || '从经历库带入的目标'}</p>
              <button type="button" className="btn secondary" disabled={!!busy || currentDetail.review_state !== 'REVIEWED'} onClick={() => void linkToTarget()}>确认关联到此经历</button>
            </details>}
          </>
        }}
      />
    </section>
  )
}
