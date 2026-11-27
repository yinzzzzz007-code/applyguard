import json
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend.services import agent_bridge
from backend.services.model_client import HttpModelClient
from backend.services.outbound_privacy import PrivacySession
from backend.services.sag_grounding import GroundingUnavailable, check_cloud_sensitive_inputs


class OutboundPrivacyTests(unittest.TestCase):
    def test_user_terms_are_session_scoped_and_restore_without_losing_context(self):
        session=PrivacySession()
        session.add_terms(['张三', '星河公司'])
        text='张三在星河公司参与项目，团队结果约提升 20%。'
        protected=session.protect(text)
        self.assertNotIn('张三',protected)
        self.assertNotIn('星河公司',protected)
        self.assertIn('团队结果约提升 20%',protected)
        self.assertEqual(session.restore(protected),text)
        self.assertNotEqual(protected,PrivacySession().protect(text))

    def test_custom_terms_cannot_corrupt_placeholders_or_protocol_identifiers(self):
        session=PrivacySession()
        session.add_terms(['AG', '张三'])
        item={'id':'AG123', 'version':'AG456', 'quote':'张三负责 AG 项目。'}
        protected=session.protect(item)
        self.assertEqual(protected['id'],'AG123')
        self.assertEqual(protected['version'],'AG456')
        self.assertEqual(session.protect(protected['quote']),protected['quote'])
        self.assertEqual(session.restore(protected['quote']),item['quote'])

    def test_contact_in_protocol_id_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'标识字段'):
            PrivacySession().protect({'id':'a@example.com','quote':'test'})

    def test_sag_blocks_recognised_identifiers_before_cloud(self):
        with self.assertRaises(GroundingUnavailable):
            check_cloud_sensitive_inputs([{'text': '负责项目'}], [{'text': '联系 13800138000'}], 'candidate')
        check_cloud_sensitive_inputs([{'text': '负责项目'}], [{'text': '约提高 20%'}], 'candidate')

    def test_pseudonyms_are_stable_and_preserve_metrics(self):
        session = PrivacySession()
        text = '电话 13800138000，邮箱 a@example.com，证件号 11010519491231002X，约提升 20%。'
        protected = session.protect(text)
        for value in ('13800138000', 'a@example.com', '11010519491231002X'):
            self.assertNotIn(value, protected)
        self.assertIn('约提升 20%', protected)
        self.assertEqual(protected, session.protect(text))
        self.assertEqual(session.restore(protected), text)

    def test_model_request_protects_and_restores(self):
        captured = {}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size):
                value = captured['payload']['messages'][1]['content']
                return json.dumps({'choices': [{'finish_reason': 'stop',
                    'message': {'content': json.dumps({'text': value})}}]}).encode()

        def request(req, timeout):
            captured['payload'] = json.loads(req.data)
            return Response()

        client = HttpModelClient(api_key='test', base_url='https://example.test')
        with patch('urllib.request.urlopen', side_effect=request):
            result = client.complete_json('test', '联系 13800138000，约提升 20%')
        sent = captured['payload']['messages'][1]['content']
        self.assertNotIn('13800138000', sent)
        self.assertEqual(result['text'], '联系 13800138000，约提升 20%')

    def test_model_failure_blocks_external_request(self):
        client=HttpModelClient(api_key='test',base_url='https://example.test')
        with patch('backend.services.privacy_ner.status',return_value={'state':'available','notice':'test'}), \
             patch('backend.services.privacy_ner.detect',side_effect=ValueError('bad model')), \
             patch('urllib.request.urlopen') as transport:
            with self.assertRaisesRegex(ValueError,'未发送'):
                client.complete_json('instructions','姓名 张三')
            transport.assert_not_called()

    def test_agent_sees_pseudonyms_but_ui_retains_exact_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quote = 'Atlas 联系 13800138000，邮箱 a@example.com，约提升 20%。'
            (root / 'report.md').write_text(quote, encoding='utf8')
            c = agent_bridge.create({'mode': 'local', 'roots': [str(root)], 'repos': [],
                'purpose': 'contribution', 'disclosure': 'cloud_allowed', 'task': '查找 Atlas 联系 13800138000'})
            try:
                def call(action, **arguments):
                    return agent_bridge.agent_call({'id': c['id'], 'action': action,
                        'arguments': arguments}, c['token'])
                task = call('task')
                self.assertNotIn('13800138000', task['task'])
                candidate = call('search', query='Atlas')['cards'][0]
                self.assertNotIn('13800138000', candidate['quote'])
                self.assertNotIn('a@example.com', candidate['quote'])
                self.assertIn('约提升 20%', candidate['quote'])
                call('submit', card_id=candidate['id'], quote=candidate['quote'],
                     version=candidate['source']['version'], interpretation='待确认', missing=[])
                ui = agent_bridge.ui_call({**c, 'action': 'status'})
                self.assertEqual(ui['cards'][0]['quote'], quote)
            finally:
                agent_bridge.GRANTS.pop(c['id'], None)

    def test_preview_requires_ui_selection_and_rejects_undisclosed_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'first.txt').write_text('Atlas 张三负责测试，约提升 20%。',encoding='utf8')
            (root/'second.txt').write_text('Atlas 张三参与分析。',encoding='utf8')
            c=agent_bridge.create({'mode':'local','roots':[str(root)],'repos':[],
                'purpose':'contribution','disclosure':'cloud_allowed','task':'查找张三的 Atlas 项目',
                'plan':'查找个人职责','review_disclosures':True,'private_terms':['张三']})
            def call(action,**arguments):
                return agent_bridge.agent_call({'id':c['id'],'action':action,'arguments':arguments},c['token'])
            def ui(action,**arguments):
                return agent_bridge.ui_call({**c,'action':action,**arguments})
            try:
                self.assertNotIn('张三',call('task')['task'])
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future=pool.submit(call,'search',query='Atlas')
                    for _ in range(100):
                        status=ui('status')
                        if status['disclosure_preview']:break
                        time.sleep(.01)
                    preview=status['disclosure_preview']
                    self.assertIsNotNone(preview)
                    self.assertFalse(future.done())
                    self.assertEqual(len(preview['cards']),2)
                    self.assertNotIn('张三',json.dumps(preview,ensure_ascii=False))
                    one,other=preview['cards']
                    with self.assertRaises(ValueError):
                        ui('review_disclosure',preview_id=preview['id'],card_ids=['bad-id'])
                    ui('review_disclosure',preview_id=preview['id'],card_ids=[one['id']])
                    result=future.result(timeout=5)
                    self.assertEqual([card['id'] for card in result['cards']],[one['id']])
                    with self.assertRaisesRegex(ValueError,'尚未经'):
                        call('submit',card_id=other['id'],quote=other['quote'],version=other['source']['version'])
                    with self.assertRaisesRegex(ValueError,'尚未经'):
                        ui('suggest_experience',card_id=other['id'],job='机器学习岗位')
                    submitted=call('submit',card_id=one['id'],quote=one['quote'],version=one['source']['version'])
                    self.assertEqual(submitted['state'],'NEEDS_REVIEW')
            finally:
                agent_bridge.GRANTS.pop(c['id'],None)

    def test_revoke_wakes_pending_preview_without_disclosure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'report.txt').write_text('Atlas project test',encoding='utf8')
            c=agent_bridge.create({'mode':'local','roots':[str(root)],'repos':[],
                'purpose':'contribution','disclosure':'cloud_allowed','task':'Find Atlas project',
                'review_disclosures':True})
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future=pool.submit(agent_bridge.agent_call,{'id':c['id'],'action':'search',
                        'arguments':{'query':'Atlas'}},c['token'])
                    for _ in range(100):
                        if agent_bridge.ui_call({**c,'action':'status'})['disclosure_preview']:break
                        time.sleep(.01)
                    agent_bridge.ui_call({**c,'action':'revoke'})
                    with self.assertRaises(ValueError):future.result(timeout=5)
            finally:
                agent_bridge.GRANTS.pop(c['id'],None)

    def test_review_timeout_does_not_send_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'report.txt').write_text('Atlas project test',encoding='utf8')
            c=agent_bridge.create({'mode':'local','roots':[directory],'repos':[],
                'purpose':'contribution','disclosure':'cloud_allowed','task':'Find Atlas project',
                'review_disclosures':True})
            try:
                with patch.object(agent_bridge,'DISCLOSURE_REVIEW_SECONDS',0):
                    with self.assertRaisesRegex(ValueError,'超时'):
                        agent_bridge.agent_call({'id':c['id'],'action':'search',
                            'arguments':{'query':'Atlas'}},c['token'])
                status=agent_bridge.ui_call({**c,'action':'status'})
                self.assertIsNone(status['disclosure_preview'])
                self.assertFalse(status['cards'][0]['approved_for_agent'])
            finally:
                agent_bridge.GRANTS.pop(c['id'],None)

    def test_parallel_searches_serialize_previews_without_bypassing_user_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'a.txt').write_text('Alpha 项目证据。',encoding='utf8')
            (root/'b.txt').write_text('Beta 项目证据。',encoding='utf8')
            c=agent_bridge.create({'mode':'local','roots':[str(root)],'repos':[],
                'purpose':'contribution','disclosure':'cloud_allowed','task':'查找项目证据',
                'review_disclosures':True,'workers':3})
            def run(query):
                return agent_bridge.agent_call({'id':c['id'],'action':'search',
                    'arguments':{'query':query}},c['token'])
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures=[pool.submit(run,'Alpha'),pool.submit(run,'Beta')]
                    seen=set()
                    for _ in range(300):
                        preview=agent_bridge.ui_call({**c,'action':'status'})['disclosure_preview']
                        if preview and preview['id'] not in seen:
                            seen.add(preview['id'])
                            agent_bridge.ui_call({**c,'action':'review_disclosure','preview_id':preview['id'],
                                'card_ids':[card['id'] for card in preview['cards']]})
                        if len(seen)==2:break
                        time.sleep(.01)
                    self.assertEqual(len(seen),2)
                    self.assertTrue(all(f.result(timeout=5)['cards'] for f in futures))
            finally:
                agent_bridge.ui_call({**c,'action':'revoke'})
                agent_bridge.GRANTS.pop(c['id'],None)

    def test_experience_suggestion_keeps_custom_terms_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'report.txt').write_text('Atlas 张三参与测试。',encoding='utf8')
            c=agent_bridge.create({'mode':'local','roots':[str(root)],'repos':[],
                'purpose':'contribution','disclosure':'cloud_allowed','task':'查找 Atlas 项目',
                'private_terms':['张三']})
            try:
                found=agent_bridge.agent_call({'id':c['id'],'action':'search',
                    'arguments':{'query':'Atlas'}},c['token'])['cards'][0]
                seen=[]
                def complete(_instruction, payload):
                    seen.append(payload)
                    quote=json.loads(payload)['quote']
                    return {'title':'Atlas','description':quote,'reason':'待确认'}
                with patch('backend.services.model_client.HttpModelClient') as client:
                    client.return_value.complete_json.side_effect=complete
                    result=agent_bridge.ui_call({**c,'action':'suggest_experience','card_id':found['id'],'job':'测试岗位'})
                self.assertNotIn('张三',seen[0])
                self.assertIn('张三',result['description'])
            finally:
                agent_bridge.GRANTS.pop(c['id'],None)


if __name__ == '__main__':
    unittest.main()
