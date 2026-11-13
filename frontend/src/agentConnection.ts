export type AgentConnection = {id:string; token:string; ui_token:string; expires:number}
export type HarnessSetup = {
  python:string; connector_path:string; launcher_path:string; requirements_path:string
  mcp_installed:boolean; connector_exists:boolean; harness_command:string|null
  model:string; base_url:string; mcp_patch:string
}

export function powershellQuote(value:string):string {
  return `'${value.replaceAll("'", "''")}'`
}

export function installConnectorCommand(setup:HarnessSetup):string {
  return `& ${powershellQuote(setup.python)} -m pip install -r ${powershellQuote(setup.requirements_path)}`
}

export function launchHarnessCommand(setup:HarnessSetup, connection:AgentConnection, origin:string):string {
  const args = [setup.python, setup.launcher_path, '--url', origin, '--id', connection.id,
    '--model', setup.model, '--base-url', setup.base_url]
  if (setup.harness_command) args.push('--harness', setup.harness_command)
  return '& ' + args.map(powershellQuote).join(' ')
}

export function agentMcpConfig(setup:HarnessSetup, connection:AgentConnection, origin:string) {
  return {mcpServers:{applyguard:{command:setup.python, args:[setup.connector_path], env:{
    APPLYGUARD_AGENT_URL:origin, APPLYGUARD_AGENT_ID:connection.id, APPLYGUARD_AGENT_TOKEN:connection.token,
  }}}}
}

export function connectionStage(connection:AgentConnection|null, paired:boolean, now=Date.now()):string {
  if (!connection) return '尚未授权'
  if (now >= connection.expires * 1000) return '授权已过期'
  return paired ? '已配对，可让 Agent 搜索材料' : '等待 Agent 连接'
}
