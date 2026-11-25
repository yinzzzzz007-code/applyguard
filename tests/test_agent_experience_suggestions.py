import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services import agent_bridge
from backend.services.model_client import ModelFailure


class AgentExperienceSuggestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'project.md'
        self.path.write_text('团队使用 Python 测试模型。', encoding='utf-8')
        connection = agent_bridge.create({'mode': 'local', 'roots': [str(self.root)],
            'repos': [], 'task': '查找项目经历', 'purpose': 'contribution', 'disclosure': 'cloud_allowed'})
        self.connection = connection
        self.grant = agent_bridge.GRANTS[connection['id']]
        self.grant['cards']['item'] = {'state': 'NEEDS_REVIEW', 'purpose': 'contribution',
            'source': {'kind': 'local', 'root': str(self.root), 'path': self.path.name,
                       'version': hashlib.sha256(self.path.read_bytes()).hexdigest()},
            'quote': self.path.read_text(encoding='utf-8'), 'experience': '', 'interpretation': ''}
        self.body = {'action': 'suggest_experience', 'id': connection['id'],
                     'ui_token': connection['ui_token'], 'card_id': 'item', 'job': 'Python 模型评测'}
        self.addCleanup(agent_bridge.GRANTS.pop, connection['id'], None)

    @patch('backend.services.model_client.HttpModelClient')
    def test_suggestion_does_not_change_card(self, model):
        model.return_value.complete_json.return_value = {'title': '模型测试', 'description': '团队进行模型测试。', 'reason': '与岗位相关。'}
        result = agent_bridge.ui_call(self.body)
        self.assertEqual(result['title'], '模型测试')
        self.assertEqual(self.grant['cards']['item']['state'], 'NEEDS_REVIEW')
        self.assertIn('尚未完成事实核验', result['notice'])

    @patch('backend.services.model_client.HttpModelClient')
    def test_private_model_choice_never_calls_cloud(self, model):
        self.grant['disclosure'] = 'isolated_local'
        with self.assertRaisesRegex(ValueError, '禁止'):
            agent_bridge.ui_call(self.body)
        model.assert_not_called()

    @patch('backend.services.model_client.HttpModelClient')
    def test_source_changed_during_generation_rejects_result(self, model):
        def change(*_args):
            self.path.write_text('材料已变更', encoding='utf-8')
            return {'title': '项目', 'description': '描述', 'reason': '原因'}
        model.return_value.complete_json.side_effect = change
        with self.assertRaisesRegex(ValueError, '原文已变化'):
            agent_bridge.ui_call(self.body)

    @patch('backend.services.model_client.HttpModelClient')
    def test_missing_key_is_actionable(self, model):
        model.return_value.complete_json.side_effect = ModelFailure('missing', code='MODEL_KEY_MISSING')
        with self.assertRaisesRegex(ValueError, '尚未配置云端模型密钥'):
            agent_bridge.ui_call(self.body)

    @patch('backend.services.model_client.HttpModelClient')
    def test_incomplete_model_response_rejected(self, model):
        model.return_value.complete_json.return_value = {'title': '项目'}
        with self.assertRaisesRegex(ValueError, '不完整'):
            agent_bridge.ui_call(self.body)


if __name__ == '__main__':
    unittest.main()
