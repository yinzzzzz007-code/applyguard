# 自带 Agent 与本机 DeepSeek Harness（2026-11-13 更新）

## 2026-11-27 本地隐私与多轮查找

Harness 的任务和检索结果返回给 Agent 前，在本机将规则识别出的常见手机号、邮箱和 18 位身份证号码替换为会话内占位符；占位符对应关系只在本次授权的内存中，撤销时清除。用户界面保留原文，Agent 回传的引用必须与脱敏后的候选逐字一致，导入仍核对原件版本。普通 HTTP 文本模型和措辞审核 SDK 的请求也使用独立请求内占位符，响应按映射恢复；本次不把它称为全链路脱敏。

界面可填写每次连接需保护的姓名、公司等敏感词，并可编辑查找计划。连接器将这些词与格式规则一起在本地替换为会话占位符；该清单只作用于当前连接及其经历建议生成，不自动保护其他功能。界面默认开启逐批检索结果预览：用户在 55 秒内勾选允许返回给 Agent 的片段，未选片段不返回；超时或撤销时停止本批回传。任务和查找计划会在启动后交给 Agent，用户应在授权前自行检查。旧 API 客户端如未请求 `review_disclosures`，不启用逐批预览；不得对所有客户端声称默认已预览。

可选本地模型 `CheezOne/pii-detector-chinese-japanese-korean-english-small`（Apache-2.0）在 CPU 上辅助识别姓名等直接标识；当前权重约 264 MB，不提交 Git。源码环境执行 `python scripts/setup_privacy_ner.py` 下载固定版本并校验散列，并安装桌面依赖中的 ONNX Runtime 和 Tokenizers；重新打包时若上述文件齐全，`ApplyGuard.spec` 包含四个模型文件。界面提示是否检测到文件和运行库，首次推理会校验模型文件。若要求模型不可缺失，可设置 `APPLYGUARD_PII_NER_MODE=required`；默认 `auto` 在未安装模型时仍使用格式规则和自定义敏感词。许可和数据来源见 [第三方声明](../THIRD_PARTY_NOTICES.md)。

本地模型和规则均可能漏识别、误识别；公司、非标准号码、图片和其他隐私未受完整保护。SAG 使用云端模型或云端向量时，对识别到的个人信息保守阻止请求，不自动替换证据原文；用户需先处理相关材料。本地向量的 vector 路径不因该检查而阻止。不要据此承诺匿名、阻止所有个人信息外发或服务商不会保存数据。其他功能的发送不经过连接器逐批预览。

用户可选择 1 或 3 个并行 Harness 检索进程；三个进程分别侧重职责、方法、结果及更正，使用独立会话目录但共享用户授权和 12 次搜索上限。逐批预览会排队等待用户确认，并行调用可能增加费用；失败任务会显示部分完成，不代表完成全部搜索。结束后可对最多 6 条已允许外发的候选做一次模型冲突复核，只保留能定位到本地原文的双侧引文，显示为待用户核对的可能冲突；模型漏检、误判和两份来源并非独立的情况仍可能存在。关键词检索、提示词和小样本测试均不保证覆盖率。

回归入口：`python -m unittest tests.test_privacy_ner_live tests.test_outbound_privacy tests.test_harness_conflicts tests.test_agent_bridge tests.test_harness_autostart tests.test_agent_mcp`。前端构建后设置 `PLAYWRIGHT_MODULE` 指向本机 Playwright 包，运行 `node scripts/agent_disclosure_browser_smoke.cjs`；此脚本使用模拟接口和虚构数据，仅检查预览交互，不调用真实 Harness 或云端模型。

