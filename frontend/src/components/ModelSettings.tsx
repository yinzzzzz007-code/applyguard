import {useState} from 'react'

type Settings = {base_url:string; model:string; complex_model:string; key_configured:boolean}

export function ModelSettings() {
  const [open,setOpen]=useState(false)
  const [form,setForm]=useState<Settings>({base_url:'',model:'',complex_model:'',key_configured:false})
  const [key,setKey]=useState('')
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  async function load() {
    setOpen(true);setMessage('')
    try {
      const response=await fetch('/api/v1/model-settings')
      if(!response.ok) throw new Error('无法读取模型配置。')
      setForm(await response.json())
    } catch(e) {setMessage(e instanceof Error?e.message:'无法连接本地后端。')}
  }
  async function save() {
    setBusy(true);setMessage('')
    try {
      const response=await fetch('/api/v1/model-settings',{method:'POST',headers:{'Content-Type':'application/json','X-ApplyGuard-UI':'1'},body:JSON.stringify({...form,api_key:key})})
      const data=await response.json()
      if(!response.ok)throw new Error(data.error?.message||'保存失败。')
      setForm(data);setKey('');setMessage('已保存。新的模型请求将使用此配置。')
    } catch(e) {setMessage(e instanceof Error?e.message:'无法连接本地后端。')}
    finally {setBusy(false)}
  }
  return <div className="model-settings">
    <button type="button" className="text-action" onClick={()=>open?setOpen(false):void load()} aria-expanded={open}>模型设置</button>
    {open&&<section className="model-settings-panel" aria-label="模型设置">
      <h2>模型设置</h2><p>润色和核验使用你配置的云端服务。密钥保存在本机。</p>
      <label>服务地址<input className="resume-input" value={form.base_url} placeholder="https://.../v1" onChange={e=>setForm({...form,base_url:e.target.value})}/></label>
      <label>模型名称<input className="resume-input" value={form.model} onChange={e=>setForm({...form,model:e.target.value})}/></label>
      <label>复杂任务模型（可选）<input className="resume-input" value={form.complex_model} onChange={e=>setForm({...form,complex_model:e.target.value})}/></label>
      <label>API Key<input type="password" autoComplete="off" className="resume-input" value={key} placeholder={form.key_configured?'已配置，留空保留':'输入密钥'} onChange={e=>setKey(e.target.value)}/></label>
      <div className="btn-row"><button className="btn primary" type="button" disabled={busy} onClick={()=>void save()}>{busy?'保存中…':'保存设置'}</button><button className="btn secondary" type="button" onClick={()=>{setKey('');setOpen(false)}}>关闭</button></div>
      {message&&<p role="status">{message}</p>}
    </section>}
  </div>
}
