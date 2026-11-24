import {useEffect,useId,useRef,type ComponentProps} from 'react'
import {GUIDE_UPDATE,requestGuide,type GuideRequirement} from '../../guide'
export type ActionButtonProps=ComponentProps<'button'>&{disabledReason?:string;guideRequirements?:GuideRequirement[]}
export function ActionButton({disabled,disabledReason,guideRequirements,children,...props}:ActionButtonProps) {
  const id=useId(),root=useRef<HTMLSpanElement>(null)
  const requirements=disabled?(guideRequirements?.length?guideRequirements:[{id:'status',label:disabledReason||'此操作暂不可用，请检查本页提示。',selector:`[data-guide-note="${CSS.escape(id)}"]`}]):[]
  const signature=JSON.stringify(requirements)
  useEffect(()=>{window.dispatchEvent(new CustomEvent(GUIDE_UPDATE,{detail:{owner:id,requirements:JSON.parse(signature)}}))},[id,signature])
  useEffect(()=>()=>{window.dispatchEvent(new CustomEvent(GUIDE_UPDATE,{detail:{owner:id,requirements:[]}}))},[id])
  function guide(){if(root.current&&disabled)requestGuide(id,root.current,requirements)}
  if(!disabled)return <button {...props}>{children}</button>
  const description=[props['aria-describedby'],id].filter(Boolean).join(' ')
  return <span ref={root} className="disabled-action" data-disabled-reason={disabledReason} title={disabledReason || '此操作暂不可用，请检查本页提示。'}>
    <button {...props} disabled aria-describedby={description}>{children}</button>
    <small className="disabled-action-reason" data-guide-note={id} id={id} role="note">{disabledReason||'此操作暂不可用，请检查本页提示。'}</small>
    <button type="button" className="disabled-action-help" onClick={guide}>查看原因与补全引导</button>
  </span>
}
