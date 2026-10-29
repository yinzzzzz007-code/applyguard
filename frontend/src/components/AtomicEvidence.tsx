import type { GroundingClaimResult } from '../api/types'

const LABEL = {SUPPORTED:'支持',CONTRADICTED:'矛盾',INSUFFICIENT:'证据不足'}

export function AtomicEvidence({result}: {result?: GroundingClaimResult}) {
  if (!result) return null
  return <div className="evidence-box atomic-evidence">
    <h4>逐事实依据</h4>
    {result.atoms.length > 0 && !result.complete && <p className="warn-text">整句覆盖检查未通过；即使部分事实有支持，也不能通过整句核验。</p>}
    {!result.atoms.length && <p className="muted">仅完成检索或核验未完成；尚无可通过的原子事实结论。</p>}
    {result.atoms.map(atom => <div className="atomic-item" key={atom.atom_id}>
      <p><strong className={`atomic-relation ${atom.relation.toLowerCase()}`}>{LABEL[atom.relation]}</strong> {atom.text}</p>
      <p className="muted">{atom.reason}</p>
      {atom.citations.map((citation,index) => <blockquote key={`${citation.source_id}-${index}`}>
        <p>{citation.quote}</p>
        <small>{citation.evidence_id} · 原文字符 [{citation.start}, {citation.end})
          {citation.file_version != null && ` · 文件 v${citation.file_version}`}
          {citation.positions?.map((p,i) => <span key={i}> · {p.page ? `第${p.page}页` : ''} {p.line_start != null ? `行${p.line_start}–${p.line_end}` : ''}</span>)}
        </small>
      </blockquote>)}
    </div>)}
    <details><summary>查看本次检索原文（{result.retrieved_sources.length}块）</summary>
      {result.retrieved_sources.map((source,index) => <div className="callout" key={`${source.source_id}-${index}`}>
        <p><strong>{source.title}</strong> · {source.evidence_id}</p>
        <p className="muted">{source.file_version != null ? `文件 v${source.file_version} · ` : ''}原文指纹 {source.sha256.slice(0,12)}</p>
        <p style={{whiteSpace:'pre-wrap'}}>{source.text}</p>
      </div>)}
    </details>
  </div>
}
