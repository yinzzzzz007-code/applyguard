import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

from backend.services.harness_setup import find_harness, retrieval_patch, setup_info
from backend.services import agent_bridge


class HarnessSetupTests(unittest.TestCase):
    def test_profile_routes_gemini_and_does_not_embed_credentials(self):
        with patch.dict(os.environ, {'APPLYGUARD_AGENT_TOKEN':'private-test-token'}):
            text = retrieval_patch('gemini-3.1-flash-lite-preview', 'https://api.chatanywhere.tech/v1')
        self.assertNotIn('private-test-token', text)
        entries = json.loads(re.sub(r'!!js process\.env\.([A-Z_]+)', r'"ENV:\1"', text))
        by_id = {entry['id']:entry for entry in entries if 'id' in entry}
        self.assertEqual(by_id['agent-default-model']['config']['model'], 'gemini-3.1-flash-lite-preview')
        for name in ['tool-bash','tool-pwsh','tool-fs','tool-web','tool-subagent','session-telemetry-otel']:
            self.assertTrue(by_id[name]['disabled'])
        config = entries[-1]['insert'][0]['config']
        self.assertEqual(config['command'], sys.executable)
        self.assertTrue(Path(config['args'][0]).is_file())
        self.assertEqual(config['env']['APPLYGUARD_AGENT_TOKEN'], 'ENV:APPLYGUARD_AGENT_TOKEN')

    def test_discovery_uses_custom_install_and_reports_missing_override(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'dsh.cmd'
            executable.write_text('@echo off')
            with patch.dict(os.environ, {'APPLYGUARD_HARNESS_COMMAND':str(executable)}):
                self.assertEqual(find_harness(), str(executable.resolve()))
            with patch.dict(os.environ, {'APPLYGUARD_HARNESS_COMMAND':str(executable)+'-missing'}):
                self.assertIsNone(find_harness())

    def test_setup_is_read_only_and_contains_real_paths_not_model_key(self):
        before = len(agent_bridge.GRANTS)
        with patch.dict(os.environ, {'APPLYGUARD_AI_API_KEY':'private-model-key'}):
            info = agent_bridge.ui_call({'action':'setup'})
        self.assertEqual(len(agent_bridge.GRANTS), before)
        self.assertNotIn('private-model-key', json.dumps(info))
        self.assertTrue(Path(info['launcher_path']).is_file())
        self.assertTrue(info['connector_exists'])
        self.assertEqual(info['python'], setup_info()['python'])

    def test_cloud_profile_rejects_non_https(self):
        with self.assertRaises(ValueError):
            retrieval_patch('gemini-3.1-flash-lite-preview', 'http://example.test')
