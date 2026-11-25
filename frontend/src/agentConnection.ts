export type AgentConnection = {id:string; token:string; ui_token:string; expires:number}
export type HarnessSetup = {
  python:string; connector_path:string; launcher_path:string; requirements_path:string
  install_python?:string; project_root?:string; shell?:'powershell'|'posix'
  mcp_installed:boolean; connector_exists:boolean; harness_command:string|null
  model:string; base_url:string; mcp_patch:string
  github_token_configured?:boolean; request_timeout_seconds?:number; session_timeout_seconds?:number
}

export function powershellQuote(value:string):string {
  return `'${value.replaceAll("'", "''")}'`
}

function shellCommand(setup:HarnessSetup, args:string[]):string {
  if (setup.shell === 'posix') return args.map(posixQuote).join(' ')
  return '& ' + args.map(powershellQuote).join(' ')
}

function posixQuote(value:string):string {
  return "'" + value.replaceAll("'", "'\"'\"'") + "'"
}

export function projectDirectoryCommand(setup:HarnessSetup):string | undefined {
  if (!setup.project_root) return undefined
  return setup.shell === 'posix' ? 'cd ' + posixQuote(setup.project_root)
    : 'Set-Location -LiteralPath ' + powershellQuote(setup.project_root)
}

export function installConnectorCommand(setup:HarnessSetup):string {
  const python = setup.install_python || setup.python
  return setup.shell === 'posix' ? `${posixQuote(python)} -m pip install -r './requirements-agent.txt'`
    : `& ${powershellQuote(python)} -m pip install -r '.\\requirements-agent.txt'`
}

export function launchHarnessCommand(setup:HarnessSetup, connection:AgentConnection, origin:string):string {
  const args = [setup.python, setup.launcher_path, '--url', origin, '--id', connection.id,
    '--model', setup.model, '--base-url', setup.base_url]
  if (setup.harness_command) args.push('--harness', setup.harness_command)
  return shellCommand(setup, args)
}

export function agentMcpConfig(setup:HarnessSetup, connection:AgentConnection, origin:string) {
  return {mcpServers:{applyguard:{command:setup.python, args:[setup.connector_path], env:{
    APPLYGUARD_AGENT_URL:origin, APPLYGUARD_AGENT_ID:connection.id, APPLYGUARD_AGENT_TOKEN:connection.token,
  }}}}
}

export function connectionStage(connection:AgentConnection|null, paired:boolean, now=Date.now(), progress?:AgentProgress|null):string {
  if (!connection) return '尚未授权'
  if (now >= connection.expires * 1000) return '授权已过期'
  if (progress?.run_state==='timed_out') return '检索已超时'
  if (progress?.run_state==='failed') return '检索会话异常结束'
  if (progress?.submitted) return '已回传引用，待确认'
  if (progress?.run_state==='finished') return progress.candidates ? '已找到原文，可核对导入' : '会话已结束，暂无回传'
  if (progress?.stage==='searching') return '正在搜索材料'
  if (progress?.stage==='searched') return '已搜索，等待回传'
  return paired ? '已配对，可让 Agent 搜索材料' : '等待 Agent 连接'
}

export function appendAllowedFolder(current: string, selected: string): string {
  const identity = (path: string) => {
    const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '')
    return /^[a-z]:/i.test(normalized) || normalized.startsWith('//') ? normalized.toLowerCase() : normalized
  }
  const paths = current.split('\n').map(path => path.trim()).filter(Boolean)
  const path = selected.trim()
  if (!path || paths.some(existing => identity(existing) === identity(path))) return paths.join('\n')
  if (paths.length >= 5) throw new Error('最多选择 5 个文件夹，请先移除不需要的目录。')
  return [...paths, path].join('\n')
}

export type AgentProgress = {
  stage:'waiting'|'task_received'|'searching'|'searched'|'search_failed'|'submitted'
  updated_at:number; run_state:'started'|'finished'|'failed'|'timed_out'|null
  candidates:number; submitted:number; failure_reason?:string
}

export function connectionDetail(progress:AgentProgress|null, now=Date.now()):string {
  if (!progress) return ''
  const returned=progress.submitted ? `已回传 ${progress.submitted} 条引用，可先核对。` : '尚未回传引用。'
  if (progress.run_state==='timed_out') return `本次检索已超时，${returned}请检查终端提示和模型服务后重新执行启动命令。`
  if (progress.run_state==='failed') return `Harness 会话异常结束，${returned}${progress.failure_reason||'请检查环境后重试。'}`
  if (progress.run_state==='finished') return progress.submitted ? returned+'会话已结束；确认来源后才能导入。' : progress.candidates ? `未回传引用解释，但已找到 ${progress.candidates} 段原文。核对下方来源、归属和数字后可直接导入。` : '会话已结束，未回传引用。请核对任务和授权来源后重试。'
  let detail=progress.submitted ? returned : progress.stage==='searching' ? '正在搜索已授权材料。'
    : progress.stage==='searched' ? `已找到 ${progress.candidates} 个候选片段，等待 Harness 回传引用。`
    : progress.stage==='search_failed' ? '材料搜索失败，请检查授权来源和终端提示。'
    : progress.stage==='task_received' ? '已领取任务，等待发起材料搜索。'
    : progress.run_state==='started' ? 'Harness 正在启动并请求模型。' : ''
  if (detail && progress.run_state==='started' && now-progress.updated_at*1000>=60000)
    detail+=' 当前阶段已等待超过 60 秒，请查看终端；会话超时后会自动停止。'
  return detail
}
