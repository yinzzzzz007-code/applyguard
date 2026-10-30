# 测试报告：agent-numeric-revoke-fixes

- 日期时间：2026-10-30T13:41:01.889473+08:00 — 2026-10-30T13:41:02.294932+08:00（北京时间）
- 范围：['tests.test_numeric_unit_guard', 'tests.test_agent_bridge', 'tests.test_grounding_v2', 'tests.test_edit_inventory']
- 结果：PASS；方法 36，通过 36，失败/错误 0，夹具错误 0，跳过 0。
- 参数子用例：27（不与测试方法相加冒充独立覆盖项）。
- 耗时：0.405秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_numeric_unit_guard.NumericUnitTests.test_both_verifier_paths_override_erroneous_model_approval | PASS | 0.016 |
| tests.test_numeric_unit_guard.NumericUnitTests.test_does_not_override_existing_rejection | PASS | 0.0 |
| tests.test_numeric_unit_guard.NumericUnitTests.test_percent_point_substitution_requires_review | PASS | 0.0 |
| tests.test_numeric_unit_guard.NumericUnitTests.test_valid_units_remain_supported | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_background_never_imports | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_changed_source_invalidates_confirmation | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_confirmed_numbers_required | PASS | 0.015 |
| tests.test_agent_bridge.AgentBridgeTests.test_expired_or_repeated_revoke_is_safe | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_expiry_and_revocation | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_fabricated_quote_or_hash_refused | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_github_immutable_scope | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_injection_is_data | PASS | 0.016 |
| tests.test_agent_bridge.AgentBridgeTests.test_materials_scattered_and_no_secret | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_pair_and_split_capabilities | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_path_boundaries | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_pre_read_disclosure_required | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_private_auth_not_implicit | PASS | 0.015 |
| tests.test_agent_bridge.AgentBridgeTests.test_real_workspace_import_stays_unreviewed | PASS | 0.032 |
| tests.test_agent_bridge.AgentBridgeTests.test_revoke_during_search_discards_inflight_results | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_scope_modes | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_secret_like_text_is_not_disclosed | PASS | 0.015 |
| tests.test_agent_bridge.AgentBridgeTests.test_summary_is_candidate_not_verified | PASS | 0.0 |
| tests.test_agent_bridge.AgentBridgeTests.test_symlink_escape | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_cache_key_binds_strategy_query_scope_and_source_version | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_coverage_repairs_are_bounded | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_full_claim_can_block_even_if_atoms_pass | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_missing_atom_ids_never_pass | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_numeric_coverage_in_chinese | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_rejected_edit_restores_and_rechecks_original | PASS | 0.015 |
| tests.test_grounding_v2.GroundingV2Tests.test_reverting_a_bad_original_does_not_make_it_verified | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_sag_preview_cannot_replace_original | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_strict_output_deterministic_id_and_exact_quote | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_supported_detail_loss_rejects_even_supported_proposal | PASS | 0.015 |
| tests.test_edit_inventory.InventoryTests.test_all_supported_fact_categories_are_preserved_in_input | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_incomplete_original_inventory_prevents_application | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_wrong_original_is_not_protected_as_true | PASS | 0.0 |
