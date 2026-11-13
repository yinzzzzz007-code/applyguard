# 2026-11-13：职责、环境与部署状态复测

本轮修复先前 280 条合成压力集中剩余的 50 条规则漏拦：人员与职责互换 20 条、测试／生产环境变化 20 条、英文尚未部署变成已部署 10 条。在语义裁判被故意设为总判等价的条件下，旧集 140 条预设错改全部被规则拦截，140 条预设合理改写全部保留。此前规则漏拦 50 条；这不是 Gemini 的真实漏放率。

`fact_lock.py` 对明确出现的双人职责做绑定，对明确的测试、预发布、生产、沙箱环境的变化要求复核；`edit_invariants.py` 支持英语被动形式的未部署／发布。明确无法对应或出现规则冲突时保留原文。规则是有限的模式识别，不能保证覆盖所有同义句、隐含否定或复杂职责。

## 歧义测试

| 测试 | 结果和边界 |
| --- | --- |
| 原 280 条 | 140 条错改拦截 140，140 条合理改写误拦 0；与上轮比较修复 50，新增回归 0 |
| 新增 2,800 条 | 14 类模板，各 100 条合理、100 条错改；规则在模拟总判等价时漏拦 0、误拦 0。案例共享模板及参数，不是 2,800 条独立人工标注实例 |
| 原有 340 条 | 160 条预设错改均拦截，180 条合理改写中 1 条既有保守误拦；没有当作新增退化 |
| 已冻结的 16 条文字案例 | 8 条合理改写保留，8 条预设错改拦截；标签为作者暂标，不是独立人工盲评 |
| Gemini，28 条合成短句 | 14 条合理改写接受；14 条错改中 11 条保留原文或拦截、3 条经模型修复后通过措辞审核。人工对照这 3 条修复未发现测试目标变化，但 CLI 原始状态仍是 `REQUIRES_REVIEW`；不代表完整证据核验或导出通过 |

规则结果见本机 `output/test-reports/ambiguity-50-repair-20261113/report.json`、`ambiguity-broad-20261113/report.json`、`wording-50-repair-20261113.json` 和 `prose-50-repair-20261113.json`；模型记录为 `ambiguity-live-50-repair-20261113/report.json`。`output/` 含本地测试材料，被 Git 忽略；本摘要随仓库保存。

## 图片简历实测

在 E 盘已有 PaddleOCR 上本机测试用户提供的第 1、2、6、7 张截图对应图片 PDF，均成功进入本地 OCR 导入。第一次导入发现英文教育／经历遗漏；修复学校分组、英文经历标题、独立日期行以及中文志愿者／项目标题后，对保存的 OCR 正文在本机回放，按截图中可见条目数进行比较：

| 截图 | 预期并提取的教育／经历／项目数 | 边界 |
| --- | --- | --- |
| 1 | 原入口 OCR：2／1／2 | 此次仅复核计数，未逐字段核验 |
| 2 | OCR 正文回放：3／2／0 | 三所学校、两段经历及起止时间抽样核对；并非所有描述均逐字验真 |
| 6 | OCR 正文回放：2／2／2 | 两条经历包含一条志愿经历；仍需核对正文、时间和角色 |
| 7 | OCR 正文回放：1／1／3 | 另一所学校名称在截图中被遮挡，不能推测或补造 |

实际 OCR 第一轮和修复后的第二轮分别见 `output/test-reports/ocr-resume-recheck-20261113.json` 与 `ocr-resume-postrepair-20261113.json`；最终分组修复使用之前保存的本地 OCR 正文回放，见 `resume-replay-delivery-20261113.json`，不是再次执行完整 OCR。只比较条目数不保证字段或文字都正确。OCR 正文、截图和真实简历不提交到仓库。

另外对截图 3、6、7、14 中先前已脱敏的 8 条短句运行 Gemini 措辞审核：4 条合理改写接受；4 条预设错改中 2 条保留原文或拦截，另 2 条经修复后通过措辞审核，人工对照未发现测试目标变化。CLI 原始状态仍为 `REQUIRES_REVIEW`。完整简历和联系方式没有发送给模型；这不等于原件核验、最终导出或整份简历完全正确。[本机记录](../output/test-reports/resume-wording-recheck-20261113/report.json)。

## 复现 CLI

```powershell
..\.venv\Scripts\python.exe scripts/evaluate_ambiguity_expansion.py --output output/test-reports/ambiguity-new
..\.venv\Scripts\python.exe scripts/evaluate_ambiguity_broad.py --output output/test-reports/ambiguity-broad-new
..\.venv\Scripts\python.exe scripts/evaluate_wording_regression.py --prose --output output/test-reports/prose-new.json
..\.venv\Scripts\python.exe scripts/evaluate_ambiguity_live.py --cases output/test-reports/ambiguity-new/cases.json --output output/test-reports/live-new --sample-index 1
# 本地 PDF 实际 OCR；可选填写每份的人工教育条目数，计数不符返回退出码 2
..\.venv\Scripts\python.exe scripts/evaluate_resume_ocr.py --expected-education 2,3 --output output/test-reports/ocr-new.json a.pdf b.pdf
# 对本地 OCR 文字/文本框 JSON 回放字段抽取，不重新运行 OCR
..\.venv\Scripts\python.exe scripts/evaluate_resume_ocr.py --replay-ocr --expected-education 3 --output output/test-reports/replay-new.json ocr.txt
..\.venv\Scripts\python.exe scripts/run_test_report.py --label ambiguity-delivery --all
```

模型 CLI 使用配置的 Gemini；仅选择确认可以发送的脱敏片段。退出码 2 表示修复结果需要复核，不视为无条件通过。OCR 模型和依赖位于 E 盘，测试临时文件可通过 `TEMP` / `TMP` 指向 D 盘。

最终完整后端回归 357 项通过、0 失败、0 跳过；前端构建和 39 项 smoke 测试通过。完整后端记录位于 `output/test-reports/20261113_211245_892637_ambiguity-resume-delivery/`。
