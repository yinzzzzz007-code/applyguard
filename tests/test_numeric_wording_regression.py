"""Regression tests for wording/evidence boundaries. No network or real resumes."""
import copy
import unittest

from backend.services.fact_lock import wording_invariants
from backend.services.grounded_workflow import GroundingService
from backend.services.structured_verifier import StructuredVerifier
from eval.career_holdout import RECORDS
from pathlib import Path
import json
from scripts.evaluate_wording_regression import numeric_pairs, optimistic_judge
from backend.services.wording_review import review_edit
from tests.test_grounding import AllSources, CLAIM, experience
from tests.test_grounding_v2 import Model
from tests.test_numeric_unit_guard import AlwaysSupports


class NumericWordingRegression(unittest.TestCase):
    def test_named_targets_keep_their_values_with_safe_reordering(self):
        original = '对甲方案，延迟约下降11%；对乙方案下降18%。'
        self.assertFalse(wording_invariants(original, '对乙方案延迟下降18%；对甲方案延迟约下降11%。'))
        self.assertTrue(wording_invariants(original, '对乙方案延迟约下降11%；对甲方案延迟下降18%。'))
        self.assertTrue(wording_invariants(original, '两种方案延迟分别下降约11%和18%。'))
        en = 'For plan A, latency fell about 11%; for plan B it fell 18%.'
        self.assertFalse(wording_invariants(en, 'For plan B it fell 18%; for plan A latency fell about 11%.'))
        self.assertTrue(wording_invariants(en, 'For plan B latency fell about 11%; for plan A it fell 18%.'))

    def test_named_metrics_keep_values_and_qualifiers(self):
        original = '准确率提升约5%，召回率提升8%。'
        self.assertFalse(wording_invariants(original, '召回率提升8%，准确率提升约5%。'))
        self.assertTrue(wording_invariants(original, '准确率提升8%，召回率提升约5%。'))
        self.assertTrue(wording_invariants(original, '准确率提升5%，召回率提升约8%。'))

    def test_approximation_must_stay_bound_to_the_same_number(self):
        cases = [
            ('对甲方案，延迟约下降11%；对乙方案下降18%。', '对甲方案，延迟约下降11%；对乙方案，延迟约下降18%。', True),
            ('对甲方案，延迟约下降11%；对乙方案下降18%。', '对乙方案延迟下降18%；对甲方案延迟约下降11%。', False),
            ('Plan A fell about 11%; plan B fell 18%.', 'Plan A fell about 11%; plan B fell approximately 18%.', True),
            ('Plan A fell about 11%; plan B fell 18%.', 'Plan B fell 18%; plan A fell approximately 11%.', False),
            ('延迟降低18%。', '延迟降低约18%。', True),
            ('Latency fell about 18%.', 'Latency fell 18%.', True),
        ]
        for before, after, should_hold in cases:
            with self.subTest(before=before, after=after):
                self.assertEqual(bool(wording_invariants(before, after)), should_hold)

    def test_bilingual_numeric_matrix_against_an_optimistic_judge(self):
        for name,old,new,label in numeric_pairs():
            with self.subTest(case=name):
                _, review = review_edit(optimistic_judge,old,new)
                self.assertEqual(review['equivalent'], label == 'SAFE')

    def test_first_prose_failures_stay_fixed(self):
        path = Path(__file__).resolve().parents[1] / 'eval/wording-prose-20261105.json'
        for row in json.loads(path.read_bytes())['cases']:
            with self.subTest(case=row['id']):
                _,trace = review_edit(optimistic_judge,row['original'],row['proposal'])
                self.assertEqual(trace['equivalent'],row['expected']=='SAFE')

    def test_same_estimator_participle_requires_a_clear_subject_and_amount(self):
        old = 'Morgan estimated a 20% cost reduction.'
        self.assertFalse(wording_invariants(old,'Morgan drafted a plan, estimating a 20% cost reduction.'))
        for new in ['Lee drafted a plan, estimating a 20% cost reduction for Morgan.',
                    'Morgan drafted a plan with Lee, estimating a 20% cost reduction.',
                    'Morgan drafted a plan, with Lee estimating a 20% cost reduction.',
                    'Morgan drafted a plan, estimating a 25% cost reduction.']:
            with self.subTest(new=new):
                self.assertTrue(wording_invariants(old,new))

    def test_pending_approval_and_fixed_calendar_durations(self):
        self.assertTrue(wording_invariants('发布尚待审批。','发布已获批。'))
        self.assertFalse(wording_invariants('故障间隔为两周。','故障间隔为14天。'))
        self.assertTrue(wording_invariants('测试持续两周。','测试持续两天。'))
        self.assertFalse(wording_invariants('巡检周期是21天。','巡检周期是三周。'))
        self.assertTrue(wording_invariants('测试持续一周。','测试持续7个工作日。'))
        self.assertFalse(wording_invariants('巡检周期是21天。','巡检周期是三个星期。'))
        old = '实验室委托审计组核查材料。'
        self.assertTrue(wording_invariants(old,'审计组委托实验室核查材料。'))
        self.assertFalse(wording_invariants(old,'材料由审计组受实验室委托核查。'))

    def test_original_quote_beats_a_reversed_or_wrong_unit_model_verdict(self):
        for text,quote,expected in [
            ('Latency went to 200 ms from 140 ms.', 'Latency fell from 200 ms to 140 ms.', 'INSUFFICIENT'),
            ('延迟从90毫秒降至35毫秒。','延迟从90毫秒降至35毫秒。','SUPPORTED'),
            ('通过率提高18个百分点。','通过率相对提高18%。','INSUFFICIENT'),
            ('Recall changed from 18% to 28%.','Precision changed from 28% to 18%. Recall rose from 18% to 28%.','SUPPORTED'),
            ('Latency changed from 35 ms to 80 ms.','Latency fell from 80 ms to 35 ms. Later latency rose from 35 ms to 80 ms.','SUPPORTED'),
        ]:
            with self.subTest(text=text):
                verifier = StructuredVerifier(AlwaysSupports())
                claim = {'claim_id':'c','text':text}
                source = dict(source_id='s',evidence_id='e',text=quote,candidate_id='p',experience_id='x',sha256='a'*64)
                context, hits = {'c':{'candidate_id':'p','experience_id':'x'}}, {'c':[source]}
                self.assertEqual(verifier.verify([claim],context,hits)['c']['relation'],expected)
                self.assertEqual(verifier.whole_claim([claim],context,hits)['c']['relation'],expected)

    def test_plain_json_model_has_the_same_numeric_guard(self):
        from backend.services.atomic_verifier import AtomicVerifier
        from tests.test_grounding import ScriptedModel
        text = 'Latency changed from 110 ms to 190 ms.'
        quote = 'Latency fell from 190 ms down to 110 ms.'
        source = dict(source_id='s',evidence_id='e',text=quote,candidate_id='p',experience_id='x',sha256='a'*64)
        row = AtomicVerifier(ScriptedModel()).verify([{'claim_id':'c','text':text}],
            {'c':{'candidate_id':'p','experience_id':'x'}}, {'c':[source]})['c']
        self.assertEqual(row['relation'],'INSUFFICIENT')

    def test_career_corpus_preserves_evidence_status_on_style_edit(self):
        # Seed the atomic verdict to isolate workflow routing. This is not a classifier benchmark.
        for record in RECORDS:
            for case in record['good'] + record['bad']:
                old = case[1]
                relation = case[2] if len(case)>2 else 'SUPPORTED'
                proposal = old[:-1] if old.endswith(('.', '。')) else old+'.'
                with self.subTest(project=record['id'],claim=old):
                    item = experience()
                    item['claims'][0]['text'] = old
                    item['evidence_sources'][0]['description'] = '\n'.join(record['sources'])
                    model = Model(proposal=proposal)
                    model.wording_step = optimistic_judge
                    original_step = model.complete_structured
                    def seeded_step(prompt,data,schema):
                        rows = original_step(prompt,data,schema)
                        if prompt.startswith('Check'):
                            for row in rows.values():
                                for verdict in [row['full_claim'], *row['atoms'].values()]:
                                    verdict['relation'] = relation
                        return rows
                    model.complete_structured = seeded_step
                    claim = {**copy.deepcopy(CLAIM),'text':old}
                    claims,checks,report = GroundingService(model=model,retriever=AllSources()).run(
                        [claim],[item],'cand_test','sag_atomic',polish=True)
                    result = report['results'][claim['claim_id']]
                    self.assertEqual(result['relation'], relation)
                    self.assertEqual(checks[0]['grounded'], relation=='SUPPORTED')
                    self.assertEqual(claims[0]['text'], old if relation=='CONTRADICTED' else proposal)
