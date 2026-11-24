import {Fragment,useState} from 'react'
import type {ReviewMark} from '../resume/reviewHighlights'

export function ClaimStatement({text,marks,id}:{text:string;marks:ReviewMark[];id:string}) {
  const [selection,setSelection] = useState('')
  const key = (m:ReviewMark) => [m.kind,m.start,m.end,text.slice(m.start,m.end)].join(':')
  const active = marks.find(m=>key(m)===selection)
  const noteId = 'review-note-'+id
  return <>
    <p className="claim-statement">{marks.map((m,i)=>{
      const quote=text.slice(m.start,m.end)
      const label=m.kind==='conflict'?'材料冲突':'待核对'
      return <Fragment key={key(m)}>{text.slice(i ? marks[i-1].end : 0,m.start)}
        <button type="button" className={'claim-ink claim-ink-'+m.kind} title={label+' · '+m.reason}
          aria-label={label+'：'+quote} aria-expanded={active===m} aria-controls={active===m?noteId:undefined}
          onClick={()=>setSelection(active===m?'':key(m))}>{quote}</button></Fragment>
    })}{text.slice(marks.at(-1)?.end ?? 0)}</p>
    {active && <div className="claim-ink-note" id={noteId} role="status">
      <strong>{active.kind==='conflict'?'材料冲突':'待核对'} · {text.slice(active.start,active.end)}</strong>
      <p>{active.reason}</p>
      {active.evidence && <blockquote>材料原文「{active.evidence}」</blockquote>}
    </div>}
  </>
}
