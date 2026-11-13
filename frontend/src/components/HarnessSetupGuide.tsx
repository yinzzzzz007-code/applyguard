import type {HarnessSetup} from '../agentConnection'
import {installConnectorCommand} from '../agentConnection'

export function HarnessSetupGuide({setup, loading, error, onRefresh}:{
  setup:HarnessSetup|null; loading:boolean; error:string; onRefresh:()=>void
}) {
  return <div className="harness-setup">
    <div className="harness-heading"><div><span className="harness-eyebrow">本机 Agent · MCP 连接</span>
      <h3>连接 DeepSeek Harness</h3><p>准备环境 → 授权材料 → 在 Harness 发起检索。找到的原文会回到这里，等你核对。</p></div>
      <button className="btn secondary" disabled={loading} onClick={onRefresh}>{loading?'正在检测…':'重新检测环境'}</button>
    </div>
    <ol className="harness-steps">
      <li><span>01</span><div><strong>准备本机环境</strong><p>确认 Harness 与 Python 连接依赖</p></div></li>
      <li><span>02</span><div><strong>授权并启动</strong><p>选择材料范围，复制专属启动命令</p></div></li>
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
          未安装请从 <a href="https://deepseek.com/harness" target="_blank" rel="noreferrer">Harness 官方页面</a> 获取；自定义安装位置可设置 <code>APPLYGUARD_HARNESS_COMMAND</code> 后重启 ApplyGuard 后端。</li>
        <li><strong>在 ApplyGuard 的 Python 环境安装 MCP 依赖。</strong>复制下面的命令到 PowerShell，执行后点“重新检测环境”。这一步不需要在 Harness 聊天中安装 Python 包。
          {setup&&<pre>{installConnectorCommand(setup)}</pre>}</li>
        <li><strong>Harness 需要 MCP stdio 客户端。</strong>下面的快捷启动会加载 <code>@deepseek-ai/dsh-mcp-client</code>。
          若终端报告找不到该插件，请更新 Harness；手动配置方式见 <a href="https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md" target="_blank" rel="noreferrer">官方 MCP 说明</a>。</li>
        <li><strong>准备模型 API Key。</strong>快捷检索使用 {setup?.model||'配置的文本模型'}，连接令牌与模型 Key 是两个不同值，运行时分别隐藏输入。已有的 Harness 聊天不会自动接入本次授权。</li>
      </ol>
      {setup&&<details><summary>本机检测到的路径</summary><dl><dt>Python</dt><dd>{setup.python}</dd><dt>连接器</dt><dd>{setup.connector_path}</dd><dt>Harness</dt><dd>{setup.harness_command||'未检测到'}</dd></dl></details>}
    </details>
  </div>
}
