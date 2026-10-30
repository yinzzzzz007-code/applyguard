# 测试报告：agent-original-reuse

- 日期时间：2026-10-30T13:51:21.678599+08:00 — 2026-10-30T13:51:26.940998+08:00（北京时间）
- 范围：['tests.test_edit_inventory', 'tests.test_grounding_v2', 'tests.test_grounding', 'tests.test_workflow_repairs']
- 结果：PASS；方法 49，通过 49，失败/错误 0，夹具错误 0，跳过 0。
- 参数子用例：6（不与测试方法相加冒充独立覆盖项）。
- 耗时：5.262秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_edit_inventory.InventoryTests.test_all_supported_fact_categories_are_preserved_in_input | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_incomplete_original_inventory_prevents_application | PASS | 0.0 |
| tests.test_edit_inventory.InventoryTests.test_rejected_edit_reuses_fresh_original_check_without_third_verification | PASS | 0.031 |
| tests.test_edit_inventory.InventoryTests.test_unchanged_polish_reuses_only_current_run_verification | PASS | 0.016 |
| tests.test_edit_inventory.InventoryTests.test_wrong_original_is_not_protected_as_true | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_cache_key_binds_strategy_query_scope_and_source_version | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_coverage_repairs_are_bounded | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_full_claim_can_block_even_if_atoms_pass | PASS | 0.015 |
| tests.test_grounding_v2.GroundingV2Tests.test_missing_atom_ids_never_pass | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_numeric_coverage_in_chinese | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_rejected_edit_restores_and_rechecks_original | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_reverting_a_bad_original_does_not_make_it_verified | PASS | 0.016 |
| tests.test_grounding_v2.GroundingV2Tests.test_sag_preview_cannot_replace_original | PASS | 0.0 |
| tests.test_grounding_v2.GroundingV2Tests.test_strict_output_deterministic_id_and_exact_quote | PASS | 0.015 |
| tests.test_grounding_v2.GroundingV2Tests.test_supported_detail_loss_rejects_even_supported_proposal | PASS | 0.016 |
| tests.test_grounding.GroundingHTTPTests.test_export_requires_human_and_fresh_atomic_check | PASS | 0.75 |
| tests.test_grounding.GroundingHTTPTests.test_polish_endpoint_and_sag_preview | PASS | 0.562 |
| tests.test_grounding.GroundingHTTPTests.test_reverify_ignores_forged_refs_and_displays_original_position | PASS | 0.594 |
| tests.test_grounding.GroundingHTTPTests.test_revoked_link_and_midflight_change_invalidate_result | PASS | 0.594 |
| tests.test_grounding.GroundingPolicyTests.test_conflicting_fact_blocks | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_duplicate_or_missing_atoms_fail_closed | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_exact_citation_and_current_text_are_bound | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_foreign_candidate_and_draft_cannot_supply_proof | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_incomplete_atomization_cannot_pass | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_nonliteral_quote_cannot_pass | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_out_of_project_retrieval_is_removed_even_if_retriever_ignores_scope | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_provider_failure_cannot_reuse_verified | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_same_experience_correction_is_searchable_and_revoked_required_ref_blocks | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_source_review_is_not_a_semantic_pass_in_sag_mode | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_three_search_channels_and_atomic_server_floor | PASS | 0.0 |
| tests.test_grounding.GroundingPolicyTests.test_truncated_valid_json_is_rejected_by_grounding_transport | PASS | 0.0 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_candidate_mismatch_and_duplicate_claims_stop | PASS | 0.047 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_changed_file_and_deleted_file_invalidate_workflow | PASS | 0.11 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_decimal_sign_and_denominator_are_not_formatting | PASS | 0.078 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_empty_draft_does_not_fall_back_to_seed | PASS | 0.031 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_foreign_span_cannot_be_assigned | PASS | 0.063 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_import_review_link_workflow_and_revocation | PASS | 0.093 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_negated_substring_and_award_extra_facts_are_not_supported | PASS | 0.11 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_positive_quote_and_unknown_claim_do_not_share_status | PASS | 0.062 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_rejected_and_target_scoped_links | PASS | 0.063 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_reverification_does_not_trust_client_state_or_refs | PASS | 0.078 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_tampered_original_cannot_pass | PASS | 0.031 |
| tests.test_workflow_repairs.EvidenceRepairTests.test_unreviewed_material_and_unrelated_link_cannot_promote | PASS | 0.047 |
| tests.test_workflow_repairs.ResumeModelConsentTests.test_default_never_constructs_model_even_with_key | PASS | 0.016 |
| tests.test_workflow_repairs.ResumeModelConsentTests.test_explicit_dynamic_is_required_and_invalid_mode_rejected | PASS | 0.0 |
| tests.test_workflow_repairs.ResumeModelConsentTests.test_model_invented_identity_falls_back_to_local_source | PASS | 0.0 |
| tests.test_workflow_repairs.StaticRepairTests.test_cors_does_not_allow_credentials_disguised_as_loopback | PASS | 0.515 |
| tests.test_workflow_repairs.StaticRepairTests.test_plain_encoded_and_symlink_traversal_denied | PASS | 0.531 |
| tests.test_workflow_repairs.StaticRepairTests.test_reverification_http_envelope_and_stopping_point | PASS | 0.532 |
