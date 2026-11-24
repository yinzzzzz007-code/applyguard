import json
import unittest
from backend.services.atomic_verifier import AtomicVerifier
from backend.services.model_client import ModelFailure
from backend.services.sag_grounding import _retrieval_strategy
from unittest.mock import patch

class RetryModel:
    def __init__(self, alternative):
        self.alternative=alternative
        self.calls=[]
    def complete_structured(self,prompt,data,schema):
        items=json.loads(data)['items']
        self.calls.append([row['id'] for row in items])
        if len(self.calls)==2 and isinstance(self.alternative,Exception):
            raise self.alternative
        return {row['id']:{'text': row['draft'] if len(self.calls)==1 else self.alternative} for row in items}

class PolishRetryTests(unittest.TestCase):
    def run_polish(self, model):
        claim={'claim_id':'one','text':'负责 Python 测试工作'}
        verifier=AtomicVerifier(model)
        output=verifier.polish([claim],{'one':{'candidate_id':'test','experience_id':'exp'}},{'one':[]},'Python')
        return verifier, output[0]['text']

    def test_unchanged_draft_retried_once(self):
        model=RetryModel('测试工作由本人使用 Python 负责')
        verifier,text=self.run_polish(model)
        self.assertEqual(text,'测试工作由本人使用 Python 负责')
        self.assertEqual(model.calls,[['one'],['one']])
        self.assertEqual(verifier.polish_source['unchanged_retry_count'],1)

    def test_retry_failure_preserves_original_without_fabrication(self):
        model=RetryModel(ModelFailure('offline',retryable=False))
        _,text=self.run_polish(model)
        self.assertEqual(text,'负责 Python 测试工作')

    def test_polish_quality_rejects_one_word_and_changed_year(self):
        from backend.services.asu_resume import polish_quality
        original='独立主导 AtlasPersona 研究（研究会议 2027 投稿），完成实验设计、用户研究与论文撰写。'
        self.assertTrue(polish_quality(original,original.replace('完成','完成了')))
        self.assertTrue(polish_quality(original,original.replace('2027','2025')))
        numeric_only='参与挑战（Top 4.7%），负责模型训练和数据分析，整理测试样本并复核模型输出。'
        self.assertTrue(polish_quality(numeric_only,numeric_only.replace('Top 4.7%','排名247/5255，前4.7%')))

    def test_redundant_year_can_be_merged_but_a_distinct_year_must_remain(self):
        from backend.services.asu_resume import polish_quality
        old='Project Delta 2026. Led the 2026 Project Delta evaluation.'
        self.assertFalse(polish_quality(old,'Led evaluation of Project Delta in 2026.'))
        self.assertTrue(polish_quality(old,'Led evaluation of Project Delta in 2025.'))

    def test_missing_mention_is_distinct_from_a_contradictory_rank(self):
        from backend.services.structured_verifier import guard_cited_verdict
        def relation(quote,reason):
            return guard_cited_verdict('项目 A 排名 246/5,252。',{'relation':'CONTRADICTED',
                'citations':[{'quote':quote}], 'reason':reason})['relation']
        self.assertEqual(relation('# 项目 B', '文档介绍另一项目。'),'INSUFFICIENT')
        self.assertEqual(relation('项目 B 用于检索文档。','来源未提及项目 A。'),'INSUFFICIENT')
        self.assertEqual(relation('# 项目 A 团队排名 247/5,255', '与原文名次矛盾。'),'CONTRADICTED')
        self.assertEqual(relation('项目 A 团队排名 247/5,255。','证书记载 247/5,255，而非 246/5,252。'),'CONTRADICTED')

    def test_wording_repair_cannot_reintroduce_a_year(self):
        import copy
        from backend.services.grounded_workflow import GroundingService
        from tests.test_grounding import AllSources,experience,CLAIM,TEXT
        from tests.test_grounding_v2 import Model
        proposal='For Atlas, Alex wrote Python interface tests.'
        with patch('backend.services.grounded_workflow.review_edit', return_value=(
                'In 2025, Alex wrote Python interface tests for Atlas.', {'equivalent':True})):
            claims,_,report=GroundingService(retriever=AllSources(),model=Model(proposal=proposal)).run(
                [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        row=report['results'][CLAIM['claim_id']]
        self.assertEqual(row['proposed_text'],proposal)
        self.assertEqual(claims[0]['text'],TEXT)
        self.assertFalse(row['wording_review']['equivalent'])
        self.assertTrue(row['wording_review']['repair_quality_issues'])

    def test_conflicting_claim_is_skipped_and_other_claim_is_polished(self):
        first='独立主导 AtlasPersona 研究（研究会议 2027 投稿），完成实验设计和论文撰写。'
        second='负责 Python 测试工作'
        revised='测试工作由本人使用 Python 负责'
        class MixedModel:
            def __init__(self):self.ids=[]
            def complete_structured(self,prompt,data,schema):
                entries=json.loads(data)['items']
                self.ids.extend(entry['id'] for entry in entries)
                return {entry['id']:{'text':revised} for entry in entries}
        model=MixedModel()
        hits={'one':[{'source_id':'src','text':'材料另有年份。'}], 'two':[]}
        checks={'one':{'relation':'CONTRADICTED','atoms':[]},'two':{'relation':'INSUFFICIENT','atoms':[]}}
        verifier=AtomicVerifier(model)
        output=verifier.polish([{'claim_id':'one','text':first},{'claim_id':'two','text':second}],
            {'one':{'candidate_id':'test','experience_id':'one'},'two':{'candidate_id':'test','experience_id':'two'}},
            hits,'Python',original_checks=checks)
        self.assertEqual(output[0]['text'],first)
        self.assertEqual(output[1]['text'],revised)
        self.assertNotIn('one',model.ids)
        self.assertEqual(verifier.polish_source['conflict_claim_ids'],['one'])
        self.assertTrue(hits['one'])

    def test_model_year_drift_is_not_presented_as_rewrite(self):
        original='独立主导研究（研究会议 2027 投稿），完成实验设计和论文撰写。'
        class DriftModel:
            def complete_structured(self,prompt,data,schema):
                return {'one':{'text':original.replace('2027','2025')}}
        verifier=AtomicVerifier(DriftModel())
        output=verifier.polish([{'claim_id':'one','text':original}],
            {'one':{'candidate_id':'test','experience_id':'exp'}},{'one':[]},'Python')
        self.assertEqual(output[0]['text'],original)
        self.assertEqual(verifier.polish_source['year_drift_claim_ids'],['one'])

    def test_gemini_gateway_defaults_vector_but_accepts_graph_override(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertEqual(_retrieval_strategy('https://api.chatanywhere.tech/v1'),'vector')
            self.assertEqual(_retrieval_strategy('https://fixture.invalid/v1'),'full_expand')
        with patch.dict('os.environ',{'APPLYGUARD_GROUNDING_STRATEGY':'full_expand'}):
            self.assertEqual(_retrieval_strategy('https://api.chatanywhere.tech/v1'),'full_expand')

if __name__ == '__main__':
    unittest.main()
