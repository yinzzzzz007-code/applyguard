# ApplyGuard D-2 `test1` 测试与修复交付说明

日期：2026-10-06；起点：`D-2` 的 `816a246`；目标分支：`test1`。本分支只基于 `E:\软件工程\applyguard-D-2` 开发。这里是**已执行工作的说明**；教师要求、修复前问题、详细测试计划和用例分别见 [01](01-课程要求与多视角评述.md)、[02](02-当前问题与实际测试报告.md)、[03](03-完整测试计划.md)、[04](04-详细用例与需求追踪.md)。逐次修复与失败过程见 [07](07-测试执行与修复记录-20261006.md)。

## 交付内容

| 用户任务 | 本分支实现或约束 | 验证情况 |
|---|---|---|
| 经历库真实可编辑、可靠保存 | 表单提交到后端草稿；原子写入 `data/local/`，成功响应才显示绿底；失败保留最后有效版本和未保存状态。 | 后端 93 项、浏览器保存/失败/刷新检查；当前 7 项脚本覆盖保存及刷新。 |
| 修改后证据一致 | 工作流使用当前草稿；改动经历不再继承旧种子的 claims/evidence；修改 JD、陈述或 ATS 映射值撤销旧决定。无证据手填句阻断复制。 | 单元/API 及浏览器反例；[最新核心 E2E](evidence/20261006-rerun-clean/browser-results.json)。 |
| 可选 PDF、竞赛 | 文本 PDF 提取预览后由用户确认替换；损坏、加密、扫描/无文本文件明确报错且保留旧稿。结构化竞赛/获奖表单、种子、schema 和来源页码。 | PDF/API 测试及较早扩展浏览器轮次；OCR 和复杂版面仍未支持。 |
| 中文与交互 | JD 原文上色并弹详情；简历卡片键盘焦点；模拟网申试填、个人信息可复制填写稿；演示文本尽量中文，仍不真实投递。 | 构建、冒烟和浏览器轮次；未完成真实用户研究、完整无障碍矩阵。 |
| 评价与可复核证据 | 保留英文旧基准，新建中文 v2 集并输出数据/种子 SHA256；全部测试日志、截图、Trace 和失败轮次单独留档。 | v2 40/40 是当前种子与规则的同分布回归，**不等于真实泛化准确率**。 |

这些工程任务对应课程对可运行全栈主流程、异常处理、人工修正、核心测试和 AI 评价的要求（C04–C07、C11）；老师没有规定本项目的 8 MB PDF、20 页、93 项测试或 40 条评价集为评分阈值。中文产品 UI 不改变英文最终报告和演示要求。不得把模拟 ATS 称为实际网申。

## 实际测试结论和原始日志

| 轮次 | 结果 | 证据 |
|---|---|---|
| 最新静态/单元门禁 | 后端 **93/93**；前端 Node **5/5**；构建、lint、中文 v2 benchmark、Git 忽略检查退出码均为 0。lint 保留 2 条警告。 | [门禁汇总](evidence/20261006-release-final/gates/gate-results.json)及同目录各项 `.log`、[环境快照](evidence/20261006-release-final/gates/environment.json) |
| 最新干净环境核心浏览器回归 | Chrome 155，**7/7 PASS**，页面脚本异常 0；唯一后端、全新测试草稿目录。 | [结果 JSON](evidence/20261006-rerun-clean/browser-results.json)、[命令/时间/退出码](evidence/20261006-rerun-clean/browser-run-metadata.json)、[截图](evidence/20261006-rerun-clean/01-saved.png)、[Trace](evidence/20261006-rerun-clean/browser-trace.zip) |
| 较早扩展浏览器轮次 | **13/13 PASS**，包含保存故障、保存中再编辑、ATS 映射改写、PDF 替换/损坏等。发生在最后两处 lint/ref 调整之前，**不与最新 7 项合并计算**。 | [结果 JSON](evidence/20261006-final-verified/browser-results.json)、[Trace](evidence/20261006-final-verified/browser-trace.zip) |
| 失败轮次 | 先有两个测试后端同时监听 8000，混用空白/种子草稿；之后有 Playwright 文本定位不唯一。两者按测试环境/脚本缺陷处理，保留原日志。 | [端口污染轮次](evidence/20261006-release-final/browser-results.json)、[选择器失败轮次](evidence/20261006-rerun-final/browser-results.json)、[进程清理](evidence/20261006-rerun-clean/server-cleanup-final.json) |

日志原则：原失败文件不覆盖；每轮单独目录并保留原始输出、测试输入、版本和退出码；`PASS` 只用于实际执行的检查点。详细规则见 [05-测试日志与留档规范](05-测试日志与留档规范.md)。计划的 110 条用例并未全部执行，不能把上表说成全量验收。

## 本地复现

在 Windows PowerShell 中，从仓库根目录执行；需要 Python、Node、npm 和 `requirements.txt`/`frontend/package-lock.json` 对应依赖。测试只用虚构数据，真实简历不要放入仓库或截图。

```powershell
cd E:\软件工程\applyguard-D-2
python -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
.\docs\testing-D2\scripts\Run-Repair-Gates.ps1 -EvidenceDir .\docs\testing-D2\evidence\<新运行编号>\gates
```

浏览器复测须先**保证 8000 端口没有旧后端**，再用新建且为空的绝对目录设置 `APPLYGUARD_LOCAL_DATA_DIR`；另一个终端运行 Vite，确认 `/api/v1/vault` 返回预期 4 条种子经历后运行脚本。给每次运行独立的 `D2_EVIDENCE_DIR`，不要覆盖本交付的日志。

```powershell
$env:APPLYGUARD_LOCAL_DATA_DIR='E:\软件工程\applyguard-D-2\output\一次性测试目录\local'
python -m backend.app
# 另一终端：npm.cmd --prefix frontend run dev -- --host 127.0.0.1
# 再另一终端：
$env:FRONTEND_BASE_URL='http://127.0.0.1:5173'
$env:D2_EVIDENCE_DIR='E:\软件工程\applyguard-D-2\docs\testing-D2\evidence\新运行编号'
node docs\testing-D2\scripts\Browser-Repair-Regression.cjs
```

当前浏览器脚本默认读取本机的 Playwright 模块和 Chrome 路径；换机器应设置 `PLAYWRIGHT_MODULE` 与 `CHROME_EXE`。当前脚本有种子项前置检查，但**不会自动关闭重复后端**；启动前须核对 8000 端口唯一监听者。正式复跑应按 [03 完整测试计划](03-完整测试计划.md) 扩展 Edge、移动宽度、复杂 PDF、跨标签、无障碍与独立 AI 留出集。

## 尚未关闭的问题

1. 编辑后的新经历与手动句可保持安全阻断，但尚缺上传新证明、后端核验并恢复可复制的完整闭环；竞赛奖项也未进入证据验证链。
2. 不同浏览器标签同时保存没有乐观版本冲突提示；复杂文本 PDF 识别未建立充分人工金标，扫描 PDF 不做 OCR。
3. 最新 7 项与较早 13 项尚未整理成同一版完整 E2E；110 条计划用例多数未执行。真实用户研究、独立中文 AI 评价、干净机器部署和英文课程报告/演示仍需后续完成。

发布停止线：无证据句可复制、改稿后展示旧证据、失败保存报成功、PDF 导入失败删除旧稿、发生真实网申提交，或私有 `data/local/` 被 Git 跟踪时，均不得宣布主流程验收。该分支不含真实个人草稿；`data/local/` 被 `.gitignore` 忽略。