入口位于「证明材料」页的「连接 DeepSeek Harness / 其他 Agent」。页面检测实际 Python、连接脚本、MCP 依赖和已安装的 Harness，并生成本机命令。无需替换路径占位符。本机 Harness 0.2.1-rc.3 已完成真实 Gemini 配对、检索与回传，详细证据见 [续测报告](testing-report-2026-11-13-gemini.md#连接修复首页视频与严格导出续测)。

用户指定来源、决定外发规则，再授权。凭据在页面和运行进程中使用，30 分钟到期；撤销后旧凭据失效。离页会尽力撤权，崩溃／断网时由服务端到期兜底。已经传给 Agent／云端的片段不能通过撤权收回。手动上传仍可独立使用。

## 启动与配对

1. 启动 ApplyGuard 后端及前端，访问 `/evidence`。开发默认 `http://127.0.0.1:5173/evidence`；构建后也可直接访问后端的同一路径。保持页面和后端开启。
2. 展开连接入口并检查环境。缺依赖时安装说明自动展开。先在项目根目录打开终端，也可用「复制切换目录命令」进入。再执行「复制安装命令」，它使用当前后端的 Python 和相对的 `requirements-agent.txt`。执行完成后点「重新检测环境」。
3. 已装桌面版时自动发现其自带 `dsh.cmd`，也会查找 PATH 中的 `dsh`。自定义安装可将 `APPLYGUARD_HARNESS_COMMAND` 设为 PATH 命令名、相对项目根目录的路径或本机绝对路径，然后重启后端。快捷启动会加载 `@deepseek-ai/dsh-mcp-client`。缺该插件时先更新 Harness。 [Harness 安装](https://deepseek.com/harness) · [官方 MCP 说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md)
4. 填查找任务，点“选择文件夹”打开本机选择窗口；可连续点“继续添加文件夹”，最多 5 个，重复选择不增加，各项可移除。系统窗口未出现或不想继续时，点击“取消选择”；取消保留原列表。界面通过异步任务轮询选择结果，网络请求超时会显示错误，系统窗口最多等待 150 秒。无法打开窗口时展开“手动输入路径（备用）”。选择目录本身不读取或授权材料，仍须选择外发规则并点击授权连接。GitHub 范围为 `owner/repo@40位提交SHA`，不自动搜索整个账号。私有仓库须另行勾选，通过 GitHub 官方设备授权页确认，并选择本次可读仓库；“查技术背景”不能导入为本人贡献。
5. 点击授权，页面显示「等待 Agent 连接」。允许云端时，在本机终端执行启动命令。终端将分别隐藏读取临时连接令牌和模型 API Key。默认模型为 `gemini-3.1-flash-lite-preview`，地址取后端配置。
6. 启动器创建独立临时 `DSH_HOME` 和检索 patch，禁用其他通用工具，退出后清理临时目录。不会修改原 Harness 会话配置。安装检测和预检都不等于配对；只有 Harness 调用 `get_task` 后显示“已配对”，页面每 3 秒自动刷新候选。
7. 核对回传原文、本人归属及数字，再导入材料。完成后撤销连接。离页／撤销后的旧刷新响应不能重新恢复配对；过期后需要新命令与新令牌。

若选择“隔离本地模型，禁止外发”，快捷云端启动器会明确拒绝。请把下面 MCP 片段接入自己已隔离的检索 profile，并配置本地模型和网络隔离；这个选择不会自动完成操作系统隔离。已有 Harness 聊天不会自动获得新授权。

### 迁移到新目录或机器

在新项目目录运行 `python -m venv .venv` 重建环境，并用该解释器启动后端。页面会重新检测路径。项目内的 PowerShell 安装命令示例如下。

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r '.\requirements-agent.txt'
```

macOS 或 Linux 项目内环境的解释器为 `./.venv/bin/python`。共享环境与项目跨盘时，页面会针对目标机器生成解释器绝对路径，依赖清单仍从项目根目录读取。迁移后重新授权并生成 MCP 配置，授权目录按新机器上的材料位置填写。

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
| 连续选择本机文件夹、去重和移除 | `AgentConnector.tsx`、`agentConnection.ts`、`folder_picker.py`；同源 UI `pick_folder → folder_status / cancel_folder` | `python -m unittest tests.test_folder_picker`；前端构建 |
| 环境检测与相对安装命令，支持直接复制 | `HarnessSetupGuide.tsx`、`agentConnection.ts`、`harness_setup.py`；UI `setup` | `tests/test_harness_setup.py`、`frontend/scripts/agent-connection.test.mjs` |
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


## 2026-11-23 实际连接状态

本机目录选择已改为原生窗口，可连续追加、去重和移除。早期两次测试只完成 get_task 配对，检索回传失败。后续同日补测已完成 get_task → search_materials → submit_evidence；新 Key 最后一次实际用时 43.465 秒，4 个候选、回传 1 个。早期失败记录保留，不代表持续可用性。详见 [本轮报告](testing-report-2026-11-23-folders-harness.md)。`scripts/harness_agent_probe.py --timeout 240` 会记录各 MCP 阶段并在 Windows 下清理测试进程树。

## 可选 GitHub 点按引导

点击“从 GitHub 查找材料 · 点按引导”，按红点依次完成仓库与完整提交 SHA、私有仓库选择、外发规则、生成授权、启动检索。可随时跳过引导，不要求绑定整个账号。默认不勾选私有仓库，也不选择云端或本地模型授权。

管理员为 GitHub App 开启 Device Flow，设置 Contents 只读，安装时选择指定仓库，并在启动环境填写 `APPLYGUARD_GITHUB_APP_CLIENT_ID`。演示者点击“在 GitHub 授权私有仓库”，在 GitHub 官方页输入设备码并确认，返回点“我已确认，检查授权”，然后选择仓库与固定版本。断开、过期或重启后须重新授权。公开搜索、读取私库与 Harness 配对分别操作。

单独验证模型：`python scripts/diagnose_harness_model.py --timeout 45`。它区分基本鉴权、普通响应、流式工具调用和工具结果后的续轮。正式启动器与探针共用有总时限的进程执行器，界面提示真实进度。最新实测见 [恢复与引导记录](testing-report-2026-11-23-harness-recovery.md)。

## 更新：公开发现与云朵补全

无需先填写提交 SHA。输入 GitHub 用户名、公开邮箱或关键词，查找并勾选公开仓库；系统固定选定仓库的当前 SHA，显示“正在固定版本”后才允许授权。公开邮箱只能查 GitHub 可搜索资料，空结果不证明账号不存在；须人工选择候选账号，不据邮箱推断所有权。仍保留精确 `owner/repo@SHA` 输入。

查询公开元数据不等于授权读取材料。私有仓库仍需另行勾选并配置有限范围凭据；不自动扫描或关联全部私有仓库。GitHub 匿名 API 限流会明确提示；公共 HEAD 查询的备用 git 命令禁用凭据和交互。

授权按钮显示全部未满足条件。“查看原因与补全引导”调用共享云朵，先定位离按钮最近的未完成模块；完成后按原队列提示下一项，不代选外发规则、不创建授权。其他安装步骤和目录选择仍可展开查看。


## 最后复测与等待上限

当前独立 Harness 会话上限 240 秒，单次模型请求／流式空闲上限 90 秒；使用 `harness_setup.retrieval_patch` 生成唯一配置，启动器与探针共享。请求成功不等于事实核验通过，回传片段仍须人工确认和关联。新 Key 实测记录：`output/test-reports/20261123_195112_harness-live/report.json`。

模型异常时，页面明确区分本地服务已连接与云模型不可用。不会用静态示例、旧结果或未完成核验替代本次真实结果。整体状态及费用以 [最终个人流程报告](testing-report-2026-11-23-final-personal-flow.md) 为准。
