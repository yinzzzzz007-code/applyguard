# 自带 Agent 与本机 DeepSeek Harness（2026-11-13 更新）

入口位于「证明材料」页的「连接 DeepSeek Harness / 其他 Agent」。页面检测实际 Python、连接脚本、MCP 依赖和已安装的 Harness，并生成本机命令。无需替换路径占位符。本机 Harness 0.2.1-rc.3 已完成真实 Gemini 配对、检索与回传，详细证据见 [续测报告](testing-report-2026-11-13-gemini.md#连接修复首页视频与严格导出续测)。

用户指定来源、决定外发规则，再授权。凭据在页面和运行进程中使用，30 分钟到期；撤销后旧凭据失效。离页会尽力撤权，崩溃／断网时由服务端到期兜底。已经传给 Agent／云端的片段不能通过撤权收回。手动上传仍可独立使用。

## 启动与配对

1. 启动 ApplyGuard 后端及前端，访问 `/evidence`。开发默认 `http://127.0.0.1:5173/evidence`；构建后也可直接访问后端的同一路径。保持页面和后端开启。
2. 展开连接入口，查看环境状态。缺依赖时安装说明自动展开，授权按钮不可用。Python MCP 依赖安装在运行 ApplyGuard 的 Python 环境：复制页面生成的 `python.exe -m pip install -r requirements-agent.txt` 完整命令，到 PowerShell 执行，再点“重新检测环境”。不在 Harness 聊天内安装 Python 包。
3. 已装桌面版时自动发现其自带 `dsh.cmd`，也会查找 PATH 中的 `dsh`。未安装请从 [官方页面](https://deepseek.com/harness) 获取。自定义路径通过 `APPLYGUARD_HARNESS_COMMAND` 配置并重启后端。快捷启动自动加载 `@deepseek-ai/dsh-mcp-client`；缺该插件时更新 Harness，参考 [官方 MCP 文档](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)。
4. 填查找任务和具体目录，选择材料外发规则。GitHub 范围为 `owner/repo@40位提交SHA`，不自动搜索整个账号。私有仓库须另行勾选并配置独立 `APPLYGUARD_GITHUB_TOKEN`；“查技术背景”不能导入为本人贡献。
5. 点击授权，页面显示“等待 Agent 连接”。允许云端时，复制 PowerShell 启动命令并执行；终端依次隐藏询问临时连接令牌和模型 API Key。令牌从页面单独复制，两者不是同一个值。默认模型为 `gemini-3.1-flash-lite-preview`，地址取后端配置，命令不含密钥。
6. 启动器创建独立临时 `DSH_HOME` 和检索 patch，禁用其他通用工具，退出后清理临时目录。不会修改原 Harness 会话配置。安装检测和预检都不等于配对；只有 Harness 调用 `get_task` 后显示“已配对”，页面每 3 秒自动刷新候选。
7. 核对回传原文、本人归属及数字，再导入材料。完成后撤销连接。离页／撤销后的旧刷新响应不能重新恢复配对；过期后需要新命令与新令牌。

若选择“隔离本地模型，禁止外发”，快捷云端启动器会明确拒绝。请把下面 MCP 片段接入自己已隔离的检索 profile，并配置本地模型和网络隔离；这个选择不会自动完成操作系统隔离。已有 Harness 聊天不会自动获得新授权。

DeepSeek Harness 支持 MCP stdio；在**独立检索 profile** 中加入以下 patch（临时 ID/token 通过环境变量提供，不写进仓库）：

```yaml
- insert:
  - id: applyguard-mcp
    name: '@deepseek-ai/dsh-mcp-client'
    config:
      serverName: applyguard
      transport: stdio
      command: '<Python绝对路径>'
      args: ['<ApplyGuard绝对路径>/scripts/agent_mcp.py']
      env:
        APPLYGUARD_AGENT_URL: !!js process.env.APPLYGUARD_AGENT_URL
        APPLYGUARD_AGENT_ID: !!js process.env.APPLYGUARD_AGENT_ID
        APPLYGUARD_AGENT_TOKEN: !!js process.env.APPLYGUARD_AGENT_TOKEN
      failOnStartupError: true
```

手动接入时，将页面实际生成的 YAML 保存为 `applyguard-mcp.patch.yml`；通用 JSON 的 `env` 提供本次 URL、ID、TOKEN，在启动 Harness 的终端设置对应进程环境变量。使用 `dsh --profile <已隔离的配置名> --patch <该文件绝对路径>`，要求模型先调用 `get_task`。请勿把临时凭据提交到仓库。通用 JSON 可直接交给支持 `mcpServers` 的其他客户端。

此 MCP 片段本身不禁用其他工具。完整快捷检索配置由 `backend/services/harness_setup.py` 生成，启动器和真实探针共用；禁用 shell、文件、web、subagent、技能和遥测等入口。工具限制仍不等于操作系统隔离。

## 用户入口与验证地图

| 用户操作／预期证据 | 实现位置 | 验证入口 |
| --- | --- | --- |
| 环境检测，显示真实安装路径和依赖状态 | `HarnessSetupGuide.tsx`、`harness_setup.py`；UI `setup` | `tests/test_harness_setup.py` |
| 授权后等待；真正调用工具后已配对 | `AgentConnector.tsx`、`agentConnection.ts`、`agent_bridge.py` | `frontend/scripts/agent-connection.test.mjs`、`tests/test_agent_bridge.py` |
| PowerShell 启动、预检外发规则、独立会话 | `scripts/connect_harness.py`、共享检索 patch | `tests/test_agent_mcp.py`、`scripts/harness_agent_probe.py` |
| 本机同源代理，不放开外站访问 | `frontend/vite.config.ts`、`backend/app.py` | `scripts/agent_browser_smoke.cjs` |
| 自动回传、撤销、忽略旧响应、缺依赖提示 | `AgentConnector.tsx` | `scripts/agent_browser_smoke.cjs` |

浏览器测试使用 Playwright 和本机 Edge：在仓库根目录设置 `PLAYWRIGHT_MODULE` 为已安装 `playwright` 模块目录，执行 `node scripts/agent_browser_smoke.cjs`。有 `APPLYGUARD_AI_API_KEY` 时真实启动 Harness；无 Key 时仅模拟配对，报告明确区分。只使用脚本生成的虚构材料；报告及截图写入 `output/test-reports/`。`APPLYGUARD_TEST_URL` 可覆盖默认 5173 地址。

## 证据与修改保护

- 连接器仅提供领取任务、检索、回传；没有任意 shell、任意路径读取、扩大授权范围或批准陈述工具。UI 与 Agent 使用不同能力凭据，界面接口要求本机同源。
- 片段由服务器从原件解析；回传须逐字匹配引用和版本。卡片保存路径、页码/行/段、SHA256、GitHub commit SHA、关联经历、候选解释和缺失信息。模型解释不会标成 VERIFIED。
- 原件变更后不能按旧哈希导入。用户核对归属，含数字片段须单独确认数字与范围；导入后的 Markdown 保留来源位置，仍需进入现有 SAG/原子核验及关联流程。不会自动修改简历。
- 润色前新增原文原子核验，只保护有依据的旧事实，防止把纠正旧错误误判成丢失有效信息。新稿仍独立核验；拆分不完整保留待复核。原有历史回滚机制保留，回滚后旧审批失效。
- “百分点→百分比”相同数字但单位改变时保守转为待复核。仅复用本次请求、同一证据快照中刚完成的原文核验：原文未变化或建议被拒绝时不重复调用；跨请求不复用旧通过状态，返回前仍检查材料变更与撤权。
- 撤销按钮不受刷新/导入等待状态锁定；撤销后忽略旧刷新响应，过期及重复撤销可正常退出。MCP本机HTTP通信明确绕过系统代理，凭据不走代理。

## 当前边界

关键词检索是连接器的首版基线，不把它称为 SAG 检索效果。可由 Harness 多次查询补充线索；导入后才进入已有 SAG 工作流。每次最多扫描500个本地文件/目录条目、60个GitHub文件，返回20片段；单文件1MB，PDF40页，不做图片OCR。隐藏目录、依赖目录、符号链接/目录联接越界、常见密钥形态内容均跳过；密钥检测不是完整DLP。PDF/DOCX是本地文本提取，尚未覆盖各种扫描件和排版。

当前授权仅内存保存，服务重启全部失效；候选卡片不跨重启保存，确认导入后的材料按原工作区保存。账号/URL范围选择器、OS沙箱、真实私有仓库联调、持久化连接管理和独立人工标注属于后续项目。
