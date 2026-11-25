import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.model_settings import current_settings, save_settings


class ModelSettingsTests(unittest.TestCase):
    def test_save_and_preserve_key_without_returning_it(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            root = Path(directory)
            body = {'base_url': 'https://example.com/v1', 'model': 'example-model', 'api_key': 'test-secret'}
            response = save_settings(body, root)
            self.assertTrue(response['key_configured'])
            self.assertNotIn('test-secret', str(response))
            save_settings({**body, 'api_key': '', 'model': 'second-model'}, root)
            self.assertEqual(os.getenv('APPLYGUARD_AI_API_KEY'), 'test-secret')
            self.assertIn('APPLYGUARD_AI_API_KEY=test-secret', (root / '.env').read_text(encoding='utf-8'))
            self.assertEqual(current_settings()['model'], 'second-model')

    def test_rejects_unencrypted_or_malformed_configuration(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            for url in ('http://example.com/v1', 'https://name:secret@example.com', 'https://example.com/?token=secret'):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    save_settings({'base_url': url, 'model': 'model', 'api_key': 'key'}, Path(directory))
            with self.assertRaises(ValueError):
                save_settings({'base_url': 'https://example.com', 'model': 'model\nBAD=1', 'api_key': 'key'}, Path(directory))


if __name__ == '__main__':
    unittest.main()
