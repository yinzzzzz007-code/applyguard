# C 阶段逐项验收（2026-10-03）

结论：Proposal 阶段 C 的本地技术交付已具备；Git 发布未执行。不能据此宣称最终完整产品、真实用户研究或通用事实核验已经完成。检查依据为项目总分工中 C 职责、C 阶段交付、三个演示，以及 B 交接文档更新后的 29 测试基线。

## 要求、实现和验收证据

| 要求 | 实现/证据 | 状态与边界 |
| --- | --- | --- |
| 从 B 接手，保留 A/B | C 基于 `64cae15`；A/B 原 29 测试、数据、冻结 contracts 不变 | 已验收；C 独立分支交付 |
| JD 技能/经验/学历/职责、hard/preferred、原文片段 | `jd_parser.py`；`test_categories_and_inherited_preferred`、`test_model_keyword_quote_cannot_upgrade_preferred` | 已实现；离线词典有限，模型事实仍须过校验 |
| Prompt/模型封装、格式和 Schema 校验 | `prompts.py`、`model_client.py`、`schema_validation.py` | 已实现；低成本默认 gpt-4o-mini、2048 输出 token，均可配置 |
| malformed JSON、超时、一次重试、Fallback/安全停止 | `test_member_c.py` Parser tests；`test_c_audit.py` transport tests | 已验收；认证失败不重复收费调用 |
| 注入、虚构词、中文和否定语境、伪造引用 | 两份 C 测试的 grounding/injection/negation cases | 已覆盖已知模式；不保证识别任意语义攻击 |
| Claim→Evidence、归属/状态/可信度 | `claim_validator.py`；foreign/missing/partial evidence、cross-candidate、low-confidence tests | 已实现；通过 claim_id 和 evidence_ids 关联来源，不修改冻结 Schema |
| SUPPORTED/NEEDS_CONFIRMATION/BLOCKED | 映射既有 `VERIFIED/NEEDS_REVIEW/BLOCKED` | 已实现；不改 A 枚举；VERIFIED 仅代表给定 Vault 支持 |
| 虚构技能/指标、角色/范围夸大、团队个人化、计划交付、分母/口径 | `test_asu_failure_cases_have_fragments_risk_and_blocked_stop` 等 | 已断言状态、片段、解释、风险、停止点；复用 B 的 ASu 算术 |
| L0 普通、L1 展示来源、L2 歧义、L3 敏感严重 | `risk_engine.py` 的 `field_controls`；L0–L3 tests | 已实现字段控制；D 展示 UI；与汇总风险等级分开 |
| BLOCKED 不可用确认绕过 | blocked-sensitive / missing-verification / unsupported-selected-claim tests | 已验收，映射字段也同步 BLOCKED |
| 九模块 Router、每步一次、错误传播、审计 | `skill_router.py`；retry trace、downstream failure tests | 已验收；任何模块失败跳过后续执行，返回审计；不持久化 |
| 固定 endpoint/envelope、B 接口、禁止自动提交 | 完整 API 测试和集成测试；最终停止在 Human Confirmation | 已验收；只有现有 health/mock 路径，未添加 submit |
| Resume Matcher 最小复用 | `third_party/resume_matcher_keywords.py`；`THIRD_PARTY_NOTICES.md` | 选取原样帮助函数并实际调用；完整提取函数与本项目格式不适配 |
| Plan-Then-Execute | 自行实现 Router；third-party notices 记录未复制原因 | 与已采用方案一致；不是复用该仓库的交付 |
| 小型 Benchmark 和评价 | `eval/c_cases.json`、`eval/c_benchmark.py`、`eval/results/c-offline-audit.json` | 10 JD/40 Claim，超过分工要求的 5–10 JD/20 Claim；虚构回归集 |
| JD Parsing Accuracy / Grounded / Unsupported Block | `docs/ai-evaluation-C.md`，补接受精度/误拦率/混淆矩阵 | 已给口径；JD 用词项 precision/recall，非任意语义准确率 |
| 正常、无证据阻止、超时 fallback 三例 | `python -m demo.run_c_cases` | 全部可复现，始终离线 |
| 报告/PPT 原始内容、HANDOFF | `docs/ai-evaluation-C.md`、`presentation/slide-content-C.md`、`HANDOFF.md`、`C_TO_D_HANDOFF.md` | 已更新；PPT 最终装配为 D 职责 |
| C 对研究材料提供反馈 | `docs/user-study/C-failure-case-review.md` | 已审阅；真实研究结果尚未提供，未捏造 |
| `proposal-v0.3-ai-core` | C 独立分支与标签 | 已获用户授权发布；不改 B/main |

## 测试结果与复现

Python 3.11+，安装 `requirements.txt` 后运行：

```sh
python -B -m unittest discover -s tests -v
python -B -m eval.c_benchmark
python -B -m demo.run_c_cases
```

本次完整回归为 76 项（A/B 29 + C 初版 24 + 本次审计 23）。全部为离线/模拟调用；此次审计没有付费 API 请求。Benchmark 当前结果：JD 词项 precision/recall 0.973/0.973；Claim 状态 40/40；无依据阻止 28/28；应通过 4/4；应复核 8/8。正样本很少、与开发规则相关，不能用于泛化或用户研究结论。

历史 gpt-4o-mini 实测数据在评价报告中明确标为修复前快照。本轮没有为获得“最新实测”重复消耗预算。

## 给 A、B、D 的后续事项

A 负责发布与持久化审计/版本，发布前审阅 C 差异及许可证。B 提供真实匿名研究失败例，A 确定需求后 C 再扩充测试。D 替换 ATS fixture、展示来源与 field_controls、实现人工确认与最终手动提交 UI，组装 PPT/视频。页面扫描、真实 ATS 填写、数据库 CRUD、最终产品可用性研究均不属于此次 C 接管。

目前默认无 key/无 parse_mode 请求仍走 A/B 兼容 fixture。验收 C 必须指定 `offline`（零费用）或 `dynamic`（有 key 时调用模型）。不设置 key 也能完成本阶段测试和演示。

## 局限

核验是给定 Vault 下的保守规则，不会打开外部证据证明真实性；指标多义、复杂中文释义、混合否定和任意改写可能误拦或漏检。未知改写尽量复核或阻止，但不能声称解决所有自然语言事实核验。真实泛化评价、D 页面执行及 A 审计存储仍需后续阶段验证。
