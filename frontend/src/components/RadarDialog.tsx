import {useEffect,useRef,type ReactNode} from 'react'
import {Button} from './ui/button'

export function RadarDialog({title,onClose,children,showClose=true}:{title:string;onClose:()=>void;children:ReactNode;showClose?:boolean}) {
  const dialog=useRef<HTMLDialogElement>(null)
  useEffect(()=>{
    const element=dialog.current
    const previous=document.activeElement instanceof HTMLElement?document.activeElement:null
    element?.showModal()
    return ()=>{element?.close();previous?.focus()}
  },[])
  return <dialog className="radar-summary-dialog" ref={dialog} aria-labelledby="radar-summary-title" onCancel={onClose} onClick={event=>{if(event.target===event.currentTarget){const r=event.currentTarget.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)onClose()}}}>
    <header><h3 id="radar-summary-title">{title}</h3>{showClose&&<Button variant="secondary" onClick={onClose} autoFocus aria-label="关闭摘要弹窗">关闭</Button>}</header>
    {children}
  </dialog>
}
