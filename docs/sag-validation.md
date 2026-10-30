# 实测记录：SAG 与原子事实核验

日期：2026-10-29。上游 ApplyGuard：43416faf6b575b9f4d1afc9ae834e87e89a2cb61（2026-10-22 20:15:03，北京时间）。
实际模型：ChatAnywhere 的 gpt-4o-mini；引擎：zleap-sag 0.15.0 full_expand，两跳，支持／反驳／更正三路查询。

本次真实 HTTP 端到端试验使用6份虚构原件、5组正反陈述，共10条固定输入，并另检验5条润色输出。是作者设计并标注的小样本，不是独立标注或统计代表性数据。

| 项目 | 有依据原句 | 问题原句 | SAG润色后再原子核验 |
| --- | --- | --- | --- |
| atlas | VERIFIED | BLOCKED | VERIFIED |
| beacon | VERIFIED | BLOCKED | BLOCKED |
| delta | VERIFIED | BLOCKED | VERIFIED |
| forge | NEEDS_REVIEW | NEEDS_REVIEW | NEEDS_REVIEW |
| cedar | NEEDS_REVIEW | NEEDS_REVIEW | NEEDS_REVIEW |

固定输入结果：漏放 0/5；严格误拦 0/5；复核 4/10；有依据陈述自动通过 3/5。
正确陈述未自动通过率为 2/5；因此“零误拦”不能理解成正例都通过。全部检索／模型流程未报告运行错误，但有原子覆盖或格式不完整的复核情况。

## 一个具体失败

SAG润色输出保留了“Alex led the Beacon project and implemented its React frontend.”；原件却写“Priya led the project and implemented React.”，Alex负责Redis。
输出附带的检索原文也包含这条分工和项目别名材料。这证明检索辅助润色仍可能保留职责错配。最后一列记录后置原子核验的实际处理结果，不能把SAG预览的全部NEEDS_REVIEW当成检测效果。

## 延迟与质量限制

- good：427.0 秒（整个5句请求）
- bad：113.69 秒（整个5句请求）
- sag_polish：222.27 秒（整个5句请求）
- polish_atomic：174.03 秒（整个5句请求）

good 包含首次建索引，其余复用同一来源快照索引；不是单句延迟、p95或受控性能对比。首次抽取有一次结构校验重试，最终建立索引。整个流程仍偏慢，下一步应加限定并发、相同快照检索缓存和清晰进度。不得为提速删掉反驳、更正材料。

拆分和判定使用同一模型，不能视为独立裁判。有依据的Forge句出现覆盖检查未通过，Cedar句出现原子结果结构不完整，均保留复核。这个试验没有相同生成提示下的向量RAG消融，不证明SAG本身优于普通RAG；更不证明零幻觉。5个负例零漏放的单侧95%漏放率上界仍约45%。

## 软件验证

- Python 回归：155项，154通过；1项因没有paddleocr而跳过（可选图片OCR，非SAG测试）。16项新增机制及HTTP集成测试包含在内；可控假模型测试不计入上方模型准确率。
- 前端：构建通过；16项测试与预录冒烟检查通过。
- Lint：无错误，保留4条原有组件警告；新增组件没有警告。
- 界面检查：两种模式可选、模型不可用显示复核、不可点击确认绕过、历史恢复使旧结论失效、下一步被禁用；截图见output/sag-app-preview.jpg。

代码在本机，真实模型调用只发送虚构材料。交付包不含密钥、.env、node_modules、.venv或用户材料／索引。启动和完整改进标准见[sag-grounding.md](sag-grounding.md)。原始结果见output/integration-live.json，可逐条复查原子事实和原文位置。
