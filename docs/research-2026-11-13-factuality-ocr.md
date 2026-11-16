# 歧义和图片简历：论文、开源代码与验证边界

## 已观察的问题

- 280 条配对是模板生成；假定语义模型总是判等价时，140 条错改有 70 条漏过规则。它不是 Gemini 的真实漏放率。
- 真实 Gemini 曾将“约”加到错误指标：数值保护已修复该例，不能据此推断实际总体漏放率。
- 四份原始图片型 PDF 在原入口均被拒绝；另行增加 OCR 文字层后均能导入，但其中两份教育字段不完整。[原始实测](testing-report-2026-11-13-ambiguity.md)。

## 可以复用什么

| 方法 | 来源和定位 | 对项目的作用 | 边界 |
| --- | --- | --- | --- |
| 先选证据再生成 | [Attribute First, then Generate](https://aclanthology.org/2024.acl-long.182/)，ACL 2024 主会、Google Research 等；[Apache-2.0 源码](https://github.com/lovodkin93/attribute-first-then-generate) | 先限定原文片段，针对该片段生成并保留细粒度引用，减少错绑定风险 | 项目已有原子事实和证据来源；论文数据集并非简历，尚未直接接入或验证 |
| 完整性、精简度和归因分开评估 | [DocLens](https://aclanthology.org/2024.acl-long.39/)，ACL 2024 主会，含微软研究人员；[MIT 源码](https://github.com/yiqingxyq/DocLens) | 已保留原版汇总函数，用人工标注分别测事实保留与新增、引用情况 | 论文面向医学文本；汇总器不产生标签、不证明简历质量、不参与自动放行 |
| 原子断言与证据蕴含关系 | Amazon [RefChecker 论文](https://aclanthology.org/2024.emnlp-main.395/)和 [Apache-2.0 代码](https://github.com/amazon-science/RefChecker) | 已复用原版子句检查提示词和严格汇总；适配项目现有 Gemini 和已拆分事实，可选用于额外否决 | EMNLP 是 CCF-B；不是完整上游抽取流水线；适配判断有误拦风险，默认关闭 |
| 本地 OCR 和版面 | [百度 PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)；[PP-StructureV3 文档](https://www.paddleocr.ai/v3.1.0/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html) | 已复用项目现有本地 OCR，新增简历扫描件入口；可进一步试版面和阅读顺序 | 本次未接入 PP-StructureV3；模型和运行成本需另测，识别成功不代表字段完整 |
| 视觉模型 OCR | 微软 [MarkItDown OCR 插件](https://github.com/microsoft/markitdown/blob/main/packages/markitdown-ocr/README.md) | 可作为用户明确授权后的远程视觉方案候选 | 需要视觉模型；未配置或调用失败时可能跳过，当前未接入，不能视作本地 OCR |

会议类别以 [CCF 人工智能目录](https://www.ccf.org.cn/Academic_Evaluation/AI/)为准；ACL 主会为 A，EMNLP 为 B，不把 Findings 一概当作 A。论文中的性能数字不能直接迁移到简历。

## 本次实现及 CLI

1. 首页简历导入选择“本地 OCR”，最多 5 页，逐页渲染并调用 `backend/services/evidence_parsers.py` 的本地 OCR；任何一页识别失败则拒绝返回不完整结果。OCR 与规则抽取均在本机，仍需人工逐项核对。默认的文字 PDF 和动态模型模式不变。PaddleOCR 包与模型已有 E 盘安装，PDF 渲染临时文件使用系统 TEMP，可通过运行后端前配置 TEMP/TMP 指向 D 或 E 盘。
2. 固定引入 DocLens 的 `aggregate_scores.py`，上游版本 `e77cfc9f200c03cde23c6a8d1ca7b5f2c499e0c7`，许可见 `third_party/doclens/LICENSE`。仅汇总已有标签。`claim_precision` 表示生成事实是否有依据，`claim_recall` 表示人工列出的原文事实是否保留；标签 `1` 支持、`0` 不支持、`null` 未知，未知不进分母且单独计数。引用 precision/recall 使用上游定义，不等同信息检索意义上的标准引用召回率。所有例子为虚构数据。
3. 原文原子核验完整通过时，润色优先使用已验证的逐字引文作为输入，保留来源版本、哈希和文字位置，并保留检索到的纠正与反驳材料；现有最终核验和材料快照复查仍独立执行。对于明确可识别的多个方案或多个指标，规则比较名称与数值及近似限定的对应关系；对应不上就保留原文供人工确认。这是有限模式匹配，不保证覆盖所有语言和歧义。
4. 引入 RefChecker 提示词及汇总函数（上游版本 `1df1b25cee792ba2b171302e31ca4f768bd67703`，Apache-2.0，见 `third_party/refchecker/LICENSE` 和 `NOTICE`）。检查使用已有原子事实及精确引文，通过现有 Gemini 客户端请求 JSON；不是上游完整 RefChecker 或其三元组抽取器。可选设置 `APPLYGUARD_REFCHECKER_AUDIT=1` 并重启后端，额外逐项检查改写；Neutral、Contradiction、缺引文或服务失败都不自动采用，Entailment 也无法覆盖原有检查。默认关闭：增加调用次数、费用和误拦风险。报告中 `refchecker_review` 可查看该步骤结果。

```powershell
# 可选评测依赖；按需要将 pip 缓存设置到 E 盘
..\.venv\Scripts\python.exe -m pip install -r requirements-audit.txt
..\.venv\Scripts\python.exe scripts/evaluate_doclens_audit.py --input eval/doclens-example.json --output output/test-reports/doclens-new.json
# 五条虚构、预先拆分的短事实会发给配置的模型；API 密钥不落盘
..\.venv\Scripts\python.exe scripts/evaluate_refchecker_pilot.py --input eval/refchecker-pilot.json --output output/test-reports/refchecker-new.json --live
# 在本地逐份读取用户指定的 PDF；输出仅含条目数量和状态，不保存简历正文
..\.venv\Scripts\python.exe scripts/evaluate_resume_ocr.py --output output/test-reports/ocr-new.json path/to/a.pdf path/to/b.pdf
..\.venv\Scripts\python.exe scripts/run_test_report.py --label ocr-doclens --all
```

## 推荐下一步（尚未完成）

1. 建立独立人工标注集，覆盖职责互换、生产／测试环境、指标对象、否定与限定语；对同一组分别报告错改漏放、正确改写误拦、模型不可用、修复后结果及置信区间，避免与模板开发集重叠。280 条旧模板经规则复测，错改漏过从 70 降至 50，正确改写无新增误拦；剩余职责互换 20、环境切换 20、否定状态 10。这不是模型实际漏放率。
2. 将“主体、动作、对象、数值、单位、近似/上下界、条件、时间、证据位置”作为绑定单元，对指标归属进行校验；抽取有歧义、模型不可用或无依据时要求人工确认，不用通用三元组替代限定语。
3. 建立教育字段的独立真值，扩展中英文学校、学历、时间同一行及跨行、多条教育经历；对比版面识别前后学校、学历、专业、起止时间的召回率，并检查数字/文字 OCR 的准确性。

## 本次验证

### 事实绑定与逐项复核续测

- 基于相同 280 条合成案例、乐观模拟语义裁判：错改漏放 70 → 50，正确改写误拦 0，新增回归 0。[对照报告](../output/test-reports/ambiguity-link-20261113/report.json)。这只是规则压力测试，不代表 Gemini 的实际错误率。
- Gemini 对 5 条虚构、人工预先拆分的事实运行改编版 RefChecker 提示词：4 条符合预标标签；一条英文职责案例被模型判为矛盾，作者预标为证据不足，可能误拦。标签尚未由独立标注者复核，不能据此估计准确率。[本机记录](../output/test-reports/refchecker-pilot-final-20261113.json)。初次记录中把不同案例汇总为一项 strict 结果没有意义，已保留原记录并生成[去除该项的勘误](../output/test-reports/refchecker-pilot-20261113-corrected.json)；当前 CLI 不再跨案例汇总。
- 完整后端回归 349 项通过、0 跳过；其后补充保留纠正／反驳材料，相关 49 项再次通过。[全量报告](../output/test-reports/20261113_205332_918973_refchecker-veto-final/report.json)、[补充回归](../output/test-reports/20261113_205526_364799_fact-links-targeted/report.json)。现有运行中的后端需重启才能加载修改。

### 扫描件与 DocLens 上轮验证

- 前端构建通过，前端 smoke 39 项通过。后端全量回归 338 项通过、0 跳过（在补充 1 项 HTTP 用例和评分输入校验之前）；随后相关模块 46 项通过。[全量报告](../output/test-reports/20261113_183952_877935_research-ocr-doclens/report.json)、[补充回归](../output/test-reports/20261113_184202_811887_ocr-doclens-targeted/report.json)。
- 使用 E 盘已安装的 PaddleOCR，四份图片 PDF 通过新的 `offline_ocr` 本地入口；处理约 35–59 秒/份。[匿名统计](../output/test-reports/ocr-import-pilot-20261113.json)。

| 截图 | OCR 导入 | 教育条数 | 项目条数 | 对照说明 |
| --- | --- | ---: | ---: | --- |
| 3 | 成功 | 2 | 3 | 计数并非完整性结论 |
| 6 | 成功 | 1 | 1 | 截图可见 2 条教育，仍有遗漏 |
| 7 | 成功 | 0 | 6 | 截图可见英文教育，仍有遗漏 |
| 14 | 成功 | 4 | 2 | 截图可见 2 条教育，结果可能重复或误分，尚未逐条审阅 |

这些条目数来自规则抽取，不能直接当准确率；OCR 可读性、所有项目与教育的对应关系都未完成独立标注。新入口仍须重启正在运行的旧后端才能使用。
