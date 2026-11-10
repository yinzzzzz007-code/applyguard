# 2026-11-05 简历润色等价判断与单次修复配对报告

在完成对照的 25 条暂标安全改写上，旧流程采用 20 条，新流程采用 24 条。6 条暂标错改在两版中均未自动采用。此次改善集中在少拦合理改写。暂标、重复场景和 15 条未完成样本限制了对实际错改率的判断。

## 对照口径

输入来自 10 月 30 日的[冻结建议与旧流程判定](testing/runs/2026-10-30/main/20261030_172733_803092_asu-reviewed-replay/report.json)。从 57 条中选出旧判定完整且有 SAFE／WRONG 暂标的 48 条。逐条用 SHA-256 核对同一份建议。未重新生成建议，也未重测 SAG 召回。原句、建议和引文未变时复用当日原子核验。新修复文本需要重新核验。历史标签仅用于计分，未提供给模型。

新流程使用 [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) 的结构化输出，通过 [Chat Completions 适配器](https://openai.github.io/openai-agents-python/models/) 连接 ChatAnywhere，请求模型为 `gemini-3.1-flash-lite-preview`。SDK 用于判断改写和最多一次修复，每次调用一个模型回合，关闭 SDK 轨迹外发。SAG 仍负责找原件，原子核验仍负责检查事实支持。

| 同一批配对 | 旧流程 | 新流程 |
| --- | ---: | ---: |
| 暂标安全且确有改动，建议进入草稿 | 20/25（80%） | 24/25（96%） |
| 暂标错误且确有改动，错改进入草稿 | 0/6 | 0/6 |
| 原句与建议相同 | 2 条 | 2 条，单列 |
| 未获得可用新判断 | — | 15/48（暂标安全 8 条、暂标错误 7 条） |

有效的改写对照是 31 条，加上 2 条未改动共 33 条。6 条错误建议仅覆盖两个场景，每个场景有三个生成版本。六次均触发修复，均未产生可采用的新文本。真人标签、实际用户复核率及可归因的逐条费用本轮未取得。所报采用率只统计是否进入草稿；材料支持度另记。

## 逐条查看旧流程拦下的五条

| 冻结样本 | 建议改变了什么 | 最终结果 |
| --- | --- | --- |
| en_assist_1 / asu_v1 | 在 architecture 前加 the。负责人与 Avery 审查 12 条 SQL 的信息仍在 | 采用。原句证据不足，保留标记 |
| zh_alias_2 / asu_fixed | 调整语序，许宁负责 PostgreSQL 恢复测试、林岚负责 Redis 缓存，两人的归属均保留 | 采用。证据不足 |
| zh_prototype_1 / asu_fixed | “把”换为“将”，保留本机相同负载、中位耗时 200 至 140 毫秒及尚未上线 | 采用。证据不足 |
| zh_prototype_3 / asu_fixed | 另一角色同样将“把”换为“将” | 采用。证据不足 |
| en_pending_2 / asu_fixed | “Morgan 估算成本可降低 20%”变为“预计成本降低 20%”，估算人的归属消失 | 保留原句。首次 Gemini 判断等价，最终程序检查发现遗漏；加规则后尚未实测该条能否成功修复 |

首次模型判断以上五条均等价。我们在检查估算人示例后补入归属规则，用已保存的真实判断离线重放最终程序。第五条的历史 SAFE 暂标保持原值，方便复现比较。四条新增采用均只更新草稿，未提升证据级别。逐条判定、输入指纹和未完成清单见[最终重放记录](testing/review-20261105/wording-final-pairs.json)。

## 2026-11-05 各次执行

| 执行 | 观察 |
| --- | --- |
| 真实 SDK 冒烟 | 用虚构材料将“协助 SQL 测试”夸大为“主导”，Gemini 判断含义改变，触发修复，原错误建议被拦下 |
| 第一轮，11:53 UTC 开始 | 169 秒。48 条中 16 条建议被采用、3 条保留原句、2 条未改动、27 条调用失败 |
| 断点续跑，12:01 UTC 开始 | 本轮 169 秒。保留成功结果，优先补五条疑似误拦，串行重试。服务返回 HTTP 403 余额不足，停止后续付费调用 |
| 最终规则离线重放 | 重新检查 31 个已完成的改写，锁定估算人以后采用 24 个冻结建议。15 条缺失没有计为成功拦截 |
| 工程回归 | D 盘项目虚拟环境：后端运行 305 项，304 通过、1 跳过。前端 smoke 32/32 通过，TypeScript 与生产构建通过，有现有包体积提醒。依赖一致性检查通过 |

工程用例覆盖合理同义改写、职责升级、删除“约／仅离线／尚未上线”、丢失估算人、一次修复后再次判断、最终文字被原子核验拦下、修复成功后按最终文字指纹采用、材料不足时不升格，以及用户确认稿的导出。模拟模型的回归用于验证分支行为，和上表真实 Gemini 配对分开统计。

## 复现

在项目根目录，用项目虚拟环境运行下列命令。真实重放需要通过本地环境设置 `APPLYGUARD_AI_API_KEY`。断点文件位于本机 `output/test-reports/`，其中保存逐次调用结果。另附[脱敏 SDK 判断缓存](testing/review-20261105/wording-sdk-decisions.json)，只保留虚构案例建议、判定及修复状态，可离线复现最终规则。

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests
.\.venv\Scripts\python.exe -B scripts/replay_wording_pairs.py --workers 1
.\.venv\Scripts\python.exe -B scripts/replay_wording_pairs.py --resume output/test-reports/wording-pairs-20261105T120122138022Z.json --workers 1
.\.venv\Scripts\python.exe -B scripts/replay_wording_pairs.py --audit-cache docs/testing/review-20261105/wording-sdk-decisions.json --audit-output docs/testing/review-20261105/wording-final-pairs.json
```

`frontend` 目录执行 `npm run smoke` 和 `npm run build`。后续真实模型优先复测估算人的修复，再补上 15 个未完成配对。新的独立材料需要覆盖不同人物归属与限定语，才能判断本批观察能否推广。
