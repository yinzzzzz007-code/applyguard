import copy
import hashlib
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.services.grounded_workflow import export_grounded, GroundingService
from backend.services.model_client import HttpModelClient

ROOT=Path(__file__).resolve().parents[1]
class ReviewExportTests(unittest.TestCase):
    def request(self):
        text='仅离线测试，约降低30%，尚未上线。'
        return {'candidate_id':'cand_demo_001','application_id':'app_review_test',
            'jd_text':'招聘 Python 后端工程师，要求掌握 Python 和 HTTP API 开发，能够编写自动化测试。',
            'claims':[{'claim_id':'claim_manual_test','text':text,'state':'VERIFIED'}],
            'human_confirmed':True,'acknowledge_unverified':True,'export_policy':'user_confirmed',
            'confirmed_text_sha256':hashlib.sha256(text.encode()).hexdigest()}
    def test_user_export_preserves_text_but_does_not_forge_support(self):
        request=self.request()
        with patch('backend.services.grounded_workflow.GroundingService') as model:
            out=export_grounded(ROOT/'data/career-vault.seed.json',request)
        model.assert_not_called()
        self.assertEqual(out['text'],request['claims'][0]['text'])
        self.assertEqual(out['material_support'],'NOT_ATOMICALLY_VERIFIED')
        self.assertTrue(out['user_confirmed'])
        self.assertEqual(out['review_record']['claims'][0]['local_rule_state'],'BLOCKED')
    def test_final_confirmation_and_digest_are_required(self):
        for field,value in [('human_confirmed',False),('acknowledge_unverified',False),('confirmed_text_sha256','stale')]:
            request=self.request();request[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):export_grounded(ROOT/'data/career-vault.seed.json',request)
    def test_invalid_and_empty_claims_are_rejected_even_with_confirmation(self):
        for claims in [[],[{'claim_id':'claim_bad','text':'x'*421}],[{'claim_id':'claim_x','text':'x'}]*2]:
            request=self.request();request['claims']=claims
            with self.assertRaises(ValueError):export_grounded(ROOT/'data/career-vault.seed.json',request)
    def test_unknown_policy_is_not_a_bypass(self):
        request=self.request();request['export_policy']='anything'
        with self.assertRaises(ValueError):export_grounded(ROOT/'data/career-vault.seed.json',request)
    def test_short_multiline_draft_keeps_qualifiers(self):
        from backend.services.resume_draft_vault import _claim_text
        text = "Atlas API\n延迟降低约30%。\n仅离线测试，尚未上线。"
        self.assertEqual(_claim_text("", "Atlas API", "", text), text)

    def test_task_routing_and_legacy_fallback(self):
        with patch.dict(os.environ,{'APPLYGUARD_AI_MODEL':'gpt-4o','APPLYGUARD_COMPLEX_AI_MODEL':'gemini-3.1-flash-lite-preview'},clear=True):
            self.assertEqual(HttpModelClient().model,'gpt-4o')
            self.assertEqual(GroundingService().model.model,'gemini-3.1-flash-lite-preview')
            self.assertEqual(HttpModelClient(model='explicit',task='complex').model,'explicit')
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(HttpModelClient(task='complex').model,'gpt-4o-mini')
