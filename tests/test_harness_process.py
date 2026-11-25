import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from backend.services.harness_process import run_harness

class HarnessProcessTests(unittest.TestCase):
    def test_success_uses_the_same_bound_for_captured_output(self):
        process = Mock(returncode=0)
        process.communicate.return_value = ('result', 'diagnostic')
        with patch('backend.services.harness_process.subprocess.Popen', return_value=process):
            result = run_harness(['installed-harness'], env={}, cwd=Path('.'), timeout=30, capture_output=True)
        self.assertEqual((result.returncode, result.timed_out, result.stdout), (0, False, 'result'))
        process.communicate.assert_called_once()
        self.assertGreater(process.communicate.call_args.kwargs['timeout'],29)
        self.assertLessEqual(process.communicate.call_args.kwargs['timeout'],30)

    def test_timeout_stops_owned_tree_and_preserves_prior_output(self):
        process = Mock(returncode=None)
        process.communicate.side_effect = [subprocess.TimeoutExpired('harness', 15), ('partial', '')]
        with patch('backend.services.harness_process.subprocess.Popen', return_value=process), patch('backend.services.harness_process.stop_harness') as stop:
            result = run_harness(['installed-harness'], env={}, cwd=Path('.'), timeout=15)
        stop.assert_called_once_with(process)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.stdout, 'partial')

    def test_invalid_deadline_never_starts_process(self):
        with patch('backend.services.harness_process.subprocess.Popen') as start:
            with self.assertRaises(ValueError):run_harness(['unused'],env={},cwd=Path('.'),timeout=0)
            start.assert_not_called()
