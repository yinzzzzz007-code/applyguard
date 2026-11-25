import type {GroundingClaimResult} from '../api/types'

export function ConflictSummary({result}:{result:GroundingClaimResult}) {
  const conflicts=result.atoms.filter(atom=>atom.relation==='CONTRADICTED'&&atom.citations.some(c=>c.quote.trim()&&c.end>c.start))
  if(!conflicts.length)return null
  return <section className="claim-conflicts" aria-label="简历与材料冲突对照">
    <h4>发现 {conflicts.length} 处材料冲突</h4>
    {conflicts.map(atom=><div key={atom.atom_id} className="claim-conflict-item">
      <div className="claim-conflict-grid"><div><strong>简历中写的是</strong><p><mark className="claim-ink claim-ink-conflict">{atom.claim_excerpt||atom.claim_spans?.map(s=>s.quote).join('；')||atom.text}</mark></p></div>
        <div><strong>材料原文写的是</strong>{atom.citations.filter(c=>c.quote.trim()&&c.end>c.start).map((citation,index)=>{
          const source=result.retrieved_sources.find(s=>s.source_id===citation.source_id)
          const characters=Array.from(source?.text||'')
          const located=characters.slice(citation.start,citation.end).join('')===citation.quote
          return <div key={index}><p><mark className="claim-ink claim-ink-pending">{citation.quote}</mark></p><p className="muted">{source?.title||citation.evidence_id}{citation.positions?.map((p,i)=><span key={i}> · {p.page?`第 ${p.page} 页`:''}{p.line_start!=null?`第 ${p.line_start}–${p.line_end??p.line_start} 行`:''}</span>)}</p>
            {located&&<details><summary>定位材料原文与上下文</summary><p className="claim-source-context">{characters.slice(Math.max(0,citation.start-120),citation.start).join('')}<mark>{citation.quote}</mark>{characters.slice(citation.end,citation.end+120).join('')}</p></details>}
          </div>
        })}</div></div><p>{atom.reason}</p>
    </div>)}
    <p className="muted">请核对统计口径和版本，再选择编辑或排除。保留个人稿会继续记录这处冲突。</p>
  </section>
}
