import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.services.verification_audit import save_failure


class VerificationFailureTests(unittest.TestCase):
    def test_local_failure_keeps_cause_and_redacts_model_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
                'APPLYGUARD_LOCAL_DIR':folder, 'APPLYGUARD_AI_API_KEY':'synthetic-secret'}):
            try:
                try:
                    raise OSError('synthetic-secret: transport unavailable')
                except OSError as cause:
                    raise ValueError('retrieval failed') from cause
            except ValueError as error:
                identifier = save_failure('retrieval', error)
            text = (Path(folder) / 'verification-failures' / (identifier + '.json')).read_text('utf-8')
            self.assertNotIn('synthetic-secret',text)
            self.assertIn('[REDACTED]',text)
            self.assertIn('OSError',text)
            self.assertEqual(json.loads(text)['stage'],'retrieval')
