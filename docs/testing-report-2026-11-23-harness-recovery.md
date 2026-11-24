# Harness 分层诊断、回传恢复与 GitHub 点按引导（2026-11-23）

本轮真实 Harness 已完成“领取任务 → 搜索 → 回传”，随后用正式启动器和页面确认导入再次通过。已增加等待上限、阶段反馈及可选 GitHub 小红点引导。此前两次超时确实发生；本轮恢复不能确定当时是网关、上游模型还是网络中的哪个环节异常。

## 分层诊断结果

均使用用户指定的 `gemini-3.1-flash-lite-preview` 与 `https://api.chatanywhere.tech/v1`，测试 Key 只在进程环境内使用。没有改系统代理，没有切换模型或服务商。

| 层级 | 真实结果 | 证据 |
| --- | --- | --- |
| API 连通与 Key | 系统代理路径、直接路径的未鉴权请求均快速返回 401；带 Key 的模型列表返回 200，包含所选模型 | 分层 CLI 的 models 阶段 |
| 普通模型回复 | HTTP 200，返回 OK；正式诊断耗时 30.921 秒 | `output/test-reports/20261123_163232_harness-model-diagnosis/report.json` |
| 工具调用 | 独立非流式、流式工具调用均成功；正式流式诊断为 200、21.368 秒 | 同上 streaming_tool_call |
| 工具结果后的下一轮 | 模型接收工具结果后成功继续回复，HTTP 200、1.645 秒 | 同上 tool_result_continuation |
| 真实 Harness 探针 | 32.876 秒，实际 get_task、search_materials、submit_evidence 均完成；4 个检索候选、1 条回传，退出码 0 | `output/test-reports/20261123_162442_harness-live/report.json` |
| 正式启动器和页面 | 61.503 秒，正式 `connect_harness.py` 退出码 0；页面显示 1 条真实回传，核对来源和数字后导入 1 份原文 | `output/harness-recovery-20261123/production-launcher.json`、`harness-returned.jpg` |

材料是本次创建的虚构 Atlas 文本。导入保持“待陈述核验”，没有把模型解释、来源确认或一次成功当成事实审核通过。测试授权已撤销；主服务的个人材料未参与这些模型测试。

## 修复的等待与反馈问题

- 原正式启动器没有会话总时限；已改用共享 `harness_process.py`，默认 180 秒，支持 `--timeout 15–600`。超时停止本次进程树并返回 124，不继续无限等待。
- 读取本机已安装 Harness 的插件配置及官方说明后，设置每次模型尝试 45 秒、流式空闲 45 秒、最多重试一次。保留原模型和 HTTPS 验证。
- 后端记录真实工具阶段与候选／回传数量，启动器记录开始、正常结束、失败和超时。界面分开显示“正在搜索”“等待回传”“已回传待确认”“已超时”等；超过 60 秒未推进时提示查看终端。
- 会话结束提示不授予事实通过权限。只有真实工具返回的卡片计入候选／回传，超时仍保留已回传内容。
- 运行临时目录位于当前项目 `output/harness-runtime/`，不再使用默认 C 盘临时目录；Key 不写入启动配置。

## GitHub 小红点引导

入口：证明材料 → 连接 DeepSeek Harness / 其他 Agent → **从 GitHub 查找材料 · 点按引导**。

引导有五步，当前目标显示红点、浅色边框与步骤卡，并自动定位：

1. **仓库和版本**：每行 `owner/repo@完整40位提交SHA`，最多五个。支持打开所填写仓库的提交记录；格式错误不能进入下一步，不接收 Token 作为仓库地址。
2. **私有仓库**：默认不勾选。公开仓库可直接继续；私有仓库需要后端凭据。缺凭据会显示具体操作并阻止继续，后端也在创建授权前校验。
3. **材料外发规则**：两项默认均未选，用户必须自行确认；仓库读取授权与发送云端模型分别处理。
4. **本次授权**：引导定位实际授权按钮，继续操作需要用户点击。引导本身不会生成授权。
5. **启动检索**：授权生成后定位启动命令与令牌；本地隔离模型路径定位手动 MCP 配置。结束引导不等于已配对或已完成核验。

支持上一步、关闭／跳过引导和减少动态效果。无需绑定整个 GitHub 账号，当前实现是按指定仓库和版本读取；没有新增 GitHub OAuth 账号绑定。后端只返回“是否配置凭据”，不会把 GitHub Token 传给前端或 Harness。

实际浏览器已检查第一至第四步：空仓库和错误格式拦截、位置跳转、私有凭据缺失提示、公开选项可继续、外发规则不自动勾选、授权按钮定位。创建 GitHub 测试授权被自动审批拒绝，原因是尚未明确允许读取具体仓库；本轮没有绕过该拒绝。第五步的状态切换和组件通过类型／构建检查，未进行 GitHub 真实授权或私有仓库读取实测。

私有凭据步骤依据 [GitHub 官方 Token 管理说明](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) 与 [细粒度权限表](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)：选择所需仓库，将 Contents 设为 Read-only。Harness 配置依据 [官方多模型适配器说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/llm/llm-pi-ai/README.md) 和本机已安装的 0.2.1-rc.3 代码核对。

## CLI 与检查

```powershell
python scripts/diagnose_harness_model.py --timeout 45
python scripts/harness_agent_probe.py --timeout 120
python scripts/verify_ui_actions.py --build
```

第一条独立检查模型列表、普通回复、流式工具调用、工具结果后续回复，并保存脱敏 JSON；第二条必须运行真实 Harness，不能用模拟配对替代；第三条不调用模型、不读取个人文件。

本轮必要检查：后端 41 项、前端 smoke 60 项及构建通过，日志位于 `output/test-reports/20261123_164228_ui-actions/`；最后修改阶段标题后，相关前端 10 项与构建再次通过。网络服务仍可能波动，本轮两次真实端到端成功是当前可用证据，不是持续可用或准确率保证。
