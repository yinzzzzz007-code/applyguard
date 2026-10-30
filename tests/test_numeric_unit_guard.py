"""Regression for a discovered error; not an independent accuracy benchmark."""
import json,unittest
from backend.services.structured_verifier import StructuredVerifier,guard_percent_units

class AlwaysSupports:
    def complete_structured(self,prompt,data,schema):
        data=json.loads(data)
        if prompt.startswith('Split'):return {cid:{'assertions':[r['full_claim']]} for cid,r in data.items()}
        result={}
        for cid,r in data.items():
            verdict={'relation':'SUPPORTED','reason':'simulated erroneous approval','citations':[{'source_id':'s','quote':r['sources'][0]['text']}]}
            result[cid]={'full_claim':verdict,'atoms':{a:verdict for a in r['atoms']},'missing_assertions':[]} if 'atoms' in r else verdict
        return result

class NumericUnitTests(unittest.TestCase):
    def check(self,claim,quote,relation='SUPPORTED'):
        return guard_percent_units(claim,{'relation':relation,'reason':'fixture','citations':[{'quote':quote}]})['relation']
    def test_percent_point_substitution_requires_review(self):
        for claim,quote in [('准确率提高4%','准确率80%到84%，提高4个百分点，按相对增幅计算为5%。'),
                            ('Accuracy increased 4 percent.','Accuracy increased 4 percentage points.'),
                            ('提高4.0％','提高4个百分点')]:
            with self.subTest(claim=claim):self.assertEqual(self.check(claim,quote),'INSUFFICIENT')
    def test_valid_units_remain_supported(self):
        for claim,quote in [('提高4个百分点','80%到84%，提高4个百分点'),('相对提高5%','提高4个百分点，相对提高5%'),
                            ('成本降低4%','成本降低4%，准确率提高4个百分点')]:
            with self.subTest(claim=claim):self.assertEqual(self.check(claim,quote),'SUPPORTED')
    def test_does_not_override_existing_rejection(self):
        self.assertEqual(self.check('提高4%','提高4个百分点','CONTRADICTED'),'CONTRADICTED')
    def test_both_verifier_paths_override_erroneous_model_approval(self):
        claim={'claim_id':'c','text':'苏同学测得准确率提高4%'}
        source={'source_id':'s','evidence_id':'e','text':'苏同学测得准确率80%到84%，提高4个百分点，相对提高5%。','candidate_id':'p','experience_id':'x','sha256':'a'*64}
        contexts={'c':{'candidate_id':'p','experience_id':'x'}};hits={'c':[source]}
        verifier=StructuredVerifier(AlwaysSupports())
        self.assertEqual(verifier.verify([claim],contexts,hits)['c']['relation'],'INSUFFICIENT')
        self.assertEqual(verifier.whole_claim([claim],contexts,hits)['c']['relation'],'INSUFFICIENT')

if __name__=='__main__':unittest.main()
