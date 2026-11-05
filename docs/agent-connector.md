# 自带 Agent 检索入口（2026-10-30 实验版）

Gitvextor的原型。手动上传保留；证据工作区新增「连接我的 Agent」。默认关闭，用户指定来源、决定外发规则，再点击「授权连接并生成配置」。凭据仅在进程/页面内存，30 分钟到期；撤销后旧凭据不能搜索或回传。折叠入口仍有撤销按钮，离开页面/关闭页面会尽力发送撤权请求；断网、浏览器崩溃时不能保证送达，服务端到期是兜底。撤权不撤回已经被用户 Agent 或云端模型接收的内容。

## 启动与配对

1. 安装原项目依赖及 `python -m pip install -r requirements-agent.txt`；构建前端 `npm ci`、`npm run build`。
2. PowerShell 设置 `$env:APPLYGUARD_PORT='8897'`，在仓库根目录运行 `python -m backend.app`。访问 `http://127.0.0.1:8897/evidence`。
3. 保留手动上传，或展开 Agent 入口。目录须为具体文件夹；GitHub 首版用 `owner/repo@40位提交SHA` 固定范围与版本，不自动扩展整个账号。自动模式只搜索已授权目录和仓库。
4. 选择「寻找本人贡献」或「查技术背景」。后者禁止直接导入为个人经历。私有仓库须独立勾选，并在服务进程配置 `APPLYGUARD_GITHUB_TOKEN`，不会借用用户已有 gh 登录。
5. 读取前选择允许云端模型接收片段，或确认自己已隔离本地模型。应用无法审计或限制第三方 Agent 自带工具/网络；本地选项是用户对运行环境的确认，不是本应用提供的系统沙箱。
6. 将页面生成的临时配置交给自己的 Agent，修改 Python/脚本绝对路径。模型调用 `get_task` 后页面刷新才显示已配对。点击「刷新配对与候选证据」查看回传结果。

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

不要把这个 patch 当作完整隔离配置。真实联调脚本 `scripts/harness_agent_probe.py` 在独立主目录禁用了 shell、文件、web、subagent、技能读取、遥测等入口，仅加入此 MCP；这种工具隔离仍不等于操作系统权限隔离。若需要严格本地运行，应再使用系统沙箱和网络隔离。参考 [Harness MCP](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)、[SDK范围限制](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/python-sdk.md)、[MCP边界说明](https://modelcontextprotocol.io/docs/learn/client-concepts)。

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
