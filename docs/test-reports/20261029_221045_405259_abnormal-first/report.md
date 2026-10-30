# 测试报告：abnormal-first

- 日期时间：2026-10-29T22:10:45.405259+08:00 — 2026-10-29T22:10:47.019876+08:00（北京时间）
- 范围：['tests.test_resume_abnormal', 'tests.test_resume_sections', 'tests.test_api.ResumeExtractTests', 'tests.test_workflow_repairs.ResumeModelConsentTests']
- 结果：FAIL；方法 36，通过 35，失败/错误 1，跳过 0。
- 参数子用例：166（不与测试方法相加冒充独立覆盖项）。
- 耗时：1.615秒。逐文件SHA256见report.json，完整执行信息见test.log。
- 限制：测试通过不等于无缺陷；模型桩测试不证明真实模型准确率。未执行项见测试计划。

| 测试 | 结果 | 秒 |
| --- | --- | ---: |
| tests.test_resume_abnormal.ResumeAbnormalHTTPTests.test_content_length_limits_without_sending_large_body | PASS | 0.016 |
| tests.test_resume_abnormal.ResumeAbnormalHTTPTests.test_fixed_seed_wrong_type_fuzz_120_cases | PASS | 0.734 |
| tests.test_resume_abnormal.ResumeAbnormalHTTPTests.test_invalid_pdf_keeps_error_envelope_and_service_healthy | PASS | 0.031 |
| tests.test_resume_abnormal.ResumeAbnormalHTTPTests.test_json_contract_bad_utf8_and_root_types | FAIL | 0.032 |
| tests.test_resume_abnormal.ResumeAbnormalHTTPTests.test_repeat_and_concurrent_requests_do_not_cross_contaminate | PASS | 0.031 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_blank_page_alongside_text_is_allowed | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_drawing_without_text_is_not_treated_as_blank | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_empty_model_response_preserves_rule_fields | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_encoded_size_rejected_before_decoding | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_encrypted_pdf_returns_actionable_validation | PASS | 0.016 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_fake_corrupt_and_empty_pdf | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_invalid_base64_not_silently_repaired | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_invalid_or_invented_model_payload_falls_back | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_missing_and_wrong_type_payload | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_offline_mode_never_calls_model_with_instructions_in_text | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_page_count_at_boundary_and_over | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_page_failure_cannot_return_partial_resume | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_partial_model_response_cannot_drop_rule_projects | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_pdf_byte_size_checked_before_parsing | PASS | 0.015 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_pdf_javascript_is_data_not_executed | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_text_limit_never_silently_truncates | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_wrong_filename_extension_type_and_controls | PASS | 0.0 |
| tests.test_resume_abnormal.ResumeAbnormalUnitTests.test_wrong_mode_types_are_validation_errors | PASS | 0.0 |
| tests.test_resume_sections.ResumeSectionsTests.test_education_does_not_confuse_rank_with_major_or_invent_month | PASS | 0.0 |
| tests.test_resume_sections.ResumeSectionsTests.test_header_labels_are_not_mistaken_for_names | PASS | 0.0 |
| tests.test_resume_sections.ResumeSectionsTests.test_heading_words_in_description_do_not_cut_sections | PASS | 0.0 |
| tests.test_resume_sections.ResumeSectionsTests.test_mixed_honors_are_not_headings_or_experience_paragraphs | PASS | 0.0 |
| tests.test_resume_sections.ResumeSectionsTests.test_month_precision_and_multiple_education_records | PASS | 0.0 |
| tests.test_resume_sections.ResumeSectionsTests.test_multiline_title_and_distinct_research_engineering_projects | PASS | 0.0 |
| tests.test_resume_sections.ResumeSectionsTests.test_offline_pdf_pipeline_keeps_all_rows_without_model | PASS | 0.016 |
| tests.test_resume_sections.ResumeSectionsTests.test_unlabelled_bilingual_header_and_missing_identity_fields | PASS | 0.0 |
| tests.test_api.ResumeExtractTests.test_rule_extract_reads_contest_section | PASS | 0.0 |
| tests.test_api.ResumeExtractTests.test_rule_extract_reads_labeled_chinese_fields | PASS | 0.0 |
| tests.test_workflow_repairs.ResumeModelConsentTests.test_default_never_constructs_model_even_with_key | PASS | 0.0 |
| tests.test_workflow_repairs.ResumeModelConsentTests.test_explicit_dynamic_is_required_and_invalid_mode_rejected | PASS | 0.0 |
| tests.test_workflow_repairs.ResumeModelConsentTests.test_model_invented_identity_falls_back_to_local_source | PASS | 0.0 |
