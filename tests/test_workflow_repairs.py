"""Regressions for the five reproduced integration and security defects (no model fees)."""
from __future__ import annotations
import base64
import copy
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from backend import app
from backend.services import evidence_workspace as ew
from backend.services.reverification import reverify_workflow
from backend.services.resume_parser import parse_resume_pdf

ROOT=Path(__file__).resolve().parents[1]
TEXT='Built a Python HTTP API and added automated tests for core routes.'
JD='Backend Developer requires Python HTTP API and automated testing.'

class EvidenceRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'APPLYGUARD_EVIDENCE_DIR':self.tmp.name,'APPLYGUARD_LOCAL_DIR':self.tmp.name})
        self.env.start()
        self.ws=ew.create_workspace('Fictional regression')
        self.file=self.upload(TEXT)
        self.eid=self.file['evidence_id']
        ew.review_evidence(self.eid,{'normalized_fields':{},'review_state':'REVIEWED'})
        self.form={'candidateId':'cand_demo_001','projects':[{'id':'api_project','title':'Backend Developer','organization':'Fictional Lab','start':'2025-01','end':'2025-06','description':TEXT}],'internships':[],'awards':[]}
    def tearDown(self): self.env.stop(); self.tmp.cleanup()
    def upload(self,text,name='proof.md'):
        return ew.import_files(self.ws['workspace_id'],[{'relative_path':name,'content_base64':base64.b64encode(text.encode()).decode()}])['files'][0]
    def request(self):
        return {'candidate_id':'cand_demo_001','jd_text':JD,'parse_mode':'offline','resume_draft':self.form}
    def link(self,state='ACTIVE',target='api_project'):
        return ew.create_link({'target_type':'project','target_id':target,'evidence_id':self.eid,'link_state':state})
    def test_positive_quote_and_unknown_claim_do_not_share_status(self):
        self.assertTrue(ew.check_claim_support(TEXT,self.eid)['supported'])
        for text in ('Built a CUDA cluster with 999 nodes.','Won an international award and increased revenue by 900%.',''):
            with self.subTest(text=text):
                result=ew.check_claim_support(text,self.eid)
                self.assertFalse(result['supported']);self.assertNotEqual(result['status'],'VERIFIED')
    def test_negated_substring_and_award_extra_facts_are_not_supported(self):
        f=self.upload('Never '+TEXT.lower(), 'negative.md')
        ew.review_evidence(f['evidence_id'],{'normalized_fields':{},'review_state':'REVIEWED'})
        self.assertFalse(ew.check_claim_support(TEXT,f['evidence_id'])['supported'])
        f=self.upload('奖项：程序设计竞赛\n等级：二等奖','award.md')
        ew.review_evidence(f['evidence_id'],{'normalized_fields':{'award_name':'程序设计竞赛','grade':'二等奖'},'review_state':'REVIEWED'})
        self.assertTrue(ew.check_claim_support('获得程序设计竞赛二等奖',f['evidence_id'])['supported'])
        self.assertFalse(ew.check_claim_support('获得其他比赛二等奖',f['evidence_id'])['supported'])
        self.assertFalse(ew.check_claim_support('获得程序设计竞赛二等奖，营收增长900%',f['evidence_id'])['supported'])
    def test_decimal_sign_and_denominator_are_not_formatting(self):
        f=self.upload('Result: -1.0% change, ratio 1/2.', 'numeric.md')
        ew.review_evidence(f['evidence_id'],{'normalized_fields':{},'review_state':'REVIEWED'})
        for text in ('Result: 10% change, ratio 12.', 'Result: 1.0% change, ratio 1/2.'):
            self.assertFalse(ew.check_claim_support(text,f['evidence_id'])['supported'])

    def test_rejected_and_target_scoped_links(self):
        self.link('REJECTED')
        self.assertFalse(ew.check_claim_support(TEXT,self.eid)['supported'])
        self.link('ACTIVE','other_project')
        self.assertFalse(ew.check_claim_support(TEXT,self.eid,target_type='project',target_id='api_project')['supported'])
        self.assertTrue(ew.check_claim_support(TEXT,self.eid,target_type='project',target_id='other_project')['supported'])
    def test_foreign_span_cannot_be_assigned(self):
        other=self.upload('Foreign document text','other.md')
        span=ew.get_evidence(other['evidence_id'])['spans'][0]['span_id']
        with self.assertRaises(ValueError):ew.review_evidence(self.eid,{'normalized_fields':{},'span_ids':[span]})
    def test_tampered_original_cannot_pass(self):
        with ew._db() as conn:row=ew._file_row(conn,self.file['file_id'])
        (ew._workspace_dir(row['workspace_id'])/row['storage_name']).write_text('tampered')
        self.assertEqual(ew.check_claim_support(TEXT,self.eid)['status'],'STALE')
    def test_import_review_link_workflow_and_revocation(self):
        before=app.build_mock_workflow(self.request())
        self.assertEqual(before['resume_claims'],[])
        self.link()
        after=app.build_mock_workflow(self.request())
        self.assertEqual(len(after['resume_claims']),1)
        self.assertEqual(after['claim_verification'][0]['state'],'VERIFIED')
        field=after['ats_form_mapping']['fields'][0]
        self.assertEqual(field['source_claim_ids'],['claim_api_project'])
        self.assertEqual(field['value'],TEXT)
        self.assertEqual(field['action'],'SAFE_TO_FILL')
        self.assertNotEqual(after['workflow_status'],'BLOCKED')
        self.assertEqual(len(after['step_trace']),9)
        self.link('REJECTED')
        revoked=app.build_mock_workflow(self.request())
        self.assertEqual(revoked['resume_claims'],[])
        check=reverify_workflow(app.CAREER_VAULT_PATH,{**self.request(),'claims':[{'claim_id':'claim_api_project','text':TEXT}]})
        self.assertEqual(check['claim_verification'][0]['state'],'BLOCKED')
        self.assertEqual(check['risk_result']['action'],'BLOCKED')
        self.assertNotIn('CONFIRM',check['human_confirmation']['allowed_actions'])
    def test_changed_file_and_deleted_file_invalidate_workflow(self):
        self.link()
        self.upload(TEXT+' Changed version.')
        self.assertEqual(ew.check_claim_support(TEXT,self.eid)['status'],'STALE')
        self.assertEqual(app.build_mock_workflow(self.request())['resume_claims'],[])
        ew.delete_files([self.file['file_id']])
        self.assertEqual(app.build_mock_workflow(self.request())['resume_claims'],[])
    def test_unreviewed_material_and_unrelated_link_cannot_promote(self):
        ew.review_evidence(self.eid,{'normalized_fields':{},'review_state':'UNREVIEWED'})
        with self.assertRaises(ValueError):self.link()
        self.assertEqual(app.build_mock_workflow(self.request())['resume_claims'],[])
    def test_reverification_does_not_trust_client_state_or_refs(self):
        req={**self.request(),'claims':[{'claim_id':'claim_manual_unknown','text':'Invented 900% revenue result','evidence_ids':[self.eid],'state':'VERIFIED'}]}
        result=reverify_workflow(app.CAREER_VAULT_PATH,req)
        self.assertEqual(result['claim_verification'][0]['state'],'BLOCKED')
        self.assertTrue(result['claim_verification'][0]['unsupported_fragments'])
        self.assertEqual(result['ats_form_mapping']['fields'][0]['action'],'BLOCKED')
        self.link()
        req['claims']=[{'claim_id':'claim_api_project','text':TEXT}]
        self.assertEqual(reverify_workflow(app.CAREER_VAULT_PATH,req)['claim_verification'][0]['state'],'VERIFIED')
        req['claims'][0]['text']='Owned the entire production platform and used CUDA.'
        self.assertEqual(reverify_workflow(app.CAREER_VAULT_PATH,req)['claim_verification'][0]['state'],'BLOCKED')
    def test_candidate_mismatch_and_duplicate_claims_stop(self):
        req=self.request();req['candidate_id']='cand_someone_else'
        with self.assertRaises(app.WorkflowStopped):app.build_mock_workflow(req)
        req=self.request();req['claims']=[{'claim_id':'claim_api_project','text':TEXT}]*2
        with self.assertRaises(ValueError):reverify_workflow(app.CAREER_VAULT_PATH,req)
    def test_empty_draft_does_not_fall_back_to_seed(self):
        req=self.request();req['resume_draft']={'candidateId':'cand_demo_001','projects':[]}
        with self.assertRaises(app.WorkflowStopped):app.build_mock_workflow(req)


class StaticRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.front=root/'frontend';(self.front/'dist/assets').mkdir(parents=True)
        (self.front/'dist/assets/good.js').write_text('ok')
        (root/'private.txt').write_text('fictional sentinel')
        (self.front/'dist/assets/escape.txt').symlink_to(root/'private.txt')
        self.scope=patch.object(app,'FRONTEND_DIR',self.front);self.scope.start()
        self.server=app.create_server('127.0.0.1',0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.scope.stop();self.tmp.cleanup()
    def get(self,path,origin=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=4)
        conn.request('GET',path,headers={'Origin':origin} if origin else {})
        res=conn.getresponse();body=res.read();headers=dict(res.getheaders());conn.close()
        return res.status,body,headers
    def test_plain_encoded_and_symlink_traversal_denied(self):
        self.assertEqual(self.get('/assets/good.js')[:2],(200,b'ok'))
        for path in ('/assets/../../../private.txt','/assets/%2e%2e/%2e%2e/%2e%2e/private.txt','/assets/escape.txt'):
            with self.subTest(path=path):self.assertEqual(self.get(path)[0],404)
    def test_cors_does_not_allow_credentials_disguised_as_loopback(self):
        self.assertNotIn('Access-Control-Allow-Origin',self.get('/health','http://localhost:8000@evil.invalid')[2])
        self.assertEqual(self.get('/health','http://127.0.0.1:5173')[2]['Access-Control-Allow-Origin'],'http://127.0.0.1:5173')
    def test_reverification_http_envelope_and_stopping_point(self):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=4)
        body={'candidate_id':'cand_demo_001','jd_text':JD,'claims':[{'claim_id':'claim_manual_unknown','text':'Used CUDA to increase revenue by 900%.','state':'VERIFIED'}]}
        conn.request('POST','/api/v1/workflow/reverify',json.dumps(body),{'Content-Type':'application/json'})
        response=conn.getresponse();result=json.loads(response.read());conn.close()
        self.assertEqual(response.status,200)
        self.assertEqual(result['claim_verification'][0]['state'],'BLOCKED')
        self.assertEqual(result['risk_result']['action'],'BLOCKED')
        self.assertEqual(len(result['step_trace']),9)
        self.assertEqual(result['step_trace'][7]['status'],'BLOCKED')


