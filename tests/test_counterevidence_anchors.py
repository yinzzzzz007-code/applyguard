import json
import unittest
from backend.services.structured_verifier import StructuredVerifier


class CounterevidenceAnchorsTests(unittest.TestCase):
    def verify(self, *, other_project=False, connector=' '):
        original='阶段性提升 GPU 利用率约 15%。'
        quote='本项目 GPU 利用率提升约 10%。'
        class Model:
            def complete_structured(self, prompt, data, schema):
                if prompt.startswith('Split'):
                    return {'claim_a':{'assertions':['我阶段性提升了 GPU 利用率约 15%。']}}
                verdict={'relation':'CONTRADICTED','reason':f'DRAFT[{original[:-1]}]{connector}SOURCE[{quote[:-1]}] 同一指标数值不同。',
                         'citations':[{'source_id':'src_a','quote':quote}]}
                return {'claim_a':{'full_claim':verdict,'atoms':{'a1':{**verdict,'claim_excerpt':original[:-1]}},'missing_assertions':[]}}
        source={'source_id':'src_a','evidence_id':'ev_a','sha256':'version-a','title':'training.md',
                'candidate_id':'candidate_a','experience_id':'different_project' if other_project else 'project_a','text':quote}
        return StructuredVerifier(Model()).verify([{'claim_id':'claim_a','text':original}],
            {'claim_a':{'candidate_id':'candidate_a','experience_id':'project_a'}},{'claim_a':[source]})['claim_a']

    def test_model_paraphrase_does_not_erase_anchored_numeric_conflict(self):
        result=self.verify()
        self.assertEqual(result['relation'],'CONTRADICTED')
        self.assertEqual(result['atoms'][0]['claim_excerpt'],'阶段性提升 GPU 利用率约 15%')
        self.assertTrue(result['atoms'][0]['citations'])

    def test_explanation_connectors_do_not_change_cited_conflict(self):
        for connector in (' 与 ', ' versus ', '，', '\n'):
            with self.subTest(connector=connector):
                self.assertEqual(self.verify(connector=connector)['relation'],'CONTRADICTED')

    def test_other_project_cannot_become_counterevidence(self):
        result=self.verify(other_project=True)
        self.assertEqual(result['relation'],'INSUFFICIENT')
        self.assertFalse(result['atoms'][0]['citations'])
