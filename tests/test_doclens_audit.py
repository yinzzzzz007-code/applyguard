import unittest
import importlib.util

if importlib.util.find_spec('numpy') and importlib.util.find_spec('tqdm'):
    from scripts.evaluate_doclens_audit import evaluate


@unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('tqdm'), 'optional DocLens audit dependencies')
class DocLensAuditTests(unittest.TestCase):
    def test_human_labels_and_unknowns_are_reported_separately(self):
        result = evaluate({
            'claim_precision': [{'supported': 1}, {'supported': 0}, {'supported': None}],
            'claim_recall': [{'supported': 1}, {'supported': 0}],
            'citations': [
                {'supported': 1, 'citations': ['a', 'b'], 'provenance': ['a']},
                {'supported': 0, 'citations': ['c'], 'provenance': []},
                {'supported': None},
            ],
        })
        self.assertEqual(result['claim_precision'], {'score': 0.5, 'assessed': 2, 'unknown': 1})
        self.assertEqual(result['claim_recall']['score'], 0.5)
        self.assertAlmostEqual(result['citations']['precision'], 1 / 3)
        self.assertEqual(result['citations']['recall'], 0.5)
        self.assertEqual(result['citations']['unknown'], 1)

    def test_missing_labels_do_not_become_a_score(self):
        result = evaluate({'claim_precision': [{'supported': None}]})
        self.assertIsNone(result['claim_precision']['score'])
        self.assertIsNone(result['claim_recall']['score'])
        self.assertIsNone(result['citations']['precision'])

    def test_invalid_labels_are_rejected(self):
        for label in (True, '1', 2, []):
            with self.subTest(label=label), self.assertRaises(ValueError):
                evaluate({'claim_precision': [{'supported': label}]})
        with self.assertRaises(ValueError):
            evaluate({'claim_precision': [{}]})


if __name__ == '__main__':
    unittest.main()
