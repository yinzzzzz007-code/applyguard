# 测试报告：edit-preservation-v2-retest

- 日期时间：2026-10-30T16:48:04.341588+08:00 — 2026-10-30T16:48:04.751962+08:00（北京时间）
- 范围：['tests.test_edit_preservation_v2', 'tests.test_edit_inventory', 'tests.test_grounding_v2', 'tests.test_asu_resume']
- 结果：PASS；方法 35，通过 35，失败/错误 0，夹具错误 0，跳过 0。
- 参数子用例：65（不与测试方法相加冒充独立覆盖项）。
- 耗时：0.410秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_correcting_stale_negation_does_not_force_retention | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_decimal_decrease_is_exact | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_different_direction_metric_scope_or_unit_never_discharge | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_equivalent_delta_removed_without_dropping_other_losses | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_equivalent_qualifier_paraphrases | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_exact_delta_can_be_omitted_when_endpoints_and_scope_retained | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_full_original_protects_qualifier_even_if_atoms_wrongly_omit_it | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_incorrect_original_is_not_granted_equivalence_override | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_observed_not_implemented_loss_is_caught_despite_model_approval | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_parameterized_exact_deltas_chinese_and_english | PASS | 0.0 |
| tests.test_edit_preservation_v2.EditPreservationV2Tests.test_qualifier_deletion_and_negation_substitution | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_all_supported_fact_categories_are_preserved_in_input | PASS | 0.015 |
| tests.test_edit_inventory.InventoryTests.test_incomplete_original_inventory_prevents_application | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_rejected_edit_reuses_fresh_original_check_without_third_verification | PASS | 0.016 |
| tests.test_edit_inventory.InventoryTests.test_unchanged_polish_reuses_only_current_run_verification | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_wrong_original_is_not_protected_as_true | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_cache_key_binds_strategy_query_scope_and_source_version | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_coverage_repairs_are_bounded | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_full_claim_can_block_even_if_atoms_pass | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_missing_atom_ids_never_pass | PASS | 0.015 |
| tests.test_grounding_v2.GroundingV2Tests.test_numeric_coverage_in_chinese | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_rejected_edit_restores_and_rechecks_original | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_reverting_a_bad_original_does_not_make_it_verified | PASS | 0.015 |
| tests.test_grounding_v2.GroundingV2Tests.test_sag_preview_cannot_replace_original | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_strict_output_deterministic_id_and_exact_quote | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_supported_detail_loss_rejects_even_supported_proposal | PASS | 0.016 |
| tests.test_asu_resume.ASuReuseTests.test_absent_assets_preserve_original_and_review | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_business_reference_is_loaded_only_when_relevant | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_changed_upstream_asset_never_silently_runs | PASS | 0.015 |
| tests.test_asu_resume.ASuReuseTests.test_chinese_english_and_uncertain_language_boundaries | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_original_skill_and_ledger_reach_proposal_call | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_six_original_files_match_upstream_blob_and_sha256 | PASS | 0.0 |
| tests.test_asu_resume.ASuReuseTests.test_unsolicited_translation_is_not_applied_even_if_judge_supports_it | PASS | 0.016 |
| tests.test_asu_resume.ASuReuseTests.test_unsupported_asu_proposal_does_not_override_guard_or_original | PASS | 0.016 |
| tests.test_asu_resume.ASuReuseTests.test_verification_alone_does_not_load_writing_skill | PASS | 0.015 |
