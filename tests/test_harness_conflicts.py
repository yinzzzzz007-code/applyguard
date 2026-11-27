import unittest
import hashlib
import tempfile
from pathlib import Path
from backend.services.harness_conflicts import review_conflicts, source_is_current
from backend.services.outbound_privacy import PrivacySession


class FakeModel:
    def __init__(self, result):self.result=result;self.inputs=[]
    def complete_json(self, instruction, data):self.inputs.append(data);return self.result


class HarnessConflictTests(unittest.TestCase):
    def test_only_exact_approved_excerpts_are_reported(self):
        cards=[{'id':'a','quote':'Atlas 离线测试提升 20%。','source':{'path':'a.md'}},
               {'id':'b','quote':'Atlas 离线测试提升 10%。','source':{'path':'b.md'}}]
        model=FakeModel({'conflicts':[
            {'left_id':'a','right_id':'b','left_quote':'提升 20%','right_quote':'提升 10%','reason':'数字不一致'},
            {'left_id':'a','right_id':'b','left_quote':'提升 99%','right_quote':'提升 10%','reason':'伪造引用'},
            {'left_id':'a','right_id':'bad','left_quote':'提升 20%','right_quote':'不存在','reason':'无效来源'}]})
        result=review_conflicts(cards,PrivacySession(),model)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['left_quote'],'提升 20%')
        self.assertEqual(result[0]['state'],'POTENTIAL_CONFLICT')

    def test_invalid_response_is_not_a_pass(self):
        cards=[{'id':'a','quote':'a','source':{}},{'id':'b','quote':'b','source':{}}]
        with self.assertRaises(ValueError):review_conflicts(cards,PrivacySession(),FakeModel({}))

    def test_cancellation_prevents_model_call(self):
        cards=[{'id':'a','quote':'a','source':{}},{'id':'b','quote':'b','source':{}}]
        model=FakeModel({'conflicts':[]})
        with self.assertRaises(ValueError):
            review_conflicts(cards,PrivacySession(),model,should_cancel=lambda:True)
        self.assertEqual(model.inputs,[])

    def test_changed_local_source_is_not_current(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();file=root/'evidence.txt';file.write_text('old',encoding='utf8')
            card={'source':{'kind':'local','root':str(root),'path':'evidence.txt',
                            'version':hashlib.sha256(b'old').hexdigest()}}
            grant={'roots':[str(root)],'repos':[]}
            self.assertTrue(source_is_current(card,grant))
            file.write_text('new',encoding='utf8')
            self.assertFalse(source_is_current(card,grant))


if __name__=='__main__':unittest.main()
