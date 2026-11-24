const publicStep = {target:'repositories', title:'查找公开仓库', description:'输入用户名、公开邮箱或项目关键词，点击「查找公开仓库」，再从结果中选择。'}
const privateStep = {target:'private', title:'授权并指定私有仓库', description:'先在 GitHub 确认只读授权，再从已获准的仓库中指定本次使用的仓库。'}
const harnessSteps = [
  {target:'disclosure',title:'选择材料外发规则',description:'请选择检索到的片段可以进入云端模型，还是仅交给你配置的隔离本地模型。'},
  {target:'authorize',title:'授权 Harness 读取材料',description:'核对范围后，点击授权连接按钮。本次检索配置最多 30 分钟有效。'},
  {target:'launch',title:'在 Harness 发起检索',description:'按页面提示启动 Harness，完成配对后即可查找材料。'},
]

export function githubGuideSteps(privateRepo:boolean) {
  return [privateRepo ? privateStep : publicStep, ...harnessSteps]
}

export function githubRepositoriesError(text:string, privateRepo=false):string {
  const rows=text.split('\n').map(row=>row.trim()).filter(Boolean)
  if (!rows.length) return privateRepo ? '请从已授权的私有仓库中选择一个。' : '请先查找并选择一个公开仓库。'
  if (rows.length>5) return '最多选择五个仓库。'
  if (rows.some(row=>! /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+@[a-fA-F0-9]{40}$/.test(row)))
    return '未能确认仓库版本，请重新选择仓库。'
  return ''
}

export function githubGuideBlocker(target:string|undefined, values:{repos:string;credentialConfigured:boolean;disclosure:string}):string {
  if (target==='private' && !values.credentialConfigured) return '点击「在 GitHub 授权私有仓库」，在官方页面确认后回来检查授权。'
  if (target==='repositories' || target==='private') return githubRepositoriesError(values.repos,target==='private')
  if (target==='disclosure' && !['cloud_allowed','isolated_local'].includes(values.disclosure)) return '请亲自选择一种材料外发规则。'
  return ''
}

type AuthorizationValues={mode:string;folders:number;repos:string;task:string;privateRepo:boolean;disclosure:string;setup:{mcp_installed:boolean;connector_exists:boolean;github_token_configured?:boolean}|null}
export function authorizationRequirements(v:AuthorizationValues) {
  const issues:{id:string;label:string;selector:string}[]=[]
  const add=(id:string,label:string,selector:string)=>issues.push({id,label,selector})
  if(v.task.trim().length<4||v.task.trim().length>2000)add('task','请填写 4–2000 字的查找需求。','.agent-task')
  if(v.mode==='local'&&!v.folders)add('folders','请选择至少一个材料文件夹。','.agent-folder-picker')
  if(v.mode==='auto'&&!v.folders&&!v.repos.trim())add('sources','请选择材料文件夹或 GitHub 仓库。','.agent-folder-picker')
  if(v.folders>5)add('folders','最多选择五个材料文件夹。','.agent-folder-picker')
  if (v.mode!=='local' && v.privateRepo && !v.setup?.github_token_configured) {
    add('private','请先在 GitHub 确认私有仓库授权。','[data-github-target="private"]')
  } else if (v.mode!=='local' && (v.mode==='github' || v.repos.trim() || v.privateRepo)) {
    const error=githubRepositoriesError(v.repos,v.privateRepo)
    if(error)add('repositories',error,v.privateRepo?'[data-github-target="private"]':'[data-github-target="repositories"] input[placeholder="用户名"]')
  }
  if(!['cloud_allowed','isolated_local'].includes(v.disclosure))add('disclosure','请选择一种材料外发规则。','[data-github-target="disclosure"]')
  if(!v.setup)add('setup','请先重新检测本机环境。','.harness-setup-target')
  else {if(!v.setup.mcp_installed)add('mcp','请先按上方引导安装 MCP 依赖，再重新检测。','.harness-setup-target');if(!v.setup.connector_exists)add('connector','未找到连接脚本，请检查项目安装后重新检测。','.harness-setup-target')}
  return issues
}
export function authorizationIssues(v:AuthorizationValues):string[] {return authorizationRequirements(v).map(item=>item.label)}
