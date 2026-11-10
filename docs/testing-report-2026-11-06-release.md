# 2026-11-06 · 11.6 分支发布复测

本次从 11.5 工作树建立 `feature/review-workbench-20261106`，收录 11 月 5 日的润色判断、数值与职责保护、前端审核交互、冻结测试集和逐条结果。提交署名使用姜凌天的 GitHub 身份 Gitvextor。项目默认文本模型保持 `gemini-3.1-flash-lite-preview`，未执行模型切换实验。

## 本日实际执行

- 后端在项目虚拟环境运行 `python -B -m unittest discover -s tests`，312 项运行，311 项通过、1 项可选 OCR 测试跳过，耗时 25.351 秒。
- 前端 `npm run smoke`，32/32 通过。`npm run build` 通过，构建工具提示现有大包体积。
- `scripts/evaluate_wording_regression.py` 用仓库内固定结果作基线重放，340 条输入均一致。`pip check` 显示依赖一致，`git diff --check` 通过。
- 查本机 ChatAnywhere 模型目录，存在 `gemini-3.1-flash-lite-preview` 与 `gpt-4o`，未列出 `gemini-3.1-flash`。按用户最新要求保持全部文本任务使用前者。

## 结果范围和待完成

[11 月 5 日真实模型配对](testing-report-2026-11-05-wording.md)只有 31 条有改动且完成判定的建议。按暂定标签，合理建议采用 24/25，错改采用 0/6。另有 2 条未改动、15 条缺结论。后续调用返回余额不足。这项结果不足以比较 Gemini 与 4o 的优劣。

[11 月 5 日扩展回归](testing-report-2026-11-05-wording-regression.md)包括 340 条固定配对、30 条自然语句和 60 条材料状态用例。配对用例含开发者设计的重复模板；最后一次修复后缺新的盲测，57 条历史建议缺独立真人标签。仍需在新材料上完成整条流程的真实模型对照，记录错误生成、自动修复、最终漏放、误拦、复核、延迟和费用。缓存与未完成调用不能按成功样本计分。
