# 岗位雷达接入与交接

本次把机会管理接到 ApplyGuard 现有九模块工作流之前，新增 `/jobs` 页面。实现由 ApplyGuard 独立编写，通过 HTTP API 与 [AI Career Radar](https://github.com/Haoyu-Gu/ai-career-radar) 互操作。核对的上游版本为 `0ca459b3f6975d93a08cc5eea7adfca7e2a89b5c`。

## 已实现的用户流程

1. 在顶部打开“岗位雷达”。可手动录入完整 JD，导入 JSON/JSONL，或读取本机独立运行的 AI Career Radar。
2. 搜索收藏中的公司、城市、职位和技能；查看来源链接、来源观察时间、本机导入时间、状态和版本。
3. 展开技术/能力标签，核对命中的原文；查看收藏岗位的高频需求。标签包含否定句和优先项，不代表硬性要求。
4. 点击“检查证据缺口”：只使用当前编辑的简历，或明确读取的本机草稿及其关联原件。没有简历时显示缺少经历，不使用演示种子替代。规则解析、Evidence Matcher 和 Claim Validator 均在本机运行。
5. 先导入简历或保存本机经历，再点击“用此岗位准备申请”：把完整 JD 带入原来的岗位说明页面。默认点“运行离线工作流”；随后继续证据匹配、简历审查、陈述核验、ATS 模拟和人工确认。关联收藏岗位的正式工作流也禁止用演示经历替代用户简历。
6. 后端响应附带 `target_job` 快照（编号、版本、内容哈希、公司、来源等）。复制与模拟确认前的重新核验也检查当前岗位。更新、关闭或归档后，旧关联不得继续使用。
7. 可编辑 JD，保存为新版本，查看原版本并归档/恢复收藏。编辑岗位说明页里的文本会解除收藏关联，作为手动输入重新分析。

申请历史仍只保存本浏览器中的模拟摘要，现额外记录岗位编号和当次版本。没有新增自动投递或真实投递状态。

## 与外部雷达连接

ApplyGuard 本身的依赖和启动方式没有变化。外部雷达是可选的独立服务；不启动它仍可使用手动录入、文件导入和缺口分析。

按照上游 README 在另一个目录安装并启动 AI Career Radar。仅需它的后端时，可在其依赖环境中执行：

```bash
AUTO_REFRESH_ENABLED=false PYTHONPATH=backend uv run --frozen python -m uvicorn app.main:app --host 127.0.0.1 --port 8787
```

首次使用须初始化它的数据库，并通过其更新命令或界面采集岗位；没有采集过的空库不会自动出现真实岗位。`AUTO_REFRESH_ENABLED=false` 关闭上游定时刷新，手动更新仍由用户在上游操作。ApplyGuard 不请求其刷新或模型摘要接口。

ApplyGuard `.env` 的可选配置：

```dotenv
APPLYGUARD_RADAR_BASE_URL=http://127.0.0.1:8787
```

只接受字面回环地址 `127.0.0.1` 或 `[::1]` 的 HTTP 服务，不接受远程主机、账号密码、子路径和跳转。后端直连，不经过系统代理；不会向雷达发送简历、证据、API Key 或模型提示词。

实际读取上游 `GET /api/jobs`（每页 50 条）和选中记录的 `GET /api/jobs/{id}`（每次最多 20 条）。先读取详情再原子导入，任何记录失败都不部分写入。本机已收藏岗位不会因为雷达不可用、列表为空或没有被选中而自动关闭。岗位最新状态需重新导入确认；它不是自动后台同步。

## 文件导入格式

支持对象数组、`{"jobs":[...]}`、`{"items":[...]}` 和逐行 JSON 对象的 JSONL。单批最多 100 条、文件最多 1.9 MB；每条需含公司、岗位名称和 20–18000 字符的完整 JD。服务器对导入请求另设 2 MB 上限。

示例：

```json
{
  "jobs": [{
    "source_namespace": "my-job-list",
    "external_id": "official-42",
    "company": "虚构公司",
    "title": "后端开发实习生",
    "location": "上海",
    "status": "unknown",
    "url": "https://example.com/jobs/42",
    "description": "岗位职责：使用 Python 开发接口服务并补充自动化测试。任职要求：有相关项目经验。"
  }]
}
```

也可输入上游详情记录中的 `responsibilities` 和 `requirements`，适配层会组合为带标题的原文。只含摘要的列表 CSV 不足以生成申请，不支持直接导入。模板位于 `frontend/public/data/job-opportunities.example.json`，全部为虚构岗位；不会自动导入或计为真实招聘。

## 本机存储与数据口径

- 数据库：`data/local/job-radar.sqlite3`，受 `APPLYGUARD_LOCAL_DIR` 覆盖；Git 忽略，不随分支推送。
- 去重优先使用来源命名空间、公司与官方岗位 ID；无 ID 时使用来源 URL，最后使用公司/标题/地点。不同来源同一数字 ID 不混合。
- 参考快照与机会记录隔离；`peer_benchmark` 强制变为参考状态，不混入当前机会统计。
- 同一身份内容变化时建立版本；收藏阶段保留。人工编辑标记 `local_edit` 并清除来源观察时间。重新导入官方详情仍更新原记录。
- `open` 是来源声明，`unknown` 是待核对；未提供状态不会被猜为在招。`closed`、`reference`、`archived` 无法从岗位入口进入申请流程。
- 高频需求只统计本机未归档、状态为 `open`/`unknown` 的收藏，按岗位去重计数。既不是全市场统计，也不是录用人数或录用概率。
- 证据缺口不缓存：每次重新读取证据审核、链接和原件完整性状态。相关经历缺证不等于用户不具备能力。
- JD 标签和网页文本不能写入个人经历库，也不能自行把个人声明提升为 VERIFIED。
- 标签、缺口预检查和岗位导入都不调用模型。正式 JD 模型解析仅在用户明确选择时发生。

## API 与维护入口

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/jobs?q=...&stage=...` | 本机收藏和统计 |
| POST | `/api/v1/jobs` | 保存 `{"job": {...}}` |
| POST | `/api/v1/jobs/import` | 原子导入 `{"jobs": [...]}` |
| GET | `/api/v1/jobs/{id}` | 当前记录及带标题的工作流 JD |
| GET | `/api/v1/jobs/{id}/versions` | 历史版本 |
| POST | `/api/v1/jobs/{id}/edit` | `{"job": {...}}` 编辑并创建版本 |
| POST | `/api/v1/jobs/{id}/stage` | `saved` / `preparing` / `archived` |
| POST | `/api/v1/jobs/{id}/analyze` | `{"resume_draft": ...}` 离线证据预检查 |
| GET | `/api/v1/jobs/radar?search=...&offset=...` | 读取上游岗位列表 |
| POST | `/api/v1/jobs/radar/import` | 按 `{"ids": [42]}` 导入上游完整详情 |

错误沿用统一的 `error.code/message/trace_id`；无效输入 422、记录不存在 404、外部雷达不可用 503。SQLite 事务保护批量写入和并发更新。

主要代码：`backend/services/job_radar.py`、`frontend/src/pages/JobRadarPage.tsx`、`frontend/src/api/jobs.ts`。原九模块名称和冻结契约不变；`target_job` 是工作流响应上的可选附加上下文。

## 模型预算与兼容范围

本分支按项目使用者之前的要求，将通用模型默认值恢复为 `gpt-4o-mini`，服务地址 `https://api.chatanywhere.tech/v1`，最大输出 2048 token；未包含任何密钥。它们只是当前低成本测试配置。可修改 `APPLYGUARD_AI_MODEL`、`APPLYGUARD_AI_BASE_URL` 和 `APPLYGUARD_AI_MAX_TOKENS`（代码接受 1–16384，实际仍受服务商/模型上限约束）。DeepSeek 的已有可配置适配逻辑保留。

此接入不复制上游源码、个人背景评分、论文方向预测、配置文件或运行数据库。上游代码未发现许可证，仓库引用与本次 API 互操作说明已列入 `THIRD_PARTY_NOTICES.md`。不把上游算法当作经过验证的通用个人适配模型。

测试结果和人工验收见 [岗位雷达验证记录](career-radar-validation.md)。
