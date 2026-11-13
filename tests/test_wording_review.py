import copy
import unittest
from unittest.mock import patch

from backend.services.grounded_workflow import GroundingService
from backend.services.wording_review import review_edit
from tests.test_grounding import AllSources, CLAIM, TEXT, experience
from tests.test_grounding_v2 import Model


class WordingTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict('os.environ', {'APPLYGUARD_STRONG_AI_MODEL': ''}))
        self.enterContext(patch('backend.services.grounded_workflow.HttpModelClient',
                                side_effect=AssertionError('Wording unit tests must not call a live model')))

    def test_one_repair_even_if_judge_accepts_role_upgrade(self):
        original = '参与后端开发。'
        fixed = '参与了后端开发。'
        calls = []
        def step(action, before, text, issues):
            calls.append(action)
            return {'text':fixed} if action == 'repair' else {'decision':'equivalent','reason':'fixture'}
        text, review = review_edit(step, original, '主导后端开发。')
        self.assertEqual(calls, ['judge','repair','judge'])
        self.assertEqual(text, fixed)
        self.assertTrue(review['equivalent'])

    def test_failed_repair_does_not_loop_or_pass(self):
        calls = []
        def step(action, before, text, issues):
            calls.append(action)
            return {'text':'延迟降低了30%。'} if action == 'repair' else {'decision':'equivalent','reason':''}
        _, review = review_edit(step, '仅在离线测试中，延迟降低约30%，尚未上线。', '延迟降低30%。')
        self.assertEqual(calls, ['judge','repair','judge'])
        self.assertFalse(review['equivalent'])

    def test_unlinked_equivalent_draft_stays_unsupported(self):
        item = experience()
        item['evidence_sources'] = []
        proposal = 'For Atlas, Alex wrote Python interface tests.'
        model = Model(proposal=proposal)
        model.wording_step = lambda *args:{'decision':'equivalent','reason':'same actor and task'}
        claims, checks, report = GroundingService(model=model,retriever=AllSources()).run(
            [copy.deepcopy(CLAIM)],[item],'cand_test','sag_atomic',polish=True)
        row = report['results'][CLAIM['claim_id']]
        self.assertEqual(claims[0]['text'], proposal)
        self.assertTrue(row['wording_auto_applied'])
        self.assertEqual(row['relation'], 'INSUFFICIENT')
        self.assertFalse(checks[0]['grounded'])
        self.assertEqual(row['retrieved_sources'], [])

    def test_repaired_text_is_atomically_checked_and_can_still_be_blocked(self):
        model = Model(proposal='Alex led testing and increased throughput by 900%.', fullbad=True)
        fixed = 'For Atlas, Alex wrote Python interface tests.'
        model.wording_step = lambda action,before,text,issues: (
            {'text':fixed} if action=='repair' else {'decision':'equivalent' if text==fixed else 'changed','reason':''})
        claims, _, report = GroundingService(model=model,retriever=AllSources()).run(
            [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        row=report['results'][CLAIM['claim_id']]
        self.assertEqual(row['proposed_text'], fixed)
        self.assertEqual(row['proposal_check']['relation'], 'CONTRADICTED')
        self.assertEqual(claims[0]['text'], TEXT)
        self.assertFalse(row['wording_auto_applied'])

    def test_repaired_wording_with_evidence_is_applied_to_final_text(self):
        import hashlib
        initial = 'Alex led all Atlas testing.'
        fixed = 'For Atlas, Alex wrote Python interface tests.'
        model = Model(proposal=initial)
        model.wording_step = lambda action, before, text, issues: (
            {'text':fixed} if action == 'repair' else
            {'decision':'equivalent' if text == fixed else 'changed','reason':''})
        claims, checks, report = GroundingService(model=model, retriever=AllSources()).run(
            [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        row = report['results'][CLAIM['claim_id']]
        self.assertTrue(checks[0]['grounded'])
        self.assertTrue(row['wording_auto_applied'])
        self.assertEqual(row['wording_review']['initial_text'], initial)
        self.assertEqual(claims[0]['text'], fixed)
        self.assertEqual(row['proposal_check']['claim_text_sha256'], hashlib.sha256(fixed.encode()).hexdigest())

    def test_estimate_needs_an_estimator_even_if_model_votes_equivalent(self):
        from backend.services.fact_lock import wording_invariants
        original = 'Morgan estimated a 20% cost reduction.'
        self.assertTrue(wording_invariants(original, 'There was an estimated 20% cost reduction.'))
        self.assertFalse(wording_invariants(original, "Morgan's estimate was a 20% cost reduction."))

    def test_semantic_vote_does_not_erase_a_specific_missing_detail(self):
        from backend.services.wording_review import may_apply_wording
        base = ({'equivalent': True}, {'relation':'SUPPORTED'}, {'relation':'SUPPORTED'}, [], False)
        self.assertFalse(may_apply_wording(*base, 'Alex ran offline tests.', 'Alex ran tests.',
                                            {'lost_supported_details':['offline']}))
        self.assertTrue(may_apply_wording(*base, 'Alex ran offline tests.', 'The offline tests were run by Alex.',
                                           {'lost_supported_details':['offline tests']}))

    def test_model_failure_abstains(self):
        def fail(*args):
            raise TimeoutError('fixture')
        _, review = review_edit(fail, '参与开发。', '主导开发。')
        self.assertFalse(review['equivalent'])
        self.assertFalse(review['repair_attempted'])
