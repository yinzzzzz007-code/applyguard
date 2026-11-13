import unittest

from scripts.evaluate_refchecker_pilot import aggregate_case_labels, evaluate
from backend.services.refchecker_review import review_refchecker


class FakeModel:
    def __init__(self, labels):
        self.labels = iter(labels)

    def complete_json(self, system, data):
        label = next(self.labels)
        if isinstance(label, Exception):
            raise label
        return {'label': label}


class RefCheckerPilotTests(unittest.TestCase):
    def test_three_labels_are_compared_without_persisting_input(self):
        cases = [{'id': str(i), 'reference': 'private source', 'claim': 'private claim', 'expected': label}
                 for i, label in enumerate(('Entailment', 'Neutral', 'Contradiction'))]
        result = evaluate(FakeModel(['Entailment', 'Neutral', 'Contradiction']), cases)
        self.assertTrue(result['complete'])
        self.assertEqual(result['correct'], 3)
        self.assertNotIn('private', str(result))

    def test_bad_output_and_errors_abstain(self):
        cases = [{'id': str(i), 'reference': 'r', 'claim': 'c', 'expected': 'Entailment'} for i in range(2)]
        result = evaluate(FakeModel(['unexpected', RuntimeError('provider')]), cases)
        self.assertFalse(result['complete'])
        self.assertEqual(result['assessed'], 0)

    def test_strict_aggregation_is_for_one_claim_and_unknown_fails_closed(self):
        self.assertEqual(aggregate_case_labels(['Entailment', 'Neutral']), 'Neutral')
        self.assertEqual(aggregate_case_labels(['Entailment', 'Contradiction']), 'Contradiction')
        self.assertEqual(aggregate_case_labels(['Entailment', 'Abstain']), 'Abstain')
        self.assertEqual(aggregate_case_labels([]), 'Abstain')

    def test_invalid_fixture_rejected_before_model_calls(self):
        with self.assertRaises(ValueError):
            evaluate(FakeModel([]), [{'id': 'a', 'reference': '', 'claim': 'c', 'expected': 'Entailment'}])

    def test_veto_checks_every_supported_atom_and_abstains_on_error(self):
        atom = {'text': 'A tested the API', 'relation': 'SUPPORTED', 'citations': [{'quote': 'A tested the API'}]}
        check = {'relation': 'SUPPORTED', 'complete': True, 'atoms': [atom, atom]}
        self.assertEqual(review_refchecker(FakeModel(['Entailment', 'Neutral']), 'full claim', check)['relation'], 'Neutral')
        self.assertEqual(review_refchecker(FakeModel(['Entailment', RuntimeError()]), 'full claim', check)['relation'], 'Abstain')
        self.assertEqual(review_refchecker(FakeModel([]), 'full claim', None)['relation'], 'Abstain')
        self.assertEqual(review_refchecker(FakeModel([]), 'full claim', {**check, 'atoms': [{**atom, 'citations': []}]})['relation'], 'Abstain')


if __name__ == '__main__':
    unittest.main()
