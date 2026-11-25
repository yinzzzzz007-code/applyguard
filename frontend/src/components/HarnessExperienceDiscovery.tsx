import {useState} from 'react'
import {getApiClient} from '../api/client'
import {AgentConnector} from './AgentConnector'

export function HarnessExperienceDiscovery() {
  const [open,setOpen]=useState(false)
  return <section className="item-block" aria-label="Harness 二次补充经历">
    <h3>还有可能遗漏的相关经历？</h3>
    <p>让 Harness 按当前岗位再搜索已授权的文件夹或仓库，生成可编辑的经历概括。在本页选择加入草稿，后面仍可修改或删除。</p>
    <button type="button" className="btn secondary" aria-expanded={open} onClick={()=>setOpen(value=>!value)}>
      {open?'收起二次查找':'让 Harness 二次查找并补充经历'}
    </button>
    {open&&<AgentConnector inlineDiscovery ensureWorkspace={async()=>{
      const api=getApiClient()
      const listed=await api.listEvidenceWorkspaces()
      const stored=sessionStorage.getItem('applyguard.evidence.workspaceId')
      const existing=listed.data?.find(item=>item.workspace_id===stored)||listed.data?.[0]
      if(existing)return existing.workspace_id
      const created=await api.createEvidenceWorkspace('本地证据工作区')
      return created.data?.workspace_id||null
    }} onImported={async()=>{window.dispatchEvent(new Event('applyguard:evidence-changed'))}}/>}
  </section>
}
