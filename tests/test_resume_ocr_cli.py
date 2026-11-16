import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import evaluate_resume_ocr


class ResumeOcrCliTests(unittest.TestCase):
    def test_count_check_does_not_conflate_import_with_completeness(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / 'fictional.pdf'
            pdf.write_bytes(b'%PDF-fake')
            result = {'form': {'education': [{}], 'internships': [], 'projects': [], 'awards': []}}
            output = root / 'result.json'
            with patch.object(sys, 'argv', ['evaluate_resume_ocr.py', '--output', str(output),
                    '--expected-education', '2', str(pdf)]), patch.object(evaluate_resume_ocr, 'parse_resume_pdf', return_value=result):
                self.assertEqual(evaluate_resume_ocr.main(), 2)
            saved = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(saved['samples'][0]['status'], 'imported')
            self.assertFalse(saved['samples'][0]['education_count_matches'])


if __name__ == '__main__':
    unittest.main()
