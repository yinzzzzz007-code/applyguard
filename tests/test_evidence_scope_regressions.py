import time
import unittest
from unittest.mock import patch

from backend.services import github_app_session as app
from backend.services.draft_anchors import bind_assertion, draft_phrases
from backend.services.evidence_scope import matches_item, source_identity
from backend.services.rank_evidence import rank_conflict
from backend.services.structured_verifier import guard_cited_verdict


class MaterialScopeRegression(unittest.TestCase):
    def test_target_name_in_import_metadata_does_not_count_as_a_source(self):
        text = '# GitHub 来源\n{"repo":"org/finbot","experience":"ActionPersona","commit_sha":"abc"}\n\n# Finbot\nJob-matching software.'
        self.assertFalse(matches_item('ActionPersona','ActionPersona-readme.md',text))
        self.assertTrue(matches_item('Finbot','asset.md',text))
        origin,body=source_identity('asset.md',text)
        self.assertEqual(origin['repo'],'org/finbot')
        self.assertNotIn('ActionPersona',body)

    def test_unsupported_is_not_a_conflict(self):
        verdict={'relation':'CONTRADICTED','reason':'材料未提到这个指标。','citations':[{'quote':'# Sample Project'}]}
        self.assertEqual(guard_cited_verdict('我提高了准确率',verdict)['relation'],'INSUFFICIENT')
        verdict.update(reason='DRAFT[Phase alpha] SOURCE[Phase beta] 记录明确给出另一阶段。',
                       citations=[{'quote':'The report says Phase beta.'}])
        self.assertEqual(guard_cited_verdict('Phase alpha',verdict)['relation'],'CONTRADICTED')

    def test_same_metric_and_rank_on_both_sides(self):
        source={'text':'Nemotron competition. Placed 197th of 4185 teams.','title':'Nemotron.pdf'}
        self.assertIsNotNone(rank_conflict('Nemotron Kaggle Silver · 196/4,182','Nemotron',[source]))
        self.assertIsNone(rank_conflict('Nemotron 团队完成 10/20 个样本','Nemotron',[source]))
        self.assertIsNone(rank_conflict('Nemotron 排名 197/4,185','Nemotron',[source]))

    def test_repeated_and_multi_phrase_anchors(self):
        text='获得银牌。获得银牌。团队排名第二。'
        phrases=draft_phrases(text)
        row=bind_assertion('[p2,p3] 获得银牌并排名第二。',text,phrases)
        self.assertEqual([(p['start'],p['end']) for p in row['claim_spans']],[(5,10),(10,17)])
        for raw,reason in [('', 'empty_excerpt'),('获得银牌。','ambiguous_excerpt'),('[p9] 获奖','invalid_phrase_id'),('此人为获奖者','nonverbatim_without_phrase_id')]:
            self.assertEqual(bind_assertion(raw,text,phrases)['anchor_reason'],reason)

    def test_private_access_requires_device_confirmation_pin_and_an_active_grant(self):
        sha='b'*40
        install={'id':1,'client_id':'unit-app','permissions':{'contents':'read','metadata':'read'}}
        def api(path,token):
            self.assertEqual(token,'unit-token')
            if path.startswith('user/installations?'):return {'installations':[install]}
            if path.startswith('user/installations/1/'):return {'repositories':[{'full_name':'person/chosen','private':True}]}
            if path=='repos/person/chosen':return {'default_branch':'main'}
            if path.endswith('git/ref/heads/main'):return {'object':{'sha':sha,'type':'commit'}}
            self.fail(path)
        with patch.dict('os.environ',{'APPLYGUARD_GITHUB_APP_CLIENT_ID':'unit-app'}),patch.dict(app.SESSIONS,{},clear=True),patch.object(app,'oauth',side_effect=[{'device_code':'unit-device','user_code':'USER','expires_in':600},{'access_token':'unit-token'}]):
            init=app.handle({'action':'github_app_start'},api)
            handle=init['handle']
            self.assertEqual(init['url'],'https://github.com/login/device')
            with self.assertRaises(ValueError):app.repo_token(handle,'person/chosen',sha)
            self.assertTrue(app.handle({'action':'github_app_poll','handle':handle},api)['authorized'])
            with self.assertRaises(ValueError):app.repo_token(handle,'person/chosen',sha)
            pin=app.handle({'action':'github_app_pin','handle':handle,'repo':'person/chosen'},api)
            self.assertEqual(pin['spec'],'person/chosen@'+sha)
            self.assertEqual(app.repo_token(handle,'person/chosen',sha),'unit-token')
            with self.assertRaises(ValueError):app.repo_token(handle,'person/chosen','a'*40)
            with self.assertRaises(ValueError):app.repo_token(handle,'another/repo',sha)
            with patch.object(app.time,'time',return_value=time.time()+2000):
                with self.assertRaises(ValueError):app.repo_token(handle,'person/chosen',sha)
            app.handle({'action':'github_app_revoke','handle':handle},api)
            with self.assertRaises(ValueError):app.repo_token(handle,'person/chosen',sha)
