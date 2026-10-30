import unittest
from backend.services.structured_verifier import aligned_quote,citations

class QuoteAlignmentTests(unittest.TestCase):
    def test_returns_exact_original_substring_not_rewritten_quote(self):
        source='记录：许宁负责测试，尚未上线。尾注。'
        quote,changed=aligned_quote(source,'许宁负责测试,尚未上线.')
        self.assertTrue(changed);self.assertEqual(quote,'许宁负责测试，尚未上线。');self.assertIn(quote,source)
    def test_negation_units_digits_and_ellipsis_are_not_repaired(self):
        for source,quote in [('尚未上线。','已经上线。'),('提高4个百分点。','提高4%。'),
            ('准确率80%。','准确率84%。'),('did not deploy','did ... deploy'),('比例0。5','比例0.5'),
            ('A，B。 A,B。','A,B.')]:
            with self.subTest(source=source):self.assertEqual(aligned_quote(source,quote),(None,False))
    def test_alignment_keeps_candidate_scope_and_positions(self):
        text='报告：项目尚未上线。';source={'source_id':'s','text':text,'candidate_id':'p','experience_id':'x','evidence_id':'e','sha256':'a'*64,'text_offset':20}
        verdict={'relation':'SUPPORTED','reason':'fixture','citations':[{'source_id':'s','quote':'项目尚未上线.'}]}
        result=citations(verdict,[source],{'candidate_id':'p','experience_id':'x'})
        self.assertEqual(result['relation'],'SUPPORTED');cite=result['citations'][0]
        self.assertEqual(cite['quote'],text[cite['start']-20:cite['end']-20]);self.assertTrue(cite['quote_punctuation_aligned'])
        self.assertEqual(citations(verdict,[source],{'candidate_id':'other','experience_id':'x'})['relation'],'INSUFFICIENT')

if __name__=='__main__':unittest.main()
