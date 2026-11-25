import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services import agent_bridge as bridge
from backend.services.harness_process import HarnessResult


class HarnessAutostartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'atlas.md').write_text('Atlas project used Python for testing.', encoding='utf-8')
        self.connection = bridge.create({'mode':'local','roots':[str(self.root)],'task':'Find Atlas project evidence',
            'repos':[],'purpose':'contribution','disclosure':'cloud_allowed'})
        self.setup = {'harness_command':'dsh','mcp_installed':True,'connector_exists':True,
                      'model':'test-model','base_url':'https://example.com/v1'}

    def tearDown(self):
        bridge.GRANTS.clear()
        self.temp.cleanup()

    def test_one_click_starts_and_returns_scoped_candidate(self):
        finished=threading.Event()
        def fake_run(command, *, env, cwd, timeout, capture_output, should_cancel):
            self.assertNotIn('APPLYGUARD_AI_API_KEY', env)
            token=env['APPLYGUARD_AGENT_TOKEN']
            def call(action, args=None):
                return bridge.agent_call({'id':self.connection['id'],'action':action,'arguments':args or {}},token)
            call('task')
            card=call('search',{'query':'Atlas'})['cards'][0]
            call('submit',{'card_id':card['id'],'quote':card['quote'],'version':card['source']['version']})
            finished.set()
            return HarnessResult(0,False)
        with patch.dict(os.environ,{'APPLYGUARD_AI_API_KEY':'test-only','APPLYGUARD_LOCAL_DIR':str(self.root)}), \
             patch('backend.services.harness_autostart.setup_info',return_value=self.setup), \
             patch('backend.services.harness_autostart.retrieval_patch',return_value='test'), \
             patch('backend.services.harness_autostart.run_harness',side_effect=fake_run):
            result=bridge.ui_call({**self.connection,'action':'start_harness'},server_port=8766)
            self.assertTrue(result['started'])
            self.assertTrue(finished.wait(5))
            for _ in range(100):
                status=bridge.ui_call({**self.connection,'action':'status'})
                if status['progress']['run_state']=='finished':break
                time.sleep(.01)
            self.assertTrue(status['connected'])
            self.assertEqual(status['progress']['submitted'],1)
            self.assertEqual(status['cards'][0]['state'],'NEEDS_REVIEW')

    def test_cloud_disclosure_and_key_required(self):
        g=bridge.GRANTS[self.connection['id']]
        g['disclosure']='isolated_local'
        with self.assertRaisesRegex(ValueError,'禁止'):
            bridge.ui_call({**self.connection,'action':'start_harness'},server_port=8766)
        g['disclosure']='cloud_allowed'
        with patch.dict(os.environ,{'APPLYGUARD_AI_API_KEY':''}), patch('backend.services.harness_autostart.setup_info',return_value=self.setup):
            with self.assertRaisesRegex(ValueError,'模型设置'):
                bridge.ui_call({**self.connection,'action':'start_harness'},server_port=8766)

    def test_second_search_reuses_scope_finds_new_project_and_summarizes(self):
        (self.root/'routekv.md').write_text('RouteKV project measured KV memory and inference latency.',encoding='utf8')
        finished=threading.Event()
        def fake_run(command,*,env,**kwargs):
            def call(action,args=None):
                return bridge.agent_call({'id':self.connection['id'],'action':action,'arguments':args or {}},env['APPLYGUARD_AGENT_TOKEN'])
            task=call('task')
            self.assertIn('KV memory',str(task))
            card=call('search',{'query':'RouteKV'})['cards'][0]
            call('submit',{'card_id':card['id'],'quote':card['quote'],'version':card['source']['version']})
            finished.set()
            return HarnessResult(0,False)
        with patch.dict(os.environ,{'APPLYGUARD_AI_API_KEY':'test-only','APPLYGUARD_LOCAL_DIR':str(self.root)}), \
             patch('backend.services.harness_autostart.setup_info',return_value=self.setup), \
             patch('backend.services.harness_autostart.retrieval_patch',return_value='test'), \
             patch('backend.services.harness_autostart.run_harness',side_effect=fake_run), \
             patch('backend.services.model_client.HttpModelClient') as model:
            bridge.ui_call({**self.connection,'action':'discover_experiences','job':'Optimize KV memory and inference latency','known_projects':['Atlas']},server_port=8766)
            self.assertTrue(finished.wait(5))
            card=next(iter(bridge.GRANTS[self.connection['id']]['cards'].values()))
            model.return_value.complete_json.return_value={'title':'RouteKV','description':'Measured KV memory and inference latency; personal contribution awaits confirmation.','reason':'岗位涉及推理性能。'}
            value=bridge.ui_call({**self.connection,'action':'suggest_experience','card_id':card['id'],'job':'KV memory optimization'})
            self.assertEqual(value['title'],'RouteKV')
            self.assertEqual(card['state'],'NEEDS_REVIEW')
            self.assertEqual(bridge.GRANTS[self.connection['id']]['roots'],[str(self.root.resolve())])


if __name__ == '__main__':
    unittest.main()
