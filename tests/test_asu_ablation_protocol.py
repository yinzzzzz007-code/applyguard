import unittest
from eval.asu_ablation.cases import cases
from scripts.evaluate_asu_ablation import fixture,metrics,ARMS

class AblationProtocolTests(unittest.TestCase):
    def test_sixty_unique_cases_twenty_templates_two_languages(self):
        data=cases();self.assertEqual(len(data),60);self.assertEqual(len({r['id'] for r in data}),60)
        self.assertEqual(len({r['template'] for r in data}),20)
        self.assertEqual(sum(r['language']=='en' for r in data),30)
        self.assertTrue(all(r['source'] and r['required_facts'] for r in data))
    def test_no_cross_experience_sources(self):
        claims,contexts,hits=fixture(cases()[:3])
        for c in claims:
            cid=c['claim_id'];self.assertEqual(len(hits[cid]),1)
            self.assertEqual(hits[cid][0]['experience_id'],contexts[cid]['experience_id'])
    def test_metrics_keep_wrong_safe_changed_and_total_denominators_distinct(self):
        rows=[]
        for arm in ARMS:
            for changed,wrong,old,new in [(True,True,True,False),(True,False,False,True),(False,False,True,True)]:
                rows.append({'arm':arm,'changed':changed,'audit':{'wrong_edit':wrong},'old_guard_accept':old,
                    'new_guard_accept':new,'new_final_relation':'SUPPORTED'})
        for m in metrics(rows).values():
            self.assertEqual((m['valid'],m['changed'],m['wrong_proposals'],m['safe_changed']),(3,2,1,1))
            self.assertEqual(m['old']['wrong_edits_retained'],1);self.assertEqual(m['new']['wrong_edits_retained'],0)
            self.assertEqual(m['old']['safe_edits_blocked'],1);self.assertEqual(m['new']['safe_edits_blocked'],0)

if __name__=='__main__':unittest.main()
