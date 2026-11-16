"""Boundary tests for source-bound facts and conservative edit adoption."""
import hashlib
import json
import unittest

from backend.services.fact_lock import locked_edit_findings, source_bound_ledger


SUPPORTED = {"relation": "SUPPORTED", "complete": True}


class FactLockTests(unittest.TestCase):
    def test_two_named_people_cannot_swap_assigned_actions(self):
        from backend.services.fact_lock import wording_invariants
        pairs = [
            ('林负责接口测试，周负责部署。', '周负责部署，林负责接口测试。', False),
            ('林负责接口测试，周负责部署。', '周负责接口测试，林负责部署。', True),
            ('Lin tested the API; Zhou handled deployment.', 'Zhou handled deployment; Lin tested the API.', False),
            ('Lin tested the API; Zhou handled deployment.', 'Zhou tested the API; Lin handled deployment.', True),
        ]
        for before, after, changed in pairs:
            with self.subTest(after=after):
                self.assertEqual(bool(wording_invariants(before, after)), changed)

    def test_explicit_environment_and_negative_deployment(self):
        from backend.services.fact_lock import wording_invariants
        cases = [
            ('在测试环境中，延迟降低12%。', '延迟在测试环境中降低12%。', False),
            ('在测试环境中，延迟降低12%。', '在生产环境中，延迟降低12%。', True),
            ('In staging, latency fell 12%.', 'In production, latency fell 12%.', True),
            ('The model has not been deployed.', 'The model has not yet been deployed.', False),
            ('The model has not been deployed.', 'The model has been deployed.', True),
            ('The model has been deployed.', 'The model has not been deployed.', True),
        ]
        for before, after, changed in cases:
            with self.subTest(after=after):
                self.assertEqual(bool(wording_invariants(before, after)), changed)

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

    def test_verified_quote_and_position_are_given_to_polisher(self):
        from backend.services.atomic_verifier import AtomicVerifier
        quote = '准确率提升约5%，召回率提升8%'
        source = {'source_id': 's', 'text': '前文。' + quote + '。其他未核验材料。',
                  'version': 'v1', 'sha256': 'a' * 64, 'text_offset': 20}
        citation = {'source_id': 's', 'quote': quote, 'source_version': 'v1', 'source_sha256': 'a' * 64}
        correction = {'source_id': 'correction', 'text': '原记录有修订', 'retrieval_channels': ['correction']}
        check = {**SUPPORTED, 'atoms': [{'atom_id': 'a', 'text': quote, 'relation': 'SUPPORTED', 'citations': [citation]}]}
        class Capture:
            def complete_json(self, prompt, data):
                self.payload = json.loads(data)
                return {'items': [{'id': 'c', 'text': quote}]}
        model = Capture()
        AtomicVerifier(model).polish([{'claim_id': 'c', 'text': quote}], {'c': {}}, {'c': [source, correction]}, '', {'c': check})
        row = model.payload['items'][0]
        self.assertEqual(row['source_selection'], 'verified_quotes')
        self.assertEqual(row['sources'][0]['text'], quote)
        self.assertEqual(row['sources'][1]['source_id'], 'correction')
        self.assertEqual(row['locked_facts'][0]['bindings'][0]['start'], 23)
        self.assertEqual(len(row['locked_facts'][0]['quantity_links']), 2)

    def test_partial_ledger_does_not_hide_other_sources(self):
        from backend.services.atomic_verifier import AtomicVerifier
        source = {'source_id': 's', 'text': '原始数据仍需核对', 'version': 'v1', 'sha256': 'a' * 64}
        check = {**SUPPORTED, 'atoms': [{'atom_id': 'a', 'text': '原始数据', 'relation': 'SUPPORTED', 'citations': []}]}
        class Capture:
            def complete_json(self, prompt, data):
                self.payload = json.loads(data)
                return {'items': [{'id': 'c', 'text': '原始数据'}]}
        model = Capture()
        AtomicVerifier(model).polish([{'claim_id': 'c', 'text': '原始数据'}], {'c': {}}, {'c': [source]}, '', {'c': check})
        self.assertEqual(model.payload['items'][0]['source_selection'], 'retrieved_sources')
        self.assertEqual(model.payload['items'][0]['sources'][0]['text'], source['text'])

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
        self.assertEqual(locked_edit_findings(
            "李宁是项目负责人；赵明仅实现 React 页面。",
            "项目由李宁负责；赵明仅实现 React 页面。", SUPPORTED), [])
        self.assertEqual(locked_edit_findings(
            "Avery assisted Lee with Docker tests.",
            "Avery helped Lee with Docker tests.", SUPPORTED), [])
        self.assertEqual(locked_edit_findings(
            "陈禾实现 TypeScript 前端，未负责 Java 服务。",
            "陈禾实现 TypeScript 前端，没有负责 Java 服务。", SUPPORTED), [])
        self.assertTrue(locked_edit_findings(
            "陈禾实现 TypeScript 前端，未负责 Java 服务。",
            "陈禾实现 TypeScript 前端，并负责 Java 服务。", SUPPORTED))

    def test_redundant_percentage_point_can_be_omitted(self):
        old = "准确率从80%提升至84%，提高4个百分点。"
        new = "准确率从80%提升至84%。"
        self.assertEqual(locked_edit_findings(old, new, SUPPORTED), [])
        self.assertTrue(locked_edit_findings(old, "准确率从80%提升至85%。", SUPPORTED))
        english = "Accuracy rose from 80% to 84%, an increase of 4 percentage points."
        self.assertTrue(locked_edit_findings(
            english, "Accuracy rose from 80% to 84%, a 4% relative increase.", SUPPORTED))
        self.assertEqual(locked_edit_findings(
            "The job took 200 ms.", "The job took 200 milliseconds.", SUPPORTED), [])

    def test_measurement_does_not_authorize_delivered_business_result(self):
        from backend.services.asu_resume import proposal_violations
        old = "Lina measured a 10% latency reduction in a local trial."
        bad = "Lina delivered a 10% latency reduction in production."
        good = "In a local trial, Lina measured latency 10% lower."
        self.assertTrue(proposal_violations(old, bad))
        self.assertFalse(proposal_violations(old, good))


if __name__ == "__main__":
    unittest.main()
