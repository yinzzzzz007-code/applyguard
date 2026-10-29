"""Report fixture failures without losing the enclosing run's diagnostics."""
import io
import unittest
from scripts.run_test_report import RecordedResult


class TestReportTests(unittest.TestCase):
    def test_class_setup_error_is_a_fixture_record(self):
        class BrokenFixture(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError('synthetic fixture failure')
            def test_body(self):
                self.fail('must not run')
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=RecordedResult).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(BrokenFixture))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 0)
        self.assertEqual(len(result.records), 1)
        self.assertTrue(result.records[0]['fixture'])
        self.assertEqual(result.records[0]['status'], 'ERROR')

    def test_class_teardown_error_preserves_completed_method(self):
        class BrokenCleanup(unittest.TestCase):
            @classmethod
            def tearDownClass(cls):
                raise PermissionError('synthetic cleanup failure')
            def test_body(self):
                self.assertTrue(True)
        result = unittest.TextTestRunner(stream=io.StringIO(), resultclass=RecordedResult).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(BrokenCleanup))
        self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.testsRun, 1)
        self.assertEqual([r['status'] for r in result.records], ['PASS', 'ERROR'])
        self.assertTrue(result.records[1]['fixture'])
