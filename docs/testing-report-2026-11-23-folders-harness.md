# 文件夹选择与真实 Harness 连接（2026-11-23）

**最新状态：16 时后已完成真实检索、回传及页面导入；见 [恢复报告](testing-report-2026-11-23-harness-recovery.md)。下方保留较早的失败记录。**

## 文件夹入口

证明材料页的 Agent 连接器默认使用本机文件夹选择窗口，连续选择会追加，重复选择不增加，各目录可移除，沿用最多五个目录的限制。取消不会改动已有列表。选择不创建授权或扫描材料，仍须完成外发规则选择并点击授权连接。

后续修复：窗口动作通过同源 `/api/v1/agent/ui` 的 `pick_folder → folder_status / cancel_folder` 异步分发，保持 Origin、Host 和界面请求头检查。统一使用 Python 自带 Tk 系统目录窗口，Windows 显式设为可见并置前；移除已被替代的 PowerShell/.NET 路径。前端可取消，单请求 15 秒超时，窗口 150 秒超时清理，不下载新依赖。无法启动时保留折叠的手动备用入口。用户已确认看到实际弹窗。

前端构建通过；异步窗口检查 7 项通过，覆盖不阻塞、并发限制、完成、原生取消、前端取消、整盘拒绝、超时与错误状态。连接器及 MCP 相关后端检查合计 36 项通过；完整前端 smoke 57 项通过。实际按钮审查另见 [全流程记录](testing-report-2026-11-23-ui-actions.md)。

## 15 时两次真实 Harness 测试（历史记录）

使用本机已安装的 DeepSeek Harness、实际 MCP stdio 插件、三份虚构 Atlas 材料、用户指定的 ChatAnywhere 地址和 Gemini 配置。没有用模拟配对代替真实 Harness。测试密钥仅供运行进程使用，日志脱敏。

- 第一次：实际调用 get_task，配对成功；251 秒后结束，候选 0、回传 0，退出码 1。报告：本机 `output/test-reports/20261123_151534_harness-live/report.json`。
- 第二次：使用缩短的单条回传任务；实际 get_task 完成，配对成功；180 秒超时，检索候选 0、回传 0，整体 FAIL。报告：本机 `output/test-reports/20261123_152337_harness-live/report.json`。
- 同一个 API 的最短非流式文本请求也在 30.3 秒超时，没有得到 HTTP 状态码。只能确认请求超时，无法据此确定网关、上游或网络中的具体故障位置。

这两次测试的结论：本机 Harness 配对已验证，检索回传未通过；后续恢复结果另见文首链接。

## CLI

`python scripts/harness_agent_probe.py --timeout 180` 记录 get_task/search_materials/submit_evidence 的实际完成事件。支持环境变量或隐藏输入提供 Key，使用独立 E 盘工作目录；超时结束本次进程树并撤销测试授权，报告区分配对、检索和回传。可以显式设置 15–600 秒时限；延长时限不等于证明服务恢复。

文件夹边界检查：`python -m unittest tests.test_folder_picker`。用户可直接在页面试用原生选择窗口。


## 后续恢复结果

同日后续分层诊断及正式启动器已完成真实检索、回传和页面导入。原有两次失败保留为历史证据；最新状态以 [恢复报告](testing-report-2026-11-23-harness-recovery.md) 为准。
