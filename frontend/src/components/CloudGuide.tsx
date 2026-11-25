import {useEffect,useRef,useState} from 'react'
import {Link,useLocation} from 'react-router-dom'
import {useDemo} from '../context/DemoContext'
import {GUIDE_COMPLETE,GUIDE_REQUEST,GUIDE_UPDATE,guideForPage,reopenGuide,orderRequirements,completeGuideStep,type GuideProgress,type GuideRequest} from '../guide'
const KEY='applyguard.cloud-guide.v1'
type Progress=GuideProgress
function read():Progress {try{const value=JSON.parse(localStorage.getItem(KEY)||'null');return {dismissed:value?.dismissed===true,completed:Array.isArray(value?.completed)?value.completed.filter((id:unknown)=>typeof id==='string'):[]}}catch{return {dismissed:false,completed:[]}}}
export function CloudGuide() {
  const {pathname}=useLocation()
  const {loadingWorkflow,workflow,resumeForm,reviewDrafts}=useDemo()
  const [progress,setProgress]=useState(read)
  const [request,setRequest]=useState<(GuideRequest&{pathname:string})|null>(null)
  const [position,setPosition]=useState({x:24,y:160})
  const [target,setTarget]=useState<HTMLElement|null>(null)
  const [expanded,setExpanded]=useState(false)
  const [finished,setFinished]=useState<{pathname:string;id:string}|null>(null)
  const lastScroll=useRef('')
  const bubble=useRef<HTMLElement|null>(null)
  const currentRequest=request?.pathname===pathname?request:null
  const requirement=currentRequest?.requirements[0]
  const step=guideForPage(pathname,finished?.pathname===pathname?finished.id:undefined,{hasWorkflow:!!workflow,hasForm:!!resumeForm,formDirty:!!resumeForm?.dirty,claimCount:workflow?.resume_claims.length??0,editingIds:Object.keys(reviewDrafts),historyReplay:!!workflow?._historyReplay})
  const visible=!loadingWorkflow&&!progress.dismissed&&(!!requirement||!!step)
  const showMessage=expanded||!!currentRequest
  const label=requirement?.label??step?.label??''
  const href=currentRequest?requirement?.href:(step?.href!==pathname?step?.href:undefined)
  const selector=currentRequest
    ?requirement?.selector??(href&&href!==pathname?`a[data-guide-route="${href}"]`:undefined)
    :(step?.href===pathname?step.selector:step?`a[data-guide-route="${step.href}"]`:undefined)
  const key=currentRequest?pathname+':'+currentRequest.owner+':'+(requirement?.id??''):pathname+':'+(step?.id??'')
  useEffect(()=>{try{localStorage.setItem(KEY,JSON.stringify(progress))}catch{/* optional preference */}},[progress])
  useEffect(()=>{
    const begin=(event:Event)=>{
      const next=(event as CustomEvent<GuideRequest>).detail
      const sorted=orderRequirements(next.requirements,item=>{
        const node=item.selector?document.querySelector<HTMLElement>(item.selector):null
        if(!node)return Number.POSITIVE_INFINITY
        const box=node.getBoundingClientRect()
        return Math.hypot(box.x+box.width/2+scrollX-next.origin.x,box.y+box.height/2+scrollY-next.origin.y)
      })
      setProgress(reopenGuide);setExpanded(false);setRequest({...next,pathname,requirements:sorted})
    }
    const update=(event:Event)=>{
      const next=(event as CustomEvent<{owner:string;requirements:GuideRequest['requirements']}>).detail
      setRequest(current=>{
        if(current?.owner!==next.owner)return current
        const remaining=current.requirements.filter(item=>next.requirements.some(v=>v.id===item.id)).map(item=>next.requirements.find(v=>v.id===item.id)!)
        const added=next.requirements.filter(item=>!remaining.some(v=>v.id===item.id))
        return remaining.length+added.length?{...current,requirements:[...remaining,...added]}:null
      })
    }
    const complete=(event:Event)=>{const id=(event as CustomEvent<string>).detail;setProgress(value=>({...value,completed:[...new Set([...value.completed,id])]}));setFinished({pathname,id});setRequest(null);setExpanded(false)}
    const evidenceLinked=()=>completeGuideStep('evidence')
    const reopen=()=>{setProgress(reopenGuide);setRequest(null);setFinished(null);setExpanded(true);lastScroll.current=''}
    window.addEventListener(GUIDE_REQUEST,begin);window.addEventListener(GUIDE_UPDATE,update);window.addEventListener(GUIDE_COMPLETE,complete);window.addEventListener('applyguard:guide-open',reopen);window.addEventListener('applyguard:evidence-linked',evidenceLinked)
    return()=>{window.removeEventListener(GUIDE_REQUEST,begin);window.removeEventListener(GUIDE_UPDATE,update);window.removeEventListener(GUIDE_COMPLETE,complete);window.removeEventListener('applyguard:guide-open',reopen);window.removeEventListener('applyguard:evidence-linked',evidenceLinked)}
  },[pathname])
  useEffect(()=>{setRequest(null);setFinished(null);setExpanded(false);lastScroll.current=''},[pathname])
  useEffect(()=>{
    if(!visible)return
    let frame=0
    const locate=()=>{
      cancelAnimationFrame(frame)
      frame=requestAnimationFrame(()=>{
        const candidates=selector?[...document.querySelectorAll<HTMLElement>(selector)]:[]
        if(currentRequest)for(const node of candidates){
          for(let parent=node.parentElement;parent;parent=parent.parentElement){
            if(parent instanceof HTMLDetailsElement)parent.open=true
          }
        }
        const item=candidates.find(node=>node.getClientRects().length>0)
          ??(currentRequest ? null : document.querySelector<HTMLElement>('#workspace-main h2'))
        setTarget(current=>current===item?current:item)
        if(item&&lastScroll.current!==key){
          lastScroll.current=key
          if(currentRequest)item.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'})
        }
      })
    }
    locate()
    const observer=new MutationObserver(locate)
    const content=document.getElementById('workspace-main')
    if(content)observer.observe(content,{subtree:true,childList:true})
    return()=>{cancelAnimationFrame(frame);observer.disconnect()}
  },[visible,selector,key,pathname,currentRequest])
  useEffect(()=>{
    if(!visible)return
    const place=()=>{
      const box=target?.getBoundingClientRect()
      const width=Math.min(288,innerWidth-32)
      const height=bubble.current?.offsetHeight || 54
      const gap=14
      let x=box ? box.right-width : innerWidth-width-gap
      let y=box ? box.top-height-gap : innerHeight-height-gap
      if(box && showMessage && box.right+width+gap*2<=innerWidth){
        x=box.right+gap
        y=box.top
      } else if(box && y<gap){
        if(box.bottom+gap+height<=innerHeight) y=box.bottom+gap
        else if(box.right+gap+width<=innerWidth || box.left>=gap+width){
          x=box.left>=gap+width ? box.left-gap-width : box.right+gap
          y=box.top
        } else y=box.top>innerHeight-box.bottom ? gap : innerHeight-height-gap
      }
      setPosition({x:Math.max(gap,Math.min(innerWidth-width-gap,x)),y:Math.max(gap,Math.min(innerHeight-height-gap,y))})
    }
    if(showMessage)target?.classList.add('cloud-guide-target');place()
    const observer=new ResizeObserver(place)
    if(bubble.current)observer.observe(bubble.current)
    if(target)observer.observe(target)
    window.addEventListener('scroll',place,true);window.addEventListener('resize',place)
    return()=>{observer.disconnect();target?.classList.remove('cloud-guide-target');window.removeEventListener('scroll',place,true);window.removeEventListener('resize',place)}
  },[visible,target,showMessage])
  if(!visible)return null
  return <aside ref={bubble} className="cloud-guide" data-guide-step={requirement?.id??step?.id} data-guide-mode={currentRequest?'requirement':'page'} aria-label="小云朵操作引导" style={{left:position.x,top:position.y}}>
    <button type="button" className="cloud-guide-mascot" aria-label="查看本页引导" aria-expanded={showMessage} title="查看本页下一步" onClick={()=>{if(showMessage){setRequest(null);setExpanded(false)}else setExpanded(true)}}><svg aria-hidden="true" viewBox="0 0 100 82"><path fill="#87CEEB" stroke="#65b5d5" strokeWidth="1" d="M24 18C23 0 48-5 59 9C76 3 91 17 88 32C104 42 99 65 84 67C80 83 59 85 48 76C32 86 14 77 15 64C-3 62-5 40 8 31C8 23 15 18 24 18Z"/><ellipse cx="42" cy="38" rx="4" ry="7" fill="#182330"/><ellipse cx="61" cy="38" rx="4" ry="7" fill="#182330"/></svg></button>
    {showMessage&&<div className="cloud-guide-message"><button className="cloud-guide-close" type="button" aria-label="关闭云朵引导" onClick={()=>{setProgress(value=>({...value,dismissed:true}));setRequest(null)}}>×</button>
      <strong>{currentRequest?'请处理蓝框内的项目':step?.href===pathname?'本页指引':'下一步'}</strong><p role="status">{label}</p>
      {href&&<Link to={href}>打开对应页面 →</Link>}
      {currentRequest&&currentRequest.requirements.length>1&&<small>还有 {currentRequest.requirements.length-1} 项，补齐当前项后继续引导。</small>}
    </div>}
  </aside>
}
