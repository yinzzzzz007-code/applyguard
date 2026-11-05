# ASu润色对照实验

- 日期：2026-10-30T16:54:55.728909+08:00 — 2026-10-30T17:05:17.969916+08:00（北京时间）
- 状态：PARTIAL；完整配对 9/60；模型 gpt-4.1-mini，temperature=0。
- 此表为自动盲审结果；人工/代理逐条复核修订另存，不覆盖原始记录。

| 写作策略 | 有效 | 发生改写 | 原始错改 | 旧保护留下错改 | 新保护留下错改 | 旧误拦/安全改写 | 新误拦/安全改写 |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre_asu | 9 | 8 | 4 | 2 | 2 | 1/4 | 1/4 |
| asu_v1 | 9 | 9 | 1 | 1 | 1 | 3/8 | 2/8 |
| asu_fixed | 9 | 8 | 3 | 1 | 1 | 1/5 | 1/5 |

- 分母与完整检查见 manifest.json；每次调用结果按批次保存。
- 输入/输出 token 和耗时见 report.json。

- 60 synthetic variants across 20 templates, not 60 independent real resumes.
- Blinded judge uses the same model family, not independent human annotation; inspect disagreements.
- Identical fixed sources isolate polishing; no SAG retrieval or Agent benchmark.
- Retries of malformed/transport responses are bounded; semantic failures are not retried.
- Every adopted suggestion still requires user confirmation in the product.
