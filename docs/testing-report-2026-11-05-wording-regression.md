# 2026-11-05 简历润色扩展回归

本轮测试 370 条改写。340 条使用同一输入比较修复前后，另外两批共 30 条自然语句先计首次成绩，再根据失败样例修改并重测。另用 60 条职业陈述检查工作流能否保留材料状态。

**定向测试表明，程序能识别更多数值和归属错改，也少拦了一些合理改写。真实模型在新材料上的端到端幻觉率，本轮尚未测得。** 离线压力测试故意让模拟语义裁判对所有建议都回答“等价”，模拟修复器重复原建议。这样能单独测出程序还漏过哪些错误。这里的“放过”指通过措辞检查，实际进入草稿还要经过材料检查。

## 固定配对

| 数据与来源 | 样本 | 错改漏过，旧 → 新 | 合理改写误拦，旧 → 新 |
| --- | ---: | ---: | ---: |
| [10.31 开发及评估](../eval/asu_ablation/fact-lock-challenge-2026-10-31.json) | 40 | 0/20 → 0/20 | 0/20 → 0/20 |
| [10.31 确认集](../eval/asu_ablation/fact-lock-confirmation-2026-10-31.json) | 20 | 0/10 → 0/10 | 0/10 → 0/10 |
| [11.05 既有审核集](../eval/review-holdout-20261105.json) | 10 | 0/5 → 0/5 | 0/5 → 0/5 |
| [10.30 ASu 历史建议](testing/runs/2026-10-30/main/20261030_172733_803092_asu-reviewed-replay/report.json)中有改动、有暂标且旧判断完整的配对 | 46 | 0/13 → 0/13 | 2/33 → 1/33 |
| 新增双语数值组合，为同一原句构造正确与错误改写 | 224 | **96/112 → 0/112** | **16/112 → 0/112** |
| 合计 | 340 | 96/160 → 0/160 | 18/180 → 1/180 |

数值组合覆盖起止对调、不同指标互换、约数换了对象、百分比与百分点、中英文单位。多个用例共享句型，不能当成 224 个独立项目。历史 ASu 中少误拦的一条保留了估算人 Morgan。仍被拦的一条仅写“预计降低 20%”，遗漏估算人，旧标签仍记为合理，以便同口径比较。[逐项结果、输入和代码指纹](testing/review-20261105/numeric-regression.json)

## 自然语句的首次成绩和复测

| 新写法 | 首次运行 | 修复后用原题重测 |
| --- | --- | --- |
| 第一批 16 条 | 错改漏过 3/8，合理改写误拦 2/8 | 漏过 0/8，误拦 0/8 |
| 第二批 14 条，在第二轮修复后编写 | 错改漏过 3/7，合理改写误拦 0/7 | 漏过 0/7，误拦 0/7 |

第一批暴露了把谈论话题的英文 about 当成“约”、误拦秒与毫秒换算、遗漏采访者和被采访者互换、职责主次互换，以及删除支出“待核定”。第二批首次漏掉“待审批”变为“已获批”、委托方与受托方互换、“两周”变成“两天”。修复后也允许“两周”写为“十四天”，工作日仍单独处理。

同题重测证明已发现的缺陷得到覆盖。最后一次修复后没有再测新的盲集。材料和期望由开发方编写，没有独立真人标注。[第一批样本](../eval/wording-prose-20261105.json) · [首次](testing/review-20261105/numeric-prose-holdout.json) · [重测](testing/review-20261105/numeric-prose-retest.json) · [第二批样本](../eval/wording-transfer-20261105.json) · [首次](testing/review-20261105/numeric-transfer.json) · [重测](testing/review-20261105/numeric-transfer-retest.json)

## 后端实际行为与真实模型

- 核验时，如果陈述中同一指标的起止值与引文正好相反，或者百分比与百分点被互换，程序会保留复核。测试走逐原子、整句及旧 JSON 接口。存在另一条支持正确方向的引文时，继续使用语义核验判断。
- [职业案例](../eval/career_holdout.py)共 6 项经历、60 条陈述。注入预设材料结论后，经正常润色工作流改变句尾标点，30 条材料支持、22 条矛盾、8 条不足的最终状态全部正确保留。有冲突时保留原文。这项测试隔离了状态传递，未测模型判断材料的准确率。
- 新发起一条虚构估算人用例，Gemini 网关返回 HTTP 403，原因为余额不足，停止继续调用。用[原有真实 Gemini 判断缓存](testing/review-20261105/wording-sdk-decisions.json)重放，暂标合理采用 24/25、暂标错误采用 0/6，另有 2 条未改、15 条缺结果，与上轮相同。本轮没有新测的端到端错改率、实际用户复核率或逐条费用。

## 2026-11-05 执行记录

| 顺序 | 操作 | 记录 |
| --- | --- | --- |
| 1 | 冻结输入、标签与修复前的 D 盘工作树指纹 | 保存 340 条基线；用一条虚构请求检查模型服务 |
| 2 | 修复数值归属和等价单位 | 重跑同一 340 条，单列 116 条既有配对和 224 条参数组合 |
| 3 | 修复估算人和原子引文校验，扩大到第一批自然语句 | 首次有 5 条失败。修复后重测通过。全量后端 310 项，1 项跳过 |
| 4 | 加第一批回归关卡，再用第二批新文本检查 | 首次有 3 条失败。期间全量后端 311 项，1 项跳过 |
| 5 | 修复审批、日／周换算与明确的委托方互换 | 最终后端 **312 项，311 通过、1 跳过**（可选 PaddleOCR 未安装），耗时 20.5 秒。前端 smoke **32/32**，TypeScript 与生产构建通过。依赖检查通过，前端静态检查退出成功，有原有警告和构建包体积提示 |

## 团队复现

以下命令在项目根目录离线运行。本机输出写入 output/test-reports。若已标注样例出现新增漏过或误拦，比较脚本保存逐项结果并以非零状态退出。默认后端测试同时运行数值组合、首批自然语句及 60 条状态用例。

~~~powershell
$p = '.\.venv\Scripts\python.exe'
$report = 'docs/testing/review-20261105'
& $p -B -m unittest discover -s tests
& $p -B scripts/evaluate_wording_regression.py --baseline "$report/numeric-regression.json" --output output/test-reports/numeric-repeat.json
& $p -B scripts/evaluate_wording_regression.py --prose --baseline "$report/numeric-prose-holdout.json" --output output/test-reports/prose-repeat.json
& $p -B scripts/evaluate_wording_regression.py --prose eval/wording-transfer-20261105.json --baseline "$report/numeric-transfer.json" --output output/test-reports/transfer-repeat.json
& $p -B scripts/replay_wording_pairs.py --audit-cache "$report/wording-sdk-decisions.json" --audit-output output/test-reports/sdk-repeat.json
npm --prefix frontend run smoke
npm --prefix frontend run build
~~~

下一轮应使用新的项目材料，实测“模型生成、尝试修复、重新核验、最终采用”。分别统计产生多少错改、其中多少被修好或漏放，以及多少合理改写可采用。通用 FELM 的事实正确性标签与是否保留简历原意回答不同问题，本轮没有把历史 FELM 分数计入润色成绩。
