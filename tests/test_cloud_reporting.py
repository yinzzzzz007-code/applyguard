import unittest
from scripts.summarize_cloud_features import outcome

class CloudReportingTests(unittest.TestCase):
    def test_model_parse_fallback_is_not_a_success(self):
        self.assertEqual(outcome('ai_resume_parse', {'http':200, 'extractor':'规则抽取（模型不可用）'}), 'INCOMPLETE')
        self.assertEqual(outcome('ai_resume_parse', {'http':200, 'extractor':'模型抽取'}), 'COMPLETED')
        self.assertEqual(outcome('ai_resume_parse', {'http':500, 'extractor':'模型抽取'}), 'INCOMPLETE')

    def test_polish_all_conflicted_is_complete_only_if_evaluator_passed(self):
        row = {'http':200,'proposals':0,'expected_proposals':0,'conflicts_skipped':2,'passed':True}
        self.assertEqual(outcome('ai_resume_polish',row),'COMPLETED')
        self.assertEqual(outcome('ai_resume_polish',{**row,'passed':False}),'INCOMPLETE')
        self.assertEqual(outcome('ai_resume_polish',{**row,'conflicts_skipped':0}),'INCOMPLETE')

    def test_polish_with_unverified_error_is_not_a_success(self):
        row = {'http':200, 'proposals':3, 'error':'原文原子核验未完成'}
        self.assertEqual(outcome('ai_resume_polish', row), 'INCOMPLETE')

if __name__ == '__main__':
    unittest.main()
