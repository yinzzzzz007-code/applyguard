import unittest
from scripts.evaluate_ambiguity_live import run_status


class AmbiguityLiveStatusTests(unittest.TestCase):
    def test_repair_or_missing_model_output_is_not_a_pass(self):
        safe = {'label':'SAFE','outcome':'accepted_original_proposal'}
        held = {'label':'WRONG','outcome':'held_or_restored'}
        repair = {'label':'WRONG','outcome':'accepted_repair_needs_review'}
        self.assertEqual(run_status([safe,held],2),'PASS')
        self.assertEqual(run_status([safe,repair],2),'REQUIRES_REVIEW')
        self.assertEqual(run_status([safe],2),'INCOMPLETE')
        self.assertEqual(run_status([safe,{'label':'WRONG','outcome':'error'}],2),'INCOMPLETE')
        self.assertEqual(run_status([safe,{'label':'WRONG','outcome':'accepted_original_proposal'}],2),'FAIL')
        self.assertEqual(run_status([held,{'label':'SAFE','outcome':'held_or_restored'}],2),'FAIL')


if __name__ == '__main__':
    unittest.main()