class ResumeModelConsentTests(unittest.TestCase):
    def payload(self):return base64.b64encode((ROOT/'data/evidence-samples/award-programming-text.pdf').read_bytes()).decode()
    def test_default_never_constructs_model_even_with_key(self):
        with patch.dict(os.environ,{'APPLYGUARD_AI_API_KEY':'dummy'}),patch('backend.services.resume_parser.HttpModelClient',side_effect=AssertionError('must stay local')):
            self.assertEqual(parse_resume_pdf(self.payload(),'fictional.pdf')['extractor'],'规则抽取')
    def test_explicit_dynamic_is_required_and_invalid_mode_rejected(self):
        from unittest.mock import MagicMock
        client=MagicMock();client.api_key='dummy';client.complete_json.return_value={}
        with patch('backend.services.resume_parser.HttpModelClient',return_value=client):
            parse_resume_pdf(self.payload(),'fictional.pdf',parse_mode='dynamic')
        self.assertEqual(client.complete_json.call_count,1)
        with self.assertRaises(ValueError):parse_resume_pdf(self.payload(),'fictional.pdf',parse_mode='typo')
    def test_model_invented_identity_falls_back_to_local_source(self):
        from unittest.mock import MagicMock
        client=MagicMock();client.api_key='dummy';client.complete_json.return_value={'basic':{'name':'Invented Person Absent From PDF'}}
        with patch('backend.services.resume_parser.HttpModelClient',return_value=client):
            result=parse_resume_pdf(self.payload(),'fictional.pdf',parse_mode='dynamic')
        self.assertEqual(result['extractor'],'规则抽取（模型不可用）')
        self.assertNotEqual(result['form']['basic']['name'],'Invented Person Absent From PDF')
