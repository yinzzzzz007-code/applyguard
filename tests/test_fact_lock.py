"""Boundary tests for source-bound facts and conservative edit adoption."""
import hashlib
import unittest

from backend.services.fact_lock import locked_edit_findings, source_bound_ledger


SUPPORTED = {"relation": "SUPPORTED", "complete": True}


class FactLockTests(unittest.TestCase):
    def test_source_bound_facts_require_exact_current_quote_and_version(self):
        quote = "林岚协助开发 Python 后端，尚未上线"
        source = {"source_id": "s1", "text": quote + "。", "version": "v2",
                  "sha256": hashlib.sha256((quote + "。").encode()).hexdigest()}
        citation = {"source_id": "s1", "quote": quote, "source_version": "v2",
                    "source_sha256": source["sha256"]}
        check = {**SUPPORTED, "atoms": [{"atom_id": "a1", "text": quote,
                                         "relation": "SUPPORTED", "citations": [citation]}]}
        self.assertEqual(source_bound_ledger(quote, check, [source])[0]["bindings"][0]["quote"], quote)
        for bad in [{"quote": "林岚主导开发 Python"}, {"source_version": "v1"},
                    {"source_sha256": "not-the-current-source"}]:
            altered = {**check, "atoms": [{**check["atoms"][0],
                         "citations": [{**citation, **bad}]}]}
            with self.subTest(bad=bad):
                self.assertEqual(source_bound_ledger(quote, altered, [source]), [])

    def test_good_local_rephrasing_keeps_supported_facts(self):
        old = "林岚协助开发 Python 后端，离线测试中延迟降低约 30%，尚未上线。"
        new = "林岚协助开发 Python 后端；离线测试中，延迟降低约 30%；尚未上线。"
        self.assertEqual(locked_edit_findings(old, new, SUPPORTED), [])

    def test_unsupported_or_incomplete_old_text_is_not_treated_as_locked_truth(self):
        self.assertEqual(locked_edit_findings("尚未上线", "已经上线",
                         {"relation": "INSUFFICIENT", "complete": True}), [])
        self.assertTrue(locked_edit_findings("尚未上线", "已经上线",
                        {"relation": "SUPPORTED", "complete": False}))

    def test_scope_role_technology_number_and_person_mismatch(self):
        old = "林岚协助开发 Python 后端，离线测试中延迟降低约 30%，尚未上线。"
        changes = [
            "林岚主导开发 Python 后端，离线测试中延迟降低约 30%，尚未上线。",
            "林岚协助开发 Python 后端，离线测试中延迟降低约 35%，尚未上线。",
            "林岚协助开发 Go 后端，离线测试中延迟降低约 30%，尚未上线。",
            "林岚协助开发 Python 后端，延迟降低约 30%，已经上线。",
        ]
        for new in changes:
            with self.subTest(new=new):
                self.assertTrue(locked_edit_findings(old, new, SUPPORTED))
        old = "林岚负责 SQL 接口；周同学负责 Vue 表单。"
        swapped = "林岚负责 Vue 表单；周同学负责 SQL 接口。"
        self.assertTrue(any("归属" in item for item in locked_edit_findings(old, swapped, SUPPORTED)))
        old = "Redis 缓存由林岚负责；周同学负责 Vue 表单。"
        changed = "Redis 缓存由其他人负责；周同学负责 Vue 表单。"
        self.assertTrue(any("归属" in item for item in locked_edit_findings(old, changed, SUPPORTED)))
        self.assertTrue(locked_edit_findings("林岚是项目负责人。", "项目负责人未明确。", SUPPORTED))

    def test_redundant_percentage_point_can_be_omitted(self):
        old = "准确率从80%提升至84%，提高4个百分点。"
        new = "准确率从80%提升至84%。"
        self.assertEqual(locked_edit_findings(old, new, SUPPORTED), [])
        self.assertTrue(locked_edit_findings(old, "准确率从80%提升至85%。", SUPPORTED))


if __name__ == "__main__":
    unittest.main()
