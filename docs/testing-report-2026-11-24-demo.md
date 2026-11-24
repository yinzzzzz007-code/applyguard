# 演示前全量复查（2026-11-24）

结论：本地自动化、简历导入、岗位刷新和 Harness 单次实测通过；云端事实核验与严格导出本轮未通过，不能保证录制时外部模型稳定。

后续修复和更新的验证结果见[云端修复和实测记录](testing-report-2026-11-24-cloud-repair.md)。

## 实测结果

- 项目虚拟环境后端全量 449 项通过、0 跳过；先前使用系统 Python 的运行因缺少 MCP 和 python-docx 失败，保留失败记录。CLI：`python scripts/run_test_report.py --label final-venv-20261124 --all`，应使用项目已安装依赖的 Python，隔离临时数据。
- `python scripts/verify_ui_actions.py --build`：按钮静态盘点、相关后端和前端测试、构建通过；源码中 249 个按钮、132 处条件禁用。静态检查不等于穷举每个按钮的全部状态。
- `scripts/check_running_resume.py --port 8020 --cv <个人PDF>`：8 项通过，包括原始简历离线导入和无内容图片页的错误处理。前一次检查脚本自身在 OCR 冷启动 15 秒后超时，现将该用例等待设为 180 秒；页面的相关请求上限为 600 秒。
- 8020 预览启动器已使用含 SAG 的项目 Python，并保留预算记录；原因是前一次启动误用系统 Python，缺少 SAG。预览与 8015 数据隔离，互不自动同步；进程中的模型密钥不持久保存。
- 岗位官网在隔离数据库刷新：百度、华为、Seed 均无来源错误；百度和 Seed 为部分来源范围。浏览器实查未读提醒弹窗可打开，未批量标记已读。
- 真实 Harness 在三份虚构材料中完成 get_task、search_materials 和 submit_evidence，29.383 秒；仅是单次链路实测。
- HTTP 用户确认稿虚构样例导出成功，并保留 `NOT_ATOMICALLY_VERIFIED`；不等于严格核验，也没有向招聘网站提交。
- Gemini 个人副本：JD 解析及语义匹配完成；面经生成 16 条；AI 简历字段解析本次超时回退规则抽取；三条正文生成三条 ASu 建议，但原文原子核验遇到 503，建议均未核验。SAG 图扩展检索在模型请求阶段超时；向量路径单条也在原子核验阶段遇到模型不可用，且记录 embedding 截断提示，不能视为完整通过。
- 以用户确认的奖项做单项真实严格导出：最终模型复核 HTTP 503，正确阻止导出。未改变用户真实草稿；先前成功结果不能替代本次验证。

## 本轮修复及入口

- `start-demo.bat` 在新环境安装 `requirements-sag.txt`，已有环境检查 SAG；端口占用时中止并提示，不再主动停止无关后端。只检查了端口冲突检测，未完整执行安装与双服务启动。
- `scripts/summarize_cloud_features.py` 不再将“规则抽取（模型不可用）”误判为模型成功；`scripts/evaluate_cloud_features.py` 对所请求阶段缺失或未完成返回非零。`tests.test_cloud_reporting` 和 `tests.test_resume_ocr_cli` 共 3 项通过；真实缺失阶段检查返回退出码 1。
- 自动化结果 `output/test-reports/20261124_020405_143786_final-venv-20261124/`；前端检查 `output/test-reports/20261124_020313_ui-actions/`；Harness `output/test-reports/20261124_020750_harness-live/`。个人云结果保存在被忽略的 `output/final-live-20261124/`、`output/final-vector-probe-20261124/` 和 `output/final-strict-award-retry-20261124/`，不得公开上传。
- 截至本轮严格导出后，平台累计约 1.36018142 CA；并行请求的账单差额不相加。平台计费单位和人民币的换算以服务商为准。

## 演示提示

录制前先确认 8020 服务仍在线，且不要把预览副本误认为与 8015 自动同步。服务重启后进程内密钥会消失；需要重新在已授权的启动流程中输入。模型 503 时可展示未核验建议和用户确认稿，但不能声称严格核验成功，也不能把模拟或旧结果称作实时成功。个人简历和材料先确认适合公开展示。
