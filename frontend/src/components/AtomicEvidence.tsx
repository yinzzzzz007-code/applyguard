import type { GroundingClaimResult } from '../api/types'

const LABEL = {SUPPORTED:'支持',CONTRADICTED:'矛盾',INSUFFICIENT:'证据不足'}

export function AtomicEvidence({result}: {result?: GroundingClaimResult}) {
  if (!result) return null
  if (result.verification_scope === 'personal') return <div className="evidence-box"><p>{result.scope_notice || '个人资料按填写使用，不进行SAG核验或AI润色。'}</p></div>
  const facts=result.material_status==='no_related_material' ? [] : result.atoms
  return <div className="evidence-box atomic-evidence">
    <h4>逐事实依据</h4>
    {result.material_status==='no_related_material'&&<p><strong>本次核验未读到这条经历的关联原件。</strong></p>}
    {result.excluded_links?.map(link=><p key={link.evidence_id}>已排除 {link.filename} · {link.reason}</p>)}
    {facts.length > 0 && !result.complete && <p className="warn-text">整句覆盖检查未通过；即使部分事实有支持，也不能通过整句核验。</p>}
    {!facts.length && result.material_status!=='no_related_material' && <p className="muted">仅完成检索或核验未完成；尚无可通过的原子事实结论。</p>}
    {facts.map(atom => <div className="atomic-item" key={atom.atom_id}>
      <p><strong className={`atomic-relation ${atom.relation.toLowerCase()}`}>{LABEL[atom.relation]}</strong> {atom.text}</p>
      {'claim_spans' in atom && atom.claim_spans?.map(span=><p key={span.start}><strong>简历原文</strong> {atom.relation==='SUPPORTED' && atom.citations.some(c=>c.quote.trim() && c.end>c.start)
        ? <q>{span.quote}</q> : <mark className={'claim-ink claim-ink-'+(atom.relation==='CONTRADICTED' && atom.citations.some(c=>c.quote.trim() && c.end>c.start)?'conflict':'pending')}>{span.quote}</mark>}（位置 {span.start}–{span.end}）</p>)}
      {'anchor_reason' in atom&&atom.anchor_reason&&<p>未定位到正文 · {({'empty_excerpt':'摘录为空','ambiguous_excerpt':'正文重复出现','nonverbatim_without_phrase_id':'改述未绑定正文片段','invalid_phrase_id':'返回的正文编号无效'} as Record<string,string>)[atom.anchor_reason]||atom.anchor_reason}</p>}
      <p className="muted">{atom.reason}</p>
      {atom.citations.map((citation,index) => <blockquote key={`${citation.source_id}-${index}`}>
        <p><strong>材料原文</strong> {citation.quote}</p>
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
