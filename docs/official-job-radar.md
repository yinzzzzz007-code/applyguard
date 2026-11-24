# 官网岗位雷达交接

从岗位雷达 `/jobs` 打开「官网动态」。可以刷新启用的全部来源，或者只刷新一家公司。结果保存在 `data/local/job-radar.sqlite3`，支持 `APPLYGUARD_LOCAL_DIR`。旧岗位、收藏阶段、人工 JD 编辑、AI Career Radar 文件导入和原申请流程沿用已有数据模型。

刷新摘要区分新增、更新、未变化、下线和跳过；如果来源只提供部分目录，页面直接显示来源提示。新增和更新均为零不等于刷新失败，可结合未变化数量和最近完成时间检查。

「官网动态」使用当前水彩工作台的 shadcn/ui Card 和 Button。配色在 `frontend/src/palette.css`，卡片晕染、柔和阴影和反馈动画在 `frontend/src/workspace-polish.css`。手机打开岗位详情后，可用「返回岗位列表」回到刷新、筛选和提醒。

## 来源覆盖

| 来源 | 读取范围 | 可用于判断下线 |
|---|---|---|
| [百度校园招聘](https://talent.baidu.com/jobs/list?recruitType=INTERN) | 实习列表的公开渲染数据含职责与要求。分页接口允许匿名访问时读取完整目录 | 仅当分页读取完整、总数一致且岗位识别成功 |
| [华为校园招聘](https://career.huawei.com/cn/campus-recruitment-job-list) | 公开校园目录与岗位意向。每次最多补 16 条缺少或需要更新的详情，已有详情按官网更新标识复用 | 目录完整时成立。目录记录保留，详情暂缺时提示打开官网 |
| [字节跳动 Seed](https://seed.bytedance.com/zh/career) | 官网「热招岗位」及其公开详情 | 官网详情明确标记失效时成立，热招名单变动不会触发下线 |

只看到目录的岗位可以收藏或打开官网，需要完整职责和要求才能进入证据预检和绑定岗位的申请工作流。来源读取失败时保留已入库数据和最近成功时间。后端按来源限制请求体积、时长和允许访问的域名。招聘网站请求只包含公开目录或岗位查询参数。

## 运行与配置

正常启动项目后端 `python -m backend.app` 即可启用每日计划。默认北京时间 09:00，启动时会处理到期计划。界面支持单来源配置刷新间隔、手动刷新和强制刷新。强制刷新跳过五分钟的手动冷却，仍与同一个数据库的计划任务共用并发锁。

```bash
python scripts/refresh_official_jobs.py --status
python scripts/refresh_official_jobs.py --source huawei --force
python scripts/refresh_official_jobs.py --due
```

| 环境变量 | 含义 |
|---|---|
| `APPLYGUARD_JOB_SOURCES` | 数据库首次建立时启用的来源，默认 `baidu,huawei,bytedance_seed`。已有配置通过来源管理修改 |
| `APPLYGUARD_JOBS_AUTO_REFRESH` | 默认 `true`。设为 `false` 时关闭内置调度，手动刷新及独立 CLI 可用 |
| `APPLYGUARD_JOBS_REFRESH_TIME` | 北京时间 `HH:MM`，默认 `09:00`。更改后可在来源管理保存间隔以重算已有计划 |
| `APPLYGUARD_JOB_AI_MATCH` | 默认关闭。开启后可在有规则结果的中高匹配岗位上主动请求模型解释 |
| `APPLYGUARD_AI_API_KEY`、`APPLYGUARD_AI_BASE_URL`、`APPLYGUARD_AI_MODEL`、`APPLYGUARD_COMPLEX_AI_MODEL` | 复用现有模型客户端配置。只在用户点击「请求语义解释」后使用 |

规则评分基于已保存的本机简历。项目、实习、技能、意向、城市及招聘类型构成可解释线索。学历、年限等未证实条件会提示核对。模型请求仅包含岗位标题、部分岗位要求和规则结果。模型评分单独显示，采集、提醒和申请资格仍由本地规则处理。

### 可选 macOS LaunchAgent

在 macOS 上从仓库目录运行下列命令。脚本使用当前 Python 解释器和本仓库的绝对路径生成配置。LaunchAgent 每 15 分钟检查一次到期记录，即使后端和浏览器关闭也能从同一本地数据库执行刷新。运行需要用户处于登录状态。机器休眠或暂停后，以恢复运行的首次到期检查为准。

```bash
mkdir -p ~/Library/LaunchAgents
python scripts/refresh_official_jobs.py --print-launchd > ~/Library/LaunchAgents/local.applyguard.job-refresh.plist
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/local.applyguard.job-refresh.plist
```

## 接口与实现

| 接口 | 用途 |
|---|---|
| `GET /api/v1/jobs/sources` | 来源启用状态、成功时间、失败详情和下次计划 |
| `PATCH /api/v1/jobs/sources/{source_id}` | 修改 `enabled` 和 `interval_hours` |
| `POST /api/v1/jobs/refresh` | 接受可选 `source_ids` 数组和 `force` 布尔值，返回任务编号 |
| `GET /api/v1/jobs/refresh/status` | 运行中的各来源进度和最近一次运行结果 |
| `GET /api/v1/jobs` | 支持 `source`、`new`、`unread`、`match_level`、`city`、`recruitment_type`、`status`，兼容既有搜索与收藏阶段 |
| `GET /api/v1/jobs/alerts` | 可按 `job_id` 和 `unread=true` 查看提醒 |
| `POST /api/v1/jobs/alerts/read` | 接受 `ids` 或 `job_id`，带 `unread: true` 可重新打开提醒 |
| `POST /api/v1/jobs/alerts/read-all` | 批量标记全部已读 |
| `POST /api/v1/jobs/{job_id}/match` | 重新生成规则结果，`semantic: true` 在已启用时附加模型解释 |

适配器位于 `backend/services/job_sources/`。同步和计划在 `job_refresh.py`，迁移在 `job_sync_store.py`，评分和提醒分别在 `job_matching.py`、`job_alerts.py`。岗位仍沿用 `job_radar.py` 和历史版本。SQLite 持久化运行锁跨 API、后台线程与 CLI 生效。中断租期超时后，可启动下一轮。已提交的来源结果保留。

## 验证入口

```bash
python -m unittest tests.test_official_jobs tests.test_job_radar
npm --prefix frontend run build
npm --prefix frontend run smoke
node scripts/official_jobs_browser_smoke.cjs
```

浏览器脚本使用 Playwright 和本机 Edge，支持设置 `PLAYWRIGHT_MODULE` 与 `APPLYGUARD_TEST_PYTHON`。脚本启动临时本机端口，使用虚构简历和岗位 fixture，并在 `output/test-reports/` 留下截图。真实官网测试应使用独立的 `APPLYGUARD_LOCAL_DIR`。

2026-11-18 的本机实测共入库 129 条。百度公开首屏 10 条，分页接口返回 `no-auth`，因此覆盖标记为部分。华为目录 109 条，其中 68 条已有可用详情，余下条目可打开官网并在后续刷新时补齐。Seed 官网热招 10 条均取得详情。复刷百度和 Seed 各有 10 条未变化，无重复新增。LaunchAgent 已验证配置生成，运行环境为 Windows。

## 更新：语义与兴趣排序、可展开统计

默认“为你推荐（语义与兴趣）”使用本地多语言 MiniLM 对专业、技能、项目及岗位描述计算相似度，结合已填城市偏好、感兴趣／少推荐反馈，并适度打散同公司与重复岗位。保留全部岗位及搜索筛选；没有训练个人深度推荐模型，推荐分不是录用概率。输入不含手机号、邮箱等基本联系方式。技术条件匹配与语义推荐是两种不同结果，均给出理由。

`POST /api/v1/jobs/{job_id}/feedback` 的 interest 为 -1、0 或 1；前端可撤销。`job_recommendation.py` 记录本机 SQLite 反馈与异步排序状态；未装模型、失败、载入中分别提示，不伪造 ready。

安装：`python scripts/setup_job_semantics.py --directory E:/ApplyGuard/semantic --install-runtime`；将输出的两个环境配置设到本机 `.env` 后重启。所选路径可迁移；迁移后重新运行安装器生成当前路径。公开权重不依赖模型 API Key。

“新增岗位”“未读提醒”“在招高匹配”“来源异常”均可点击打开弹窗。未读提醒可逐条查看完整原因和岗位，不会因打开而自动标记已读；下方来源和提醒列表仍保留。提醒 API 支持 limit／offset／has_more，分批载入超过 200 条的提醒。

完整个人简历、站内提醒与界面复查见 [本轮报告](testing-report-2026-11-23-final-personal-flow.md)。
