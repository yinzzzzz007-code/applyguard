import json
import threading
import time
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.services import polish_jobs as jobs
from backend.services.sag_grounding import evidence_snapshot
from backend.services.verification_audit import save_run


class PolishNavigationTests(unittest.TestCase):
    def test_leaving_rejoining_and_restarting_the_page_never_submits_twice(self):
        body = {'application_id':'app_A','candidate_id':'candidate_A','jd_text':'AI internship',
                'claims':[{'claim_id':'c1','text':'Wrote tests.'}],'local_only':False}
        entered, finish = threading.Event(), threading.Event()
        def polish(vault, request):
            entered.set()
            if not finish.wait(4):
                raise RuntimeError('Test worker did not finish')
            report = {'snapshot':evidence_snapshot([]),'results':{'c1':{
                'original_text':'Wrote tests.','proposed_text':'Authored tests.'}}}
            save_run(report,request['candidate_id'],polish=True)
            return {'grounding':report}
        with TemporaryDirectory() as root, patch.dict('os.environ',{'APPLYGUARD_LOCAL_DIR':root}), \
             patch.object(jobs,'load_grounding_experiences',return_value=[]), \
             patch.object(jobs,'polish_workflow',side_effect=polish) as calls:
            self.assertEqual(jobs.status(None,body)['state'],'idle')
            self.assertEqual(jobs.status(None,body,start=True)['state'],'running')
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(jobs.status(None,body,start=True)['state'],'running')
                self.assertEqual(jobs.status(None,body)['state'],'running')
            finally:
                finish.set()
            deadline=time.monotonic()+4
            while (result:=jobs.status(None,body))['state']=='running' and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertEqual(result['state'],'ready')
            self.assertEqual(calls.call_count,1)
            self.assertEqual(jobs.status(None,body,start=True)['run_id'],result['run_id'])
            self.assertEqual(jobs.status(None,{**body,'known_run':result['run_id']})['state'],'seen')
            for key,value in [('candidate_id','another'),('jd_text','different job'),
                              ('application_id','other'),('claims',[{'claim_id':'c1','text':'Edited.'}])]:
                self.assertEqual(jobs.status(None,{**body,key:value})['state'],'idle')
            with patch.object(jobs,'evidence_snapshot',return_value='replaced'):
                self.assertEqual(jobs.status(None,body)['state'],'stale')
            self.assertEqual(calls.call_count,1)

    def test_service_restart_reports_interruption_without_model_call(self):
        body={'candidate_id':'c','application_id':'a','jd_text':'a job',
              'claims':[{'claim_id':'x','text':'My project'}]}
        with TemporaryDirectory() as root, patch.dict('os.environ',{'APPLYGUARD_LOCAL_DIR':root}):
            jobs.save(jobs.job_file(body),{'state':'running'})
            self.assertEqual(jobs.status(None,body)['state'],'failed')
