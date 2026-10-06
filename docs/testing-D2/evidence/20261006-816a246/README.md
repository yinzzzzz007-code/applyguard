# 本轮实际测试证据

基线 `816a24601385481b7261aba893c4c950503d7880`；审计日期2026-10-06。数据均为仓库虚构样例或本次合成测试数据。未调用真实模型、未投递、未使用真实简历。

## 快速定位

| 要检查的结论 | 文件 |
|---|---|
| 基线、环境、实际结果与未测范围 | [run-summary.json](run-summary.json) |
| Windows默认命令失败与UTF-8复测79通过 | [原失败](baseline/backend-tests.log)、[复测](baseline/backend-tests-utf8.log) |
| 构建、lint警告、smoke | [build](baseline/frontend-build.log)、[lint](baseline/frontend-lint.log)、[smoke](baseline/frontend-smoke.log) |
| 当前基准与旧结果差异 | [本次输出](baseline/benchmark.log)、[历史报告](inputs/eval/results/c-offline-audit.json)、[原测试集](inputs/eval/c_cases.json) |
| 中文语义误匹配、中文原句、后端手动句阻断、404 | [接口结果](baseline/api-audit-results.json)、[探针源码](baseline/api-audit.py) |
| 手动无证据复制、JD过期、保存错误、弹层 | [完成轮结果](browser-run-03/browser-audit-results.json)、[完整追踪](browser-run-03/browser-audit-trace.zip) |
| 第一次和第二次浏览器脚本ERROR | [01](browser-run-01/browser-audit-results.json)、[02](browser-run-02/browser-audit-results.json) |
| 刷新、重载、重复当前场景、45个标签缺失 | [交互结果](interaction-run-01/results.json)、[交互追踪](interaction-run-01/trace.zip) |
| 留档脚本本身的真实验证 | [自动命令结果](collector-validation/commands.json)、[自动运行元数据](collector-validation/run.json) |
| 留档工具的故障注入验证 | [缺解释器ERROR](collector-error-validation/commands.json)：故意传不存在的Python，确认未执行不被写为PASS |
| PDF校历视觉核查与学者原始分析 | [课程核查](course-review/scholar-course-review.md)；同目录两张日历图 |
| 全部文件完整性 | [SHA256清单](manifest.sha256.json) |

## 关键截图

- [JD着色和当前强匹配](browser-run-03/ui-match.png)
- [只读模拟网申与英文残留](browser-run-03/ui-ats.png)
- [无证据句进入可复制稿](browser-run-03/ui-unsafe-copy.png)
- [财务新原文与后端旧结果混合](browser-run-03/ui-stale-jd.png)
- [存储失败仍提示已保存](browser-run-03/ui-save-failure.png)
- [375px匹配页面](browser-run-03/ui-mobile.png)
- [375px经历库](interaction-run-01/vault-mobile.png)

## 怎样理解这些材料

浏览器脚本记录实际DOM和网络，然后由审计者对照预期判定。01/02是脚本定位错误而非产品缺陷计数；03完成B01–B08观察，另一次交互探针完成I01–I06。B与I为观察编号，不等同于详细计划的110条用例均已执行。

API探针只进行本机请求和offline函数调用。输入副本冻结了当时种子、映射和旧评估，供以后复测比较。不要修改这些冻结副本来“修复”当前代码；实际修复应在生产文件中另提交，然后生成新证据包。

本机浏览器脚本使用bundled Playwright与安装的Chrome绝对路径，原样保留以解释运行环境；他人复现应复制到新的运行目录并替换运行器路径，不在本归档内重跑覆盖文件。首次浏览器脚本原始版本未单独保存，日志和trace保留；02/03及交互轮含各自执行脚本快照。这是本轮已知留档限制，后续统一使用运行前快照规则。

原始时间戳保留来源；浏览器进程与命令宿主时钟显示存在差异，不据二者差值作性能结论。没有测试日志被改写成成功结果。自动采集验证只证明命令采集可用，基准仍为REVIEW_REQUIRED。

AI使用：Codex读取课程和代码、辅助设计用例、运行本机探针、编写报告。学者子代理完成课程审阅；其他子代理部分中断，剩余视角由主助手完成。尚无人类验收签字或真实用户参与记录，不宣称已经获得。

完整原始工作材料仍在 `output/d2-audit/`；自动采集原目录见 `collector-validation/run.json`。此目录只包含本次虚构/脱敏证据，未包含.env或真实data/local草稿。
