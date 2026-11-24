import json
import unittest
from unittest.mock import MagicMock, patch

from backend.services.model_client import HttpModelClient, ModelFailure, uses_json_object_structured


class ModelJSONCompatibilityTests(unittest.TestCase):
    def response(self, value):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]
        }).encode()
        return response

    def test_chatanywhere_gemini_uses_object_and_validates_schema(self):
        schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False}
        client = HttpModelClient(api_key='test', base_url='https://api.chatanywhere.tech/v1', model='gemini-3.1-flash-lite-preview')
        with patch('urllib.request.urlopen', return_value=self.response({'ok': True})) as transport:
            self.assertEqual(client.complete_structured('prompt', 'fixture', schema), {'ok': True})
        request = json.loads(transport.call_args.args[0].data)
        self.assertEqual(request['response_format'], {'type':'json_object'})
        self.assertIn(json.dumps(schema), request['messages'][0]['content'])
        with patch('urllib.request.urlopen', return_value=self.response({'ok': 'yes'})):
            with self.assertRaisesRegex(ModelFailure, 'required schema'):
                client.complete_structured('prompt', 'fixture', schema)

    def test_wording_review_uses_same_compatible_structured_transport(self):
        from backend.services.wording_review import sdk_step
        client = MagicMock(api_key='test', base_url='https://api.chatanywhere.tech/v1', model='gemini-3.1-flash-lite-preview')
        client.complete_structured.return_value = {'decision':'equivalent','reason':'fixture'}
        result = sdk_step(client,'judge','original','proposal',[])
        self.assertEqual(result['decision'],'equivalent')
        self.assertTrue(client.complete_structured.called)

    def test_other_providers_keep_schema_mode(self):
        self.assertFalse(uses_json_object_structured('https://other.example/v1','gemini-3.1-flash-lite-preview'))
        self.assertFalse(uses_json_object_structured('https://api.chatanywhere.tech/v1','another-model'))
        self.assertFalse(uses_json_object_structured('https://api.chatanywhere.tech.evil.test/v1','gemini-x'))
        self.assertTrue(uses_json_object_structured('https://api.deepseek.com/v1','deepseek-chat'))

if __name__ == '__main__':
    unittest.main()
