# 测试报告：asu-final-provenance

- 日期时间：2026-10-30T16:23:38.986931+08:00 — 2026-10-30T16:23:39.445050+08:00（北京时间）
- 范围：['tests.test_asu_resume']
- 结果：FAIL；方法 9，通过 7，失败/错误 2，夹具错误 0，跳过 0。
- 参数子用例：10（不与测试方法相加冒充独立覆盖项）。
- 耗时：0.458秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_asu_resume.ASuReuseTests.test_absent_assets_preserve_original_and_review | ERROR | 0.016 |
| tests.test_asu_resume.ASuReuseTests.test_business_reference_is_loaded_only_when_relevant | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_changed_upstream_asset_never_silently_runs | ERROR | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_chinese_english_and_uncertain_language_boundaries | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_original_skill_and_ledger_reach_proposal_call | PASS | 0.015 |
| tests.test_asu_resume.ASuReuseTests.test_six_original_files_match_upstream_blob_and_sha256 | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_unsolicited_translation_is_not_applied_even_if_judge_supports_it | PASS | 0.016 |
| tests.test_asu_resume.ASuReuseTests.test_unsupported_asu_proposal_does_not_override_guard_or_original | PASS | 0.016 |
| tests.test_asu_resume.ASuReuseTests.test_verification_alone_does_not_load_writing_skill | PASS | 0.0 |
