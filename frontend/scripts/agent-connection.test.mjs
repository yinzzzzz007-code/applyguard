import assert from 'node:assert/strict'
import {test} from 'node:test'
import {agentMcpConfig, connectionStage, installConnectorCommand, launchHarnessCommand, projectDirectoryCommand} from '../src/agentConnection.ts'

const setup={python:"C:\\Sam's folder\\python.exe",launcher_path:'D:\\项目\\connect_harness.py',connector_path:'D:\\项目\\agent_mcp.py',model:'gemini-3.1-flash-lite-preview',base_url:'https://api.chatanywhere.tech/v1',harness_command:'C:\\Harness\\dsh.cmd'}
const connection={id:'grant-1',token:'private-agent-token',ui_token:'private-ui-token',expires:100}

test('installation is project relative and the directory command is separately copyable',()=>{
  const local={...setup, project_root:"D:\\Sam's project", install_python:'.\\.venv\\Scripts\\python.exe'}
  assert.equal(installConnectorCommand(local), "& '.\\.venv\\Scripts\\python.exe' -m pip install -r '.\\requirements-agent.txt'")
  assert.equal(projectDirectoryCommand(local), "Set-Location -LiteralPath 'D:\\Sam''s project'")
  assert.equal(installConnectorCommand({...local,install_python:setup.python}),
    "& 'C:\\Sam''s folder\\python.exe' -m pip install -r '.\\requirements-agent.txt'")
})

test('POSIX installation and launch quote apostrophes in paths',()=>{
  const local={...setup, shell:'posix', project_root:"/tmp/Sam's project", python:"/tmp/Sam's project/.venv/bin/python",
    launcher_path:"/tmp/Sam's project/scripts/connect_harness.py", install_python:'./.venv/bin/python'}
  assert.equal(installConnectorCommand(local), "'./.venv/bin/python' -m pip install -r './requirements-agent.txt'")
  assert.equal(projectDirectoryCommand(local), `cd '/tmp/Sam'"'"'s project'`)
  assert.ok(launchHarnessCommand(local,connection,'http://127.0.0.1:5173').startsWith(`'/tmp/Sam'"'"'s project/.venv/bin/python' `))
})

test('launch uses actual paths and literal PowerShell arguments without capability secrets',()=>{
  const command=launchHarnessCommand(setup,connection,'http://127.0.0.1:5173')
  assert.ok(command.includes("Sam''s folder"))
  assert.ok(command.includes(setup.launcher_path))
  assert.ok(command.includes(setup.model))
  assert.ok(!command.includes(connection.token))
  assert.ok(!command.includes(connection.ui_token))
  assert.ok(!command.includes('<ApplyGuard'))
})
test('MCP config shares only agent capability and uses the detected Python',()=>{
  const config=agentMcpConfig(setup,connection,'http://localhost:5173').mcpServers.applyguard
  assert.equal(config.command,setup.python)
  assert.deepEqual(config.args,[setup.connector_path])
  assert.equal(config.env.APPLYGUARD_AGENT_TOKEN,connection.token)
  assert.ok(!JSON.stringify(config).includes(connection.ui_token))
})
test('authorization is not pairing and expiration overrides earlier pairing',()=>{
  assert.equal(connectionStage(null,false,0),'尚未授权')
  assert.equal(connectionStage(connection,false,0),'等待 Agent 连接')
  assert.equal(connectionStage(connection,true,0),'已配对，可让 Agent 搜索材料')
  assert.equal(connectionStage(connection,true,100000),'授权已过期')
})
