import { useState } from 'react'
import type { EvidenceMatchItem, ParsedRequirement } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { claimsFromResumeForm, addDraftClaim } from '../resume/draftSelection'

type Choices = { frameworks: Record<string, string>; manual: Record<string, string[]> }
const empty = (): Choices => ({frameworks: {}, manual: {}})
function read(key: string): Choices {
  try {
    const v = JSON.parse(localStorage.getItem(key) || 'null')
    return v && typeof v.frameworks === 'object' && v.frameworks && typeof v.manual === 'object' && v.manual ? v : empty()
  } catch { return empty() }
}

export function ExperienceCandidates({ requirement, matches }: {requirement: ParsedRequirement; matches: EvidenceMatchItem[]}) {
  const {workflow, resumeForm, patchWorkflow} = useDemo()
  const key = JSON.stringify(['applyguard.related.v1', workflow?.candidate_id, workflow?.parsed_jd.jd_id])
  const [choices, setChoices] = useState(() => read(key))
  const [manualId, setManualId] = useState('')
  const [editing, setEditing] = useState('')
  const [other, setOther] = useState('')
  const [notice, setNotice] = useState('')
  if (!workflow) return null
  const available = claimsFromResumeForm(resumeForm?.candidateId === workflow.candidate_id ? resumeForm : null)
  const phrase = requirement.evidence_text
  const manual = choices.manual[phrase] || []
  const ids = new Set(matches.flatMap(row => row.claim_ids))
  const remaining = available.filter(x => !ids.has(x.claim_id) && !manual.includes(x.claim_id))
  function update(change: (current: Choices) => Choices) {
    const next = change(read(key))
    try {localStorage.setItem(key, JSON.stringify(next)); setChoices(next); setNotice('')}
    catch {setNotice('浏览器未能保存这次选择，请检查本地存储后重试。')}
  }
  function changeManual(id: string, include: boolean) {
    update(v => ({...v, manual: {...v.manual, [phrase]: include
      ? [...new Set([...(v.manual[phrase] || []), id])] : (v.manual[phrase] || []).filter(x => x !== id)}}))
    setManualId('')
  }
  function add(id: string) {
    const claim = available.find(c => c.claim_id === id)
    if (!claim || !workflow) return
    try {patchWorkflow(addDraftClaim(workflow, claim)); setNotice('已加入当前简历正文。')}
    catch (error) {setNotice(error instanceof Error ? error.message : '加入失败，请重试。')}
  }
  function addButton(id: string) {
    if (!available.some(x => x.claim_id === id)) return null
    return workflow?.resume_claims.some(x => x.claim_id === id) ? <span className="muted">已在正文中</span>
      : <button type="button" className="btn secondary" onClick={() => add(id)}>加入简历正文</button>
  }
  return <section className="stack" aria-label="相关经历">
    {!!requirement.alternatives?.length && <p>任选一种框架即可 · {requirement.alternatives.join(' / ')}</p>}
    {requirement.priority === 'general' && <p className="muted">通用能力，排序权重较低。</p>}
    {matches.filter(m => m.lead).map(m => {
      const lead = m.lead!
      const frameworkKey = JSON.stringify([m.experience_id,lead.title,lead.quote])
      const answer = choices.frameworks[frameworkKey]
      function confirm(value: string) {
        update(v => ({...v, frameworks: {...v.frameworks, [frameworkKey]: value}}))
        setEditing(''); setOther('')
      }
      return <article key={m.experience_id} className="item-block em-detail-card">
        <h4>{lead.title}</h4>
        <p><strong>为什么相关</strong> · {lead.kind === 'framework' ? '项目涉及训练，具体框架待确认' :
          lead.kind === 'related' ? '可迁移的经验，具体任务待确认' : '经历原文提到相关工作'}{lead.terms.length ? ' · '+lead.terms.join('、') : ''}</p>
        <blockquote>{lead.quote}</blockquote>
        {!!lead.pending_context?.length && <p><strong>还需确认</strong> · {lead.pending_context.join('、')}</p>}
        <p><strong>材料支持到哪里</strong> · {lead.material_quote ? '已定位同项目材料中的相关原句' : '当前依据为经历记录，暂无对应的材料原句'}</p>
        {lead.material_quote && <details><summary>查看材料原句</summary><blockquote>{lead.material_quote}</blockquote><small>{lead.material_reference}</small></details>}
        {!!m.conflicts?.length && <p role="alert">材料有冲突，请在陈述核验中处理。</p>}
        {lead.kind === 'framework' && <div>{answer && editing !== frameworkKey ?
          <p>{answer === '暂不确定' ? '已暂缓确认' : '本人已确认 · '+answer} <button type="button" className="btn secondary" onClick={() => setEditing(frameworkKey)}>更改</button></p>
          : <><p>这项训练实际用了哪个框架？</p><div className="btn-row">
            {(requirement.alternatives?.length ? requirement.alternatives : ['PyTorch','TensorFlow','JAX']).map(v => <button type="button" key={v} className="btn secondary" onClick={() => confirm(v)}>{v}</button>)}
            <button type="button" className="btn secondary" onClick={() => {setEditing(frameworkKey+'-other'); setOther('')}}>其他</button>
            <button type="button" className="btn secondary" onClick={() => confirm('暂不确定')}>暂不确定</button></div></>}
          {editing === frameworkKey+'-other' && <label>其他框架 <input value={other} maxLength={80} onChange={e => setOther(e.target.value)}/>
            <button type="button" className="btn secondary" disabled={!other.trim()} onClick={() => confirm(other.trim())}>确认框架</button></label>}</div>}
        {addButton(m.claim_ids[0])}
      </article>
    })}
    {!matches.length && !manual.length && <p>尚未找到相关项目，可以从经历库补选。</p>}
    {available.filter(x => manual.includes(x.claim_id) && !ids.has(x.claim_id)).map(x => <article className="item-block" key={x.claim_id}>
      <h4>{x.experienceTitle}</h4><p>本人补选 · 材料待核对</p>{addButton(x.claim_id)} <button type="button" className="btn secondary" onClick={() => changeManual(x.claim_id,false)}>撤销关联</button></article>)}
    {!!remaining.length && <label>从经历库补选 <select value={manualId} onChange={e => setManualId(e.target.value)}><option value="">选择相关经历</option>
      {remaining.map(x => <option key={x.claim_id} value={x.claim_id}>{x.experienceTitle}</option>)}</select>
      {manualId && <button type="button" className="btn secondary" onClick={() => changeManual(manualId,true)}>关联到这项要求</button>}</label>}
    {notice && <p role="status">{notice}</p>}
  </section>
}
