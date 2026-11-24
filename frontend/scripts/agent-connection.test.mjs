import assert from 'node:assert/strict'
import {test} from 'node:test'
import {appendAllowedFolder, agentMcpConfig, connectionDetail, connectionStage, installConnectorCommand, launchHarnessCommand, projectDirectoryCommand} from '../src/agentConnection.ts'

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

test('folder selections append, deduplicate Windows paths and preserve earlier choices',()=>{
  const first=appendAllowedFolder('', 'E:\\材料')
  assert.equal(appendAllowedFolder(first, 'e:/材料/'),first)
  assert.equal(appendAllowedFolder(first,'E:\\报告'),first+'\nE:\\报告')
  assert.equal(appendAllowedFolder(first,''),first)
})
test('folder selection explains the existing five-folder limit',()=>{
  assert.throws(()=>appendAllowedFolder('E:/a\nE:/b\nE:/c\nE:/d\nE:/e','E:/f'),/5/)
})

test('progress separates pairing, retrieval, submission and timed out sessions',()=>{
  const p={stage:'task_received',updated_at:10,run_state:'started',candidates:0,submitted:0}
  assert.match(connectionDetail(p,11000),/等待发起材料搜索/)
  assert.match(connectionDetail({...p,stage:'searched',candidates:4},11000),/4 个候选/)
  assert.match(connectionDetail({...p,stage:'submitted',submitted:1},11000),/回传 1 条/)
  assert.match(connectionDetail({...p,run_state:'timed_out',submitted:1},11000),/已超时/)
  assert.match(connectionDetail({...p,run_state:'finished'},11000),/未回传引用/)
  assert.match(connectionDetail(p,71000),/超过 60 秒/)
  assert.equal(connectionStage(connection,true,11000,{...p,run_state:'timed_out'}),'检索已超时')
  assert.equal(connectionStage(connection,true,11000,{...p,submitted:1}),'已回传引用，待确认')
})

test('GitHub guide validates exact repository scope and never accepts credentials as a repository',async()=>{
 const {githubRepositoriesError}=await import('../src/githubGuide.ts')
 assert.ok(githubRepositoriesError(''))
 assert.ok(githubRepositoriesError('owner/repo@main'))
 assert.ok(githubRepositoriesError('github_pat_private_credential'))
 assert.equal(githubRepositoriesError('owner/repo@'+'a'.repeat(40)),'')
 assert.ok(githubRepositoriesError(Array(6).fill('owner/repo@'+'a'.repeat(40)).join('\n')))
})

test('public guidance skips private authorization; private starts with consent and then the repository',async()=>{
 const {githubGuideSteps,githubGuideBlocker}=await import('../src/githubGuide.ts')
 assert.deepEqual(githubGuideSteps(false).map(s=>s.target),['repositories','disclosure','authorize','launch'])
 assert.equal(githubGuideSteps(true)[0].target,'private')
 const v={repos:'',credentialConfigured:false,disclosure:''}
 assert.match(githubGuideBlocker('repositories',v),/公开仓库/)
 assert.match(githubGuideBlocker('private',v),/在 GitHub 授权/)
 assert.match(githubGuideBlocker('private',{...v,credentialConfigured:true}),/已授权的私有仓库/)
 assert.equal(githubGuideBlocker('repositories',{...v,repos:'one/two@'+'b'.repeat(40)}),'')
 assert.match(githubGuideBlocker('disclosure',v),/亲自选择/)
})

test('authorization tells the user every missing condition and permits local auto scope',async()=>{
 const {authorizationIssues}=await import('../src/githubGuide.ts')
 const v={mode:'github',folders:0,repos:'',task:'寻找项目依据',privateRepo:false,disclosure:'',setup:null}
 assert.ok(authorizationIssues(v).some(s=>s.includes('查找并选择')))
 assert.ok(authorizationIssues(v).some(s=>s.includes('外发')))
 assert.ok(authorizationIssues(v).some(s=>s.includes('检测')))
 const valid={...v,mode:'auto',folders:1,disclosure:'cloud_allowed',setup:{mcp_installed:true,connector_exists:true}}
 assert.deepEqual(authorizationIssues(valid),[])
 assert.ok(authorizationIssues({...valid,task:''}).length)
 assert.ok(authorizationIssues({...valid,mode:'github',repos:'owner/repo@'+'a'.repeat(40),privateRepo:true}).some(s=>s.includes('授权')))
})
