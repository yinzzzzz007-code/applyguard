"""Observed failures plus adversarial boundary cases; model fixtures are not live scores."""
import json,unittest
from backend.services.edit_guard import preservation
from backend.services.edit_invariants import equivalent_point_detail,lost_qualifiers

class PreservationModel:
    def __init__(self,loss=()):self.loss=list(loss)
    def complete_structured(self,prompt,data,schema):
        return {cid:{'lost_supported_details':self.loss,'reason':'simulated model judgment'} for cid in json.loads(data)}

def check(original,proposal,loss=(),atoms=None,relation='SUPPORTED'):
    inventory={'c':{'complete':True,'relation':relation,'atoms':atoms or [{'text':original,'relation':'SUPPORTED'}]}}
    return preservation(PreservationModel(loss),[{'claim_id':'c','text':original}],
        [{'claim_id':'c','text':proposal}],{'c':[]},inventory)['c']

class EditPreservationV2Tests(unittest.TestCase):
    def test_atomic_coverage_accepts_proven_delta_but_not_wrong_endpoints(self):
        from backend.services.structured_verifier import missing_numeric_qualifiers
        text='准确率从80%变为84%，提高4个百分点。'
        self.assertEqual(missing_numeric_qualifiers(text,['准确率从80%提升至84%。']),[])
        self.assertIn('4个百分点',missing_numeric_qualifiers(text,['准确率从80%提升至85%。']))
    def test_observed_not_implemented_loss_is_caught_despite_model_approval(self):
        row=check('林同学负责SQL分析，测算预计成本下降12%，尚未实施；周同学是负责人。',
                  '林同学负责SQL分析，测算预计成本下降12%，周同学负责实施。')
        self.assertIn('尚未实施',row['lost_supported_details'])
    def test_full_original_protects_qualifier_even_if_atoms_wrongly_omit_it(self):
        row=check('方案预计节约12%，尚未实施。','方案预计节约12%。',
                  atoms=[{'text':'方案预计节约12%。','relation':'SUPPORTED'}])
        self.assertTrue(row['qualifier_findings'])
    def test_equivalent_delta_removed_without_dropping_other_losses(self):
        row=check('苏同学负责评测，准确率从80%变为84%，提高4个百分点；未参与模型训练。',
                  '苏同学负责评测，准确率从80%提升至84%。', ['提高4个百分点','未参与模型训练'])
        self.assertEqual(row['resolved_equivalences'],['提高4个百分点'])
        self.assertIn('未参与模型训练',row['lost_supported_details'])
    def test_exact_delta_can_be_omitted_when_endpoints_and_scope_retained(self):
        row=check('离线准确率从80%变为84%，提高4个百分点；未参与模型训练。',
                  '离线准确率从80%提升至84%；未参与模型训练。',['提高4个百分点'])
        self.assertFalse(row['lost_supported_details'])
    def test_parameterized_exact_deltas_chinese_and_english(self):
        for start in [40,61,70,80,90]:
            for delta in [1,2,4]:
                for english in [False,True]:
                    source=(f'Accuracy increased from {start}% to {start+delta}%, an increase of {delta} percentage points.' if english
                            else f'准确率从{start}%变为{start+delta}%，提高{delta}个百分点。')
                    proposed=f'Accuracy increased from {start}% to {start+delta}%.' if english else f'准确率{start}%提升至{start+delta}%。'
                    detail=f'increase of {delta} percentage points' if english else f'提高{delta}个百分点'
                    with self.subTest(start=start,delta=delta,english=english):self.assertTrue(equivalent_point_detail(detail,source,proposed))
    def test_different_direction_metric_scope_or_unit_never_discharge(self):
        source='离线准确率从80%变为84%，提高4个百分点。'
        for detail,proposal in [('下降4个百分点','准确率从80%变为84%'),('提高4%','准确率从80%变为84%'),
            ('提高4个百分点','准确率从80%变为85%'),('提高4个百分点','召回率从80%变为84%'),
            ('离线提高4个百分点','准确率从80%变为84%'),('2025年提高4个百分点','准确率从80%变为84%'),
            ('-4 percentage points','准确率从80%变为84%'),('提高4个百分点','准确率提高4个百分点'),
            ('提高4个百分点','准确率从80%变为84%，召回率从60%变为64%')]:
            with self.subTest(detail=detail,proposal=proposal):self.assertFalse(equivalent_point_detail(detail,source,proposal))
    def test_decimal_decrease_is_exact(self):
        self.assertTrue(equivalent_point_detail('下降0.3个百分点','通过率从90.4%降至90.1%，下降0.3个百分点。','通过率90.4%下降到90.1%。'))
        self.assertFalse(equivalent_point_detail('下降0.2个百分点','通过率从90.4%降至90.1%，下降0.3个百分点。','通过率90.4%下降到90.1%。'))
    def test_incorrect_original_is_not_granted_equivalence_override(self):
        row=check('准确率从80%变为84%，提高4个百分点。','准确率从80%变为84%。',
            ['提高4个百分点'],relation='INSUFFICIENT')
        self.assertTrue(row['lost_supported_details'])
    def test_correcting_stale_negation_does_not_force_retention(self):
        row=check('项目尚未实施。','项目已经实施。',atoms=[{'text':'项目尚未实施。','relation':'CONTRADICTED'}],relation='CONTRADICTED')
        self.assertFalse(row['lost_supported_details'])
    def test_equivalent_qualifier_paraphrases(self):
        for old,new in [('方案尚未实施','方案未付诸实施'),('预计降低成本','预估降低成本'),
            ('原型阶段','概念验证阶段'),('Alex assisted the team','Alex helped the team'),
            ('estimated savings','estimating savings'),('projected savings','projecting savings'),
            ('did not train the model','without training the model'),
            ('not yet implemented','unimplemented'),('did not train the model','not involved in model training'),
            ('项目未进入生产','项目尚未上线'),('未主导项目','并非项目负责人')]:
            with self.subTest(old=old,new=new):self.assertFalse(lost_qualifiers(old,new))
    def test_real_english_delta_paraphrase(self):
        original='Riley evaluated Seabird3 offline: accuracy increased from 80% to 84%, an increase of 4 percentage points. Riley did not train the model.'
        proposed='Riley evaluated Seabird3 offline, confirming accuracy improvement from 80% to 84%, without training the model.'
        row=check(original,proposed,['The accuracy increase of Seabird3 was 4 percentage points.'])
        self.assertFalse(row['lost_supported_details'])
    def test_model_false_loss_can_resolve_only_a_pure_equivalent_qualifier(self):
        self.assertFalse(check('Alex estimated a 12% saving.','Alex is estimating a 12% saving.',['estimated'])['lost_supported_details'])
        self.assertTrue(check('Alex estimated a 12% saving.','Alex is estimating a 12% saving.',['Alex estimated 12% for 2025'])['lost_supported_details'])
    def test_personal_role_limit_cannot_silently_disappear(self):
        for old,new in [('我只实现Vue表单','我实现Vue表单'),('Alex implemented only the React form','Alex implemented the React form')]:
            with self.subTest(old=old):self.assertTrue(lost_qualifiers(old,new))
    def test_measurement_must_not_become_causation_when_redundant_delta_is_removed(self):
        from backend.services.asu_resume import proposal_violations
        original='Riley evaluated Seabird offline: accuracy increased from 80% to 84%, an increase of 4 percentage points. Riley did not train the model.'
        good='Riley evaluated Seabird offline, confirming accuracy improvement from 80% to 84%, without training the model.'
        bad=good.replace('confirming accuracy improvement','contributing to an accuracy increase')
        self.assertFalse(proposal_violations(original,good));self.assertTrue(proposal_violations(original,bad))
        self.assertFalse(proposal_violations(original,bad,[{'text':bad}]))
    def test_qualifier_deletion_and_negation_substitution(self):
        for original,proposal in [('尚未实施，预计下降12%','已经实施，下降12%'),('仅离线测试','生产测试'),
            ('未参与模型训练','未参与模型部署'),('prototype only','production system'),
            ('pilot in one store','deployed in all stores'),('匿名数据','真实用户数据'),
            ('协助负责人分析','主导分析'),('不是项目负责人','项目负责人')]:
            with self.subTest(original=original):self.assertTrue(lost_qualifiers(original,proposal))

if __name__=='__main__':unittest.main()
