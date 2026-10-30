import copy,json,unittest
from backend.services.edit_guard import preservation

class InventoryTests(unittest.TestCase):
    def test_unchanged_polish_reuses_only_current_run_verification(self):
        from tests.test_grounding_v2 import Model
        from tests.test_grounding import AllSources,experience,CLAIM,TEXT
        from backend.services.grounded_workflow import GroundingService
        model=Model();service=GroundingService(retriever=AllSources(),model=model)
        claims,checks,report=service.run([copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(claims[0]['text'],TEXT);self.assertEqual(checks[0]['state'],'VERIFIED')
        self.assertEqual(sum(p.startswith('Check') for p in model.calls),1)
        self.assertTrue(report['results'][CLAIM['claim_id']]['reused_current_run_original_check'])
        service.run([copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(sum(p.startswith('Check') for p in model.calls),2)
    def test_rejected_edit_reuses_fresh_original_check_without_third_verification(self):
        from tests.test_grounding_v2 import Model
        from tests.test_grounding import AllSources,experience,CLAIM,TEXT
        from backend.services.grounded_workflow import GroundingService
        model=Model(proposal='Alex increased throughput by 900%.')
        claims,checks,report=GroundingService(retriever=AllSources(),model=model).run([copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(sum(p.startswith('Check') for p in model.calls),2)
        self.assertEqual(claims[0]['text'],TEXT);self.assertEqual(checks[0]['state'],'VERIFIED')
        self.assertTrue(report['results'][CLAIM['claim_id']]['proposal_rejected'])
    def test_wrong_original_is_not_protected_as_true(self):
        captured={}
        class Model:
            def complete_structured(self,prompt,data,schema):
                captured.update(json.loads(data));return {'c':{'lost_supported_details':[],'reason':'supported details retained'}}
        result=preservation(Model(),[{'claim_id':'c','text':'Lin led Atlas and used SQL.'}],
            [{'claim_id':'c','text':'Lin used SQL; Zhou led Atlas.'}],{'c':[]},
            {'c':{'complete':True,'atoms':[{'text':'Lin led Atlas','relation':'CONTRADICTED'},{'text':'Lin used SQL','relation':'SUPPORTED'}]}})
        self.assertEqual(captured['c']['original'],'Lin used SQL');self.assertEqual(result['c']['lost_supported_details'],[])
    def test_incomplete_original_inventory_prevents_application(self):
        result=preservation(object(),[{'claim_id':'c','text':'84/100 offline'}],[{'claim_id':'c','text':'84% production'}],{}, {'c':{'complete':False}})
        self.assertTrue(result['c']['lost_supported_details'])
    def test_all_supported_fact_categories_are_preserved_in_input(self):
        facts=['Lin','Atlas','contributor','SQL','84/100','2026','offline only','did not train']
        class Model:
            def complete_structured(self,prompt,data,schema):
                self.data=json.loads(data);return {'c':{'lost_supported_details':['offline only'],'reason':'scope removed'}}
        m=Model();r=preservation(m,[{'claim_id':'c','text':' '.join(facts)}],[{'claim_id':'c','text':'Lin led production training'}],{},
            {'c':{'complete':True,'atoms':[{'text':f,'relation':'SUPPORTED'} for f in facts]}})
        self.assertEqual(m.data['c']['original'].split('\n'),facts)
        self.assertEqual(r['c']['lost_supported_details'],['offline only','did not train'])

if __name__=='__main__':unittest.main()
