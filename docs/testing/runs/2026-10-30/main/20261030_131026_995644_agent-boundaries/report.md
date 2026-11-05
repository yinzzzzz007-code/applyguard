# 测试报告：agent-boundaries

- 日期时间：2026-10-30T13:10:26.995644+08:00 — 2026-10-30T13:10:27.222816+08:00（北京时间）
- 范围：['tests.test_agent_bridge']
- 结果：FAIL；方法 16，通过 15，失败/错误 1，夹具错误 0，跳过 0。
- 参数子用例：21（不与测试方法相加冒充独立覆盖项）。
- 耗时：0.227秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_agent_bridge.AgentBridgeTests.test_background_never_imports | PASS | 0.016 |
| tests.test_agent_bridge.AgentBridgeTests.test_changed_source_invalidates_confirmation | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_confirmed_numbers_required | PASS | 0.016 |
| tests.test_agent_bridge.AgentBridgeTests.test_expiry_and_revocation | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_fabricated_quote_or_hash_refused | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_github_immutable_scope | PASS | 0.015 |
| tests.test_agent_bridge.AgentBridgeTests.test_injection_is_data | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_materials_scattered_and_no_secret | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_pair_and_split_capabilities | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_path_boundaries | FAIL | 0.016 |
| tests.test_agent_bridge.AgentBridgeTests.test_pre_read_disclosure_required | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_private_auth_not_implicit | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_real_workspace_import_stays_unreviewed | PASS | 0.062 |
| tests.test_agent_bridge.AgentBridgeTests.test_scope_modes | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_summary_is_candidate_not_verified | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_symlink_escape | PASS | 0.016 |
