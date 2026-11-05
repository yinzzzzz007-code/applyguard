"""Exact upstream reuse and fail-closed integration, not model-quality metrics."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.services import asu_resume as a
from backend.services.grounded_workflow import GroundingService
from backend.services.sag_grounding import GroundingUnavailable
from tests.test_grounding import AllSources,experience,CLAIM,TEXT
from tests.test_grounding_v2 import Model

class ASuReuseTests(unittest.TestCase):
    def test_unsolicited_translation_is_not_applied_even_if_judge_supports_it(self):
        model=Model(proposal='Alex为Atlas项目编写了Python接口测试。')
        final,checks,report=GroundingService(retriever=AllSources(),model=model).run(
            [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',jd='中文岗位说明',polish=True)
        result=report['results'][CLAIM['claim_id']]
        self.assertEqual(result['proposal_check']['relation'],'SUPPORTED')
        self.assertTrue(result['proposal_rejected']);self.assertEqual(final[0]['text'],TEXT)
        self.assertTrue(result['proposal_constraint_violations'])
    def test_chinese_english_and_uncertain_language_boundaries(self):
        for original,proposed,blocked in [('我负责项目中的接口测试','I wrote tests for the project',True),
            ('I wrote Python tests','I developed Python tests',False),('我负责项目中的SQL分析','我完成了项目中的SQL分析',False),
            ('SQL分析','SQL analysis',False)]:
            with self.subTest(original=original):self.assertEqual(bool(a.proposal_violations(original,proposed)),blocked)
    def test_six_original_files_match_upstream_blob_and_sha256(self):
        manifest=json.loads((a.DIRECTORY/'UPSTREAM.json').read_text(encoding='utf8'))
        self.assertEqual(len(manifest['files']),6)
        self.assertEqual(manifest['commit'],a.COMMIT)
        for name,info in manifest['files'].items():
            with self.subTest(file=name):
                raw=(a.DIRECTORY/name).read_bytes()
                self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),info['git_blob_sha1'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(),info['sha256'])
    def test_original_skill_and_ledger_reach_proposal_call(self):
        model=Model();_,_,report=GroundingService(retriever=AllSources(),model=model).run(
            [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        prompt=next(p for p in model.calls if p.startswith('Polish'))
        self.assertIn((a.DIRECTORY/a.SKILL).read_bytes().decode('utf8'),prompt)
        self.assertIn((a.DIRECTORY/a.LEDGER).read_bytes().decode('utf8'),prompt)
        self.assertEqual(report['polish_source']['commit'],a.COMMIT)
        self.assertEqual(report['polish_source']['role'],'rewrite_proposal_only')
    def test_business_reference_is_loaded_only_when_relevant(self):
        text,info=a.proposal_policy([CLAIM],{},'Backend testing')
        self.assertNotIn(a.BUSINESS,info['resources'])
        text,info=a.proposal_policy([CLAIM],{},'SQL 经营分析和成本测算')
        self.assertIn((a.DIRECTORY/a.BUSINESS).read_bytes().decode('utf8'),text)
        self.assertIn(a.BUSINESS,info['resources'])
    def test_unsupported_asu_proposal_does_not_override_guard_or_original(self):
        model=Model(proposal='Alex increased throughput by 900%.')
        final,checks,report=GroundingService(retriever=AllSources(),model=model).run(
            [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(final[0]['text'],TEXT)
        self.assertTrue(report['results'][CLAIM['claim_id']]['proposal_rejected'])
        self.assertEqual(report['results'][CLAIM['claim_id']]['proposal_check']['relation'],'CONTRADICTED')
    def test_absent_assets_preserve_original_and_review(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(a,'DIRECTORY',Path(folder)):
            final,checks,report=GroundingService(retriever=AllSources(),model=Model()).run(
                [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(final[0]['text'],TEXT);self.assertEqual(checks[0]['state'],'NEEDS_REVIEW')
        self.assertTrue(report['error'])
    def test_changed_upstream_asset_never_silently_runs(self):
        import shutil
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'asu';shutil.copytree(a.DIRECTORY,destination)
            (destination/a.SKILL).write_text('Altered instructions',encoding='utf8')
            with patch.object(a,'DIRECTORY',destination),self.assertRaises(GroundingUnavailable):
                a.proposal_policy([CLAIM],{},'Backend')
    def test_verification_alone_does_not_load_writing_skill(self):
        with patch.object(a,'proposal_policy',side_effect=AssertionError('Must not load')):
            _,checks,report=GroundingService(retriever=AllSources(),model=Model()).run(
                [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=False)
        self.assertEqual(checks[0]['state'],'VERIFIED');self.assertIsNone(report['polish_source'])

if __name__=='__main__':unittest.main()
