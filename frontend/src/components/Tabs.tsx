import type { KeyboardEvent } from 'react'

export function Tabs({id,label,items,value,onChange,panelId}:{id:string;label:string;items:{id:string;label:string}[];value:string;onChange:(value:string)=>void;panelId:string}) {
  function onKey(event:KeyboardEvent<HTMLDivElement>) {
    const current = items.findIndex(item => item.id === value)
    let next = current
    if (event.key === 'ArrowRight') next = (current + 1) % items.length
    else if (event.key === 'ArrowLeft') next = (current - 1 + items.length) % items.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = items.length - 1
    else return
    event.preventDefault()
    onChange(items[next].id)
    event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus()
  }
  return <div className="work-tabs" role="tablist" aria-label={label} onKeyDown={onKey}>
    {items.map(item => <button type="button" key={item.id} role="tab" id={id+'-'+item.id}
      aria-selected={value === item.id} aria-controls={panelId} tabIndex={value === item.id ? 0 : -1}
      onClick={() => onChange(item.id)}>{item.label}</button>)}
  </div>
}
