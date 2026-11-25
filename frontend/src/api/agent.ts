export async function agentUi(body:object, timeout=45000) {
  const response=await fetch('/api/v1/agent/ui',{method:'POST',headers:{'Content-Type':'application/json','X-ApplyGuard-UI':'1'},body:JSON.stringify(body),signal:AbortSignal.timeout(timeout)})
  const data=await response.json().catch(()=>{throw new Error('后端返回无效响应，请确认 ApplyGuard 服务正在运行。')})
  if(!response.ok)throw new Error(data.error?.message||'请求失败，请重试。')
  return data
}
