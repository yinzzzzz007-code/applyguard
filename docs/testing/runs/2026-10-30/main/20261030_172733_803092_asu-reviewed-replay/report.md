# ASu真实建议复核与离线重放

- 日期：2026-10-30T17:27:33.803092+08:00（北京时间）
- 实际生成 57 条建议；三组完整生成配对 15 条；排除一条歧义样本后主分析 14 条。
- 复核者：Codex；不是独立人工标注。原自动评分保留，未覆盖。

| 写作策略 | 可比较样本 | 实际改写 | 错改（含关键信息丢失） |
|---|---:|---:|---:|
| pre_asu | 14 | 13 | 2 |
| asu_v1 | 14 | 14 | 3 |
| asu_fixed | 14 | 13 | 2 |

| 保护重放（完整配对） | 错改数 | 旧保护留下错改 | 新规则重放留下错改 | 安全改写数 | 旧误拦 | 新规则误拦 |
|---|---:|---:|---:|---:|---:|---:|
| pre_asu（n=8） | 2 | 0 | 0 | 5 | 0 | 0 |
| asu_v1（n=8） | 2 | 1 | 0 | 6 | 1 | 1 |
| asu_fixed（n=8） | 2 | 0 | 0 | 5 | 0 | 0 |

- 不能据此认定ASu降低错改率；配对样本很少，且评分器存在标点误判及遗漏限定语漏判。
- 60条扩大对照已冻结，余额不足中断；完成后须另报未经开发调参的新样本结果。

- Assistant reviewed, not independent human gold; strict scope preservation rubric.
- One ambiguous template excluded from primary analysis for ALL arms.
- Guard replay uses the SAME cached v1 preservation-model responses and cached atomic verdicts; no paid calls.
- No score for new citation alignment or changed prompts: those need fresh end-to-end model runs.
- Trials encountered HTTP 403 insufficient balance; 60 paired cases have NOT completed.
- Seen failures informed fixes; replay is a regression diagnostic, not an unseen holdout.
