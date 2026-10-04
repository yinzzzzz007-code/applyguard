# ApplyGuard Frontend（D · Proposal）

七步 React/Vite/TypeScript UI，另有申请历史页；接入 C 的 `POST /api/v1/workflow/mock`（默认 `parse_mode: "offline"`）。

视觉系统来自 [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) 的 **Mintlify** `DESIGN.md`（本地副本：`frontend/design/DESIGN.md`）：天蓝/奶油 hero 渐变、Inter + Geist Mono、黑底主按钮与 `#00d4a4` 强调色。

独立原型原件仍保留在：

`D:\桌面\大三上\计算机与软件工程综合设计\ApplyGuard-frontend-prototype`

## 联调启动

一键启动（推荐，Windows）：

```bat
start-demo.bat
```

会分别打开后端 / 前端两个窗口，并在 Vite 就绪后打开 `http://127.0.0.1:5173`。首次运行若缺少 `.venv` 或 `node_modules` 会自动安装。

手动启动：

终端 1 — 后端（隔离 venv，勿用未装 `jsonschema` 的系统 Python）：

```powershell
cd "D:\桌面\大三上\计算机与软件工程综合设计\ApplyGuard\code\applyguard"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.app
```

终端 2 — 前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 Vite 提示的地址（默认 `http://127.0.0.1:5173`）。`/api` 与 `/health` 经 Vite 代理到 `127.0.0.1:8000`。

构建：

```powershell
npm run build
npm run lint
npm run smoke
```

## 演示场景

| 场景 | 行为 |
| --- | --- |
| 正常·Live | `GET /health` + `POST /api/v1/workflow/mock`，`candidate_id=cand_demo_001`，`parse_mode=offline` |
| 预录·BLOCKED | `public/prerecorded/unsupported_block.json`（`python -m demo.run_c_cases`） |
| 预录·Fallback | `public/prerecorded/timeout_fallback.json`（含 `RULE_FALLBACK` / `ModelFailure`） |
| 错误重试 | 模拟后端不可用；空 JD 走 Empty/校验错误，不假成功 |

## 契约枚举（页面只认这一套）

- Claim：`VERIFIED` / `NEEDS_REVIEW` / `BLOCKED`
- 汇总风险：`LOW` / `MEDIUM` / `HIGH` / `BLOCK`
- 字段控制：`field_controls.level` = `L0`–`L3`

## 数据边界

- Live 结果来自后端离线规则链路，不是旧 mock 固定表。
- 预录 JSON **明确标注**为 `demo.run_c_cases` 产物，不是本次 Live 响应。
- Career Vault 读取 `public/data/career-vault.seed.json`（与后端种子相同）；仓库尚无 Vault HTTP API。
- 模拟 ATS = fixture 映射 + C 的 field_controls/risk；**不是**真实招聘网站扫描。
- 人工确认仅为前端本地模拟；`audit_record` **未在后端持久化**；最终投递由用户本人完成。
- 申请历史只把模拟结果摘要保存在本浏览器 `localStorage`，不保存个人资料、JD 原文或简历正文。它不是后端申请历史，也不代表已投递。
- BLOCKED 或未完成核验／确认时不生成可复制填写稿；已阻断、被拒绝或编辑后待重新核验的陈述不可复制。未经后端重新核验的本地经历描述和技能也不可复制。
- 浏览器不保存 API Key；演示默认不走付费模型。

## 目录

```
frontend/
  src/api/          # types + ApplyGuardApiClient
  src/pages/        # 七步页面
  public/data/      # career-vault.seed.json
  public/prerecorded/  # demo.run_c_cases 输出
  src/history.ts        # 本地模拟历史摘要
  src/copyRules.ts      # 复制门槛与逐条过滤
  legacy-demo.html  # A/B 时代轻量 JSON 演示页
```

Proposal 后任务型测试方案见 `docs/usability-study/D-task-study.md`；演示脚本和视频见 `presentation/demo-video/`。尚未开展真实参与者测试。

重新生成预录：

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; import json; from demo.run_c_cases import run; out=Path('frontend/public/prerecorded'); out.mkdir(parents=True, exist_ok=True); r=run();
[ (out/f'{k}.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8') for k,v in r.items() ]"
```
