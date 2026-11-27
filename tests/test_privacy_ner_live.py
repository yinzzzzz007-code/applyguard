"""Small real local-model smoke on synthetic input; not an accuracy benchmark."""
import unittest
import json
from backend.services.privacy_ner import status, detect
from backend.services.outbound_privacy import PrivacySession
from backend.services.harness_conflicts import review_conflicts


class PrivacyNerLiveTests(unittest.TestCase):
    @unittest.skipUnless(status()['state']=='available','local model or ONNX runtime unavailable')
    def test_real_model_masks_names_without_changing_metrics(self):
        for name in ('张三','李小明','张伟'):
            text=f'{name}参与系统测试，团队离线性能约提升20%。'
            with self.subTest(name=name):
                privacy=PrivacySession()
                protected=privacy.protect(text)
                self.assertNotIn(name,protected)
                self.assertIn('团队离线性能约提升20%',protected)
                self.assertEqual(privacy.restore(protected),text)

    @unittest.skipUnless(status()['state']=='available','local model or ONNX runtime unavailable')
    def test_nested_model_clients_keep_existing_pseudonyms(self):
        first=PrivacySession(); second=PrivacySession()
        original='张三参与 Atlas 项目，团队离线性能约提升20%。'
        protected=first.protect(original)
        self.assertEqual(second.protect(protected),protected)
        self.assertEqual(first.restore(second.protect(protected)),original)

    @unittest.skipUnless(status()['state']=='available','local model or ONNX runtime unavailable')
    def test_synthetic_non_person_clauses_are_not_erased(self):
        privacy=PrivacySession()
        text='团队负责测试，项目参与评估；离线准确率达到 85%。'
        self.assertEqual(privacy.protect(text),text)

    @unittest.skipUnless(status()['state']=='available','local model or ONNX runtime unavailable')
    def test_conflict_review_sends_masked_names_and_restores_citations(self):
        class Model:
            def complete_json(self, instruction, data):
                self.data=data
                rows=json.loads(data)
                return {'conflicts':[{'left_id':'a','right_id':'b','left_quote':rows[0]['text'],
                    'right_quote':rows[1]['text'],'reason':'待核对'}]}
        model=Model()
        cards=[{'id':'a','quote':'张三负责测试，结果为 20%。','source':{'path':'a'}},
               {'id':'b','quote':'张三负责测试，结果为 10%。','source':{'path':'b'}}]
        result=review_conflicts(cards,PrivacySession(),model)
        self.assertNotIn('张三',model.data)
        self.assertEqual(result[0]['left_quote'],cards[0]['quote'])

    @unittest.skipUnless(status()['state']=='available','local model or ONNX runtime unavailable')
    def test_synthetic_names_in_varied_contexts_and_chunk_boundary(self):
        cases=[('张三参与项目测试。','张三'),('李小明在星河公司参与项目。','李小明'),
               ('候选人王晓明负责训练。','王晓明'),('张伟负责测试。','张伟'),
               ('姓名：刘芳，参与数据清洗。','刘芳'),('负责人：陈思远。','陈思远'),
               ('Alice Wang worked on the project.','Alice Wang'),('实习生周雨婷负责模型评估。','周雨婷'),
               ('该项目由赵敏协助完成。','赵敏'),('作者：赵一鸣；实现了缓存。','赵一鸣'),
               ('项目'*149+'张三参与测试。','张三')]
        for text,name in cases:
            with self.subTest(name=name):
                left=text.index(name)
                self.assertTrue(any(start<=left and end>=left+len(name) for start,end in detect(text)))


if __name__=='__main__':unittest.main()
