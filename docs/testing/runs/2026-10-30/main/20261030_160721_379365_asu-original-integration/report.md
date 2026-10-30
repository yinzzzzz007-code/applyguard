# 测试报告：asu-original-integration

- 日期时间：2026-10-30T16:07:21.379365+08:00 — 2026-10-30T16:07:24.273808+08:00（北京时间）
- 范围：['tests.test_asu_resume', 'tests.test_grounding', 'tests.test_grounding_v2', 'tests.test_edit_inventory', 'tests.test_numeric_unit_guard']
- 结果：PASS；方法 42，通过 42，失败/错误 0，夹具错误 0，跳过 0。
- 参数子用例：12（不与测试方法相加冒充独立覆盖项）。
- 耗时：2.894秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_asu_resume.ASuReuseTests.test_absent_assets_preserve_original_and_review | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_business_reference_is_loaded_only_when_relevant | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_changed_upstream_asset_never_silently_runs | PASS | 0.015 |
| tests.test_asu_resume.ASuReuseTests.test_original_skill_and_ledger_reach_proposal_call | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_six_original_files_match_upstream_blob_and_sha256 | PASS | 0.016 |
| tests.test_asu_resume.ASuReuseTests.test_unsupported_asu_proposal_does_not_override_guard_or_original | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_verification_alone_does_not_load_writing_skill | PASS | 0.016 |
| tests.test_grounding.GroundingHTTPTests.test_export_requires_human_and_fresh_atomic_check | PASS | 0.687 |
| tests.test_grounding.GroundingHTTPTests.test_polish_endpoint_and_sag_preview | PASS | 0.547 |
| tests.test_grounding.GroundingHTTPTests.test_reverify_ignores_forged_refs_and_displays_original_position | PASS | 0.594 |
| tests.test_grounding.GroundingHTTPTests.test_revoked_link_and_midflight_change_invalidate_result | PASS | 0.578 |
| tests.test_grounding.GroundingPolicyTests.test_conflicting_fact_blocks | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_duplicate_or_missing_atoms_fail_closed | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_exact_citation_and_current_text_are_bound | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_foreign_candidate_and_draft_cannot_supply_proof | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_incomplete_atomization_cannot_pass | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_nonliteral_quote_cannot_pass | PASS | 0.015 |
| tests.test_grounding.GroundingPolicyTests.test_out_of_project_retrieval_is_removed_even_if_retriever_ignores_scope | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_provider_failure_cannot_reuse_verified | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_same_experience_correction_is_searchable_and_revoked_required_ref_blocks | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_source_review_is_not_a_semantic_pass_in_sag_mode | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_three_search_channels_and_atomic_server_floor | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_truncated_valid_json_is_rejected_by_grounding_transport | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_cache_key_binds_strategy_query_scope_and_source_version | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_coverage_repairs_are_bounded | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_full_claim_can_block_even_if_atoms_pass | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_missing_atom_ids_never_pass | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_numeric_coverage_in_chinese | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_rejected_edit_restores_and_rechecks_original | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_reverting_a_bad_original_does_not_make_it_verified | PASS | 0.015 |
| tests.test_grounding_v2.GroundingV2Tests.test_sag_preview_cannot_replace_original | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_strict_output_deterministic_id_and_exact_quote | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_supported_detail_loss_rejects_even_supported_proposal | PASS | 0.016 |
| tests.test_edit_inventory.InventoryTests.test_all_supported_fact_categories_are_preserved_in_input | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_incomplete_original_inventory_prevents_application | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_rejected_edit_reuses_fresh_original_check_without_third_verification | PASS | 0.015 |
| tests.test_edit_inventory.InventoryTests.test_unchanged_polish_reuses_only_current_run_verification | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_wrong_original_is_not_protected_as_true | PASS | 0.0 |
| tests.test_numeric_unit_guard.NumericUnitTests.test_both_verifier_paths_override_erroneous_model_approval | PASS | 0.016 |
| tests.test_numeric_unit_guard.NumericUnitTests.test_does_not_override_existing_rejection | PASS | 0.0 |
| tests.test_numeric_unit_guard.NumericUnitTests.test_percent_point_substitution_requires_review | PASS | 0.0 |
| tests.test_numeric_unit_guard.NumericUnitTests.test_valid_units_remain_supported | PASS | 0.0 |
