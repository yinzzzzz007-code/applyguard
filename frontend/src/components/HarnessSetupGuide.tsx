import {useState} from 'react'
import type {HarnessSetup} from '../agentConnection'
import {installConnectorCommand, projectDirectoryCommand} from '../agentConnection'
import {Button} from './ui/button'

export function HarnessSetupGuide({setup, loading, error, onRefresh}:{
  setup:HarnessSetup|null; loading:boolean; error:string; onRefresh:()=>void
}) {
  const [copyStatus,setCopyStatus]=useState('')
  const install=setup ? installConnectorCommand(setup) : ''
  const directory=setup ? projectDirectoryCommand(setup) : undefined
  const shell=setup?.shell==='posix' ? '终端' : 'PowerShell'
  async function copy(text:string,label:string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopyStatus(label+'已复制。')
    } catch {
      setCopyStatus('无法访问剪贴板，请选中下方命令手动复制。')
    }
  }
  return <div className="harness-setup">
    <div className="harness-heading"><div><span className="harness-eyebrow">本机 Agent · MCP 连接</span>
      <h3>连接 DeepSeek Harness</h3><p>准备环境 → 授权材料 → 在 Harness 发起检索。找到的原文会回到这里，等你核对。</p></div>
      <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={loading} onClick={()=>{setCopyStatus('');onRefresh()}}>{loading?'正在检测…':'重新检测环境'}</Button>
    </div>
    <ol className="harness-steps">
      <li><span>01</span><div><strong>准备本机环境</strong><p>确认 Harness 与 Python 连接依赖</p></div></li>
      <li><span>02</span><div><strong>授权并启动</strong><p>选择材料范围后，一键开始查找</p></div></li>
      <li><span>03</span><div><strong>配对与回传</strong><p>调用 get_task 后显示已配对</p></div></li>
    </ol>
    {error&&<p className="harness-warning" role="alert">环境检测失败：{error}。请保持后端运行后重试。</p>}
    {setup&&<div className="harness-checks">
      <div><span>ApplyGuard 连接器</span><strong className={setup.connector_exists?'ready':'missing'}>{setup.connector_exists?'已就绪':'缺少脚本'}</strong></div>
      <div><span>Python MCP 依赖</span><strong className={setup.mcp_installed?'ready':'missing'}>{setup.mcp_installed?'已安装':'需要安装'}</strong></div>
      <div><span>DeepSeek Harness</span><strong className={setup.harness_command?'ready':'missing'}>{setup.harness_command?'已检测到本机安装':'未检测到 · 查看安装步骤'}</strong></div>
    </div>}
    <details className="harness-install" open={setup ? !setup.mcp_installed || !setup.harness_command : undefined}>
      <summary>首次使用：安装位置与完整准备步骤</summary>
      <ol>
        <li><strong>在本机安装 DeepSeek Harness。</strong>已有桌面版时会使用它自带的 dsh，无需重复安装。
          未安装请从 <a href="https://deepseek.com/harness" target="_blank" rel="noreferrer">Harness 官方页面</a> 获取。自定义安装可将 <code>APPLYGUARD_HARNESS_COMMAND</code> 设为 PATH 中的命令名、相对项目根目录的路径或本机绝对路径，然后重启后端。</li>
        <li><strong>安装 ApplyGuard 的 MCP 依赖。</strong>在当前项目根目录打开 {shell}（该目录含 <code>requirements-agent.txt</code>），复制并运行安装命令，再点「重新检测环境」。
          <p className="muted">换机器或移动项目后，在新位置重建 <code>.venv</code>，用它重启 ApplyGuard 后端，再检测并复制新命令。</p>
          {setup && setup.install_python === setup.python && <p className="muted">当前后端 Python 位于另一磁盘，命令会使用检测到的本机解释器路径。</p>}
          {setup && <>
            <div className="btn-row harness-install-actions">
              {directory && <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={loading} onClick={()=>void copy(directory,'切换目录命令')}>复制切换目录命令</Button>}
              <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={loading} onClick={()=>void copy(install,'安装命令')}>复制安装命令</Button>
            </div>
            <pre aria-label="安装命令">{install}</pre>
            {copyStatus&&<p role="status" className="muted">{copyStatus}</p>}
            {directory && <details><summary>查看切换目录命令</summary><pre aria-label="切换目录命令">{directory}</pre></details>}
          </>}</li>
        <li><strong>Harness 需要 MCP stdio 客户端。</strong>下面的快捷启动会加载 <code>@deepseek-ai/dsh-mcp-client</code>。
          若终端报告找不到该插件，请更新 Harness；手动配置方式见 <a href="https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md" target="_blank" rel="noreferrer">官方 MCP 说明</a>。</li>
        <li><strong>准备模型 API Key。</strong>在右上角“模型设置”填写服务和密钥，一键查找会使用 {setup?.model||'配置的文本模型'}。已有的 Harness 聊天不会自动接入本次授权；如需手动连接，可在授权后展开备用说明。</li>
      </ol>
      {setup&&<details><summary>本机检测到的路径</summary><dl>{setup.project_root&&<><dt>项目根目录</dt><dd>{setup.project_root}</dd></>}<dt>Python</dt><dd>{setup.python}</dd><dt>连接器</dt><dd>{setup.connector_path}</dd><dt>Harness</dt><dd>{setup.harness_command||'未检测到'}</dd></dl></details>}
    </details>
  </div>
}
