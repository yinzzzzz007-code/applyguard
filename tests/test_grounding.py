"""Policy and integration regressions. Fake model tests are NOT quality metrics."""
import base64
import copy
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch, MagicMock

from backend import app
from backend.services import evidence_workspace as ew
from backend.services.atomic_verifier import AtomicVerifier
from backend.services.grounded_workflow import (GroundingService, collect_sources,
    grounding_mode, load_grounding_experiences)
from backend.services.model_client import HttpModelClient, ModelFailure
from backend.services.sag_grounding import GroundingUnavailable, search_queries

TEXT = 'Alex wrote Python interface tests for Atlas.'
CLAIM = {'claim_id':'claim_atlas','text':TEXT}
JD = 'Backend Developer requires Python API testing and automated tests.'

def experience():
    return {'candidate_id':'cand_test','experience_id':'exp_atlas','title':'Atlas',
        'organization':'Fictional Lab','claims':[{**CLAIM,'evidence_ids':['ev_proof']}],
        'evidence_sources':[{'evidence_id':'ev_proof','description':TEXT,
            'verification_status':'VERIFIED','_version':'v1'}]}

class AllSources:
    def retrieve_many(self, queries, sources, candidate_id):
        return {q['claim_id']:sources for q in queries}

class ScriptedModel:
    """Deliberately optimistic judge: policy must reject forged source support."""
    def __init__(self, *, relation='SUPPORTED', complete=True, quote=None, callback=None):
        self.relation, self.complete, self.quote, self.callback = relation, complete, quote, callback
    def complete_json(self, prompt, data):
        value=json.loads(data)
        if 'Split each' in prompt:
            return {'items':[{'id':c['id'],'atoms':[{'atom_id':'a1','text':c['text']}]} for c in value['claims']]}
        if 'Polish each' in prompt:
            return {'items':[{'id':c['id'],'text':TEXT} for c in value['items']]}
        if self.callback:self.callback()
        return {'items':[{'id':c['id'],'complete':self.complete,'atoms':[
            {'atom_id':a['atom_id'],'relation':self.relation,'reason':'scripted policy fixture',
             'citations':[{'source_id':s['source_id'],'quote':self.quote or s['text']}
                 for s in c['sources'][:1]]} for a in c['atoms']]} for c in value['items']]}

class GroundingPolicyTests(unittest.TestCase):
    def run_service(self, model=None, items=None, mode='sag_atomic'):
        return GroundingService(retriever=AllSources(),model=model or ScriptedModel()).run(
            [copy.deepcopy(CLAIM)],items or [experience()],'cand_test',mode)

    def test_source_review_is_not_a_semantic_pass_in_sag_mode(self):
        _, checks, report=self.run_service(mode='sag')
        self.assertEqual(checks[0]['state'],'NEEDS_REVIEW')
        self.assertEqual(report['results']['claim_atlas']['atoms'],[])

    def test_exact_citation_and_current_text_are_bound(self):
        _, checks, report=self.run_service()
        self.assertEqual(checks[0]['state'],'VERIFIED')
        result=report['results']['claim_atlas']
        quote=result['atoms'][0]['citations'][0]
        self.assertEqual(TEXT[quote['start']:quote['end']],quote['quote'])
        self.assertEqual(quote['source_version'],'v1')
        self.assertEqual(result['final_text'],TEXT)

    def test_nonliteral_quote_cannot_pass(self):
        _, checks, _=self.run_service(ScriptedModel(quote='Alex led Atlas and improved it by 900%'))
        self.assertEqual(checks[0]['state'],'NEEDS_REVIEW')

    def test_incomplete_atomization_cannot_pass(self):
        self.assertEqual(self.run_service(ScriptedModel(complete=False))[1][0]['state'],'NEEDS_REVIEW')

    def test_conflicting_fact_blocks(self):
        self.assertEqual(self.run_service(ScriptedModel(relation='CONTRADICTED'))[1][0]['state'],'BLOCKED')

    def test_provider_failure_cannot_reuse_verified(self):
        model=MagicMock();model.complete_json.side_effect=ModelFailure('timeout')
        _, checks, report=self.run_service(model)
        self.assertEqual(checks[0]['state'],'NEEDS_REVIEW');self.assertTrue(report['error'])

    def test_duplicate_or_missing_atoms_fail_closed(self):
        for payload in ({'items':[]},{'items':[{'id':'claim_atlas','atoms':[]}]},
            {'items':[{'id':'claim_atlas','atoms':[{'atom_id':'a','text':'a'}]*2}]}):
            model=MagicMock();model.complete_json.return_value=payload
            self.assertNotEqual(self.run_service(model)[1][0]['state'],'VERIFIED')

    def test_out_of_project_retrieval_is_removed_even_if_retriever_ignores_scope(self):
        original=experience();other=experience()
        other.update(experience_id='exp_beacon',claims=[])
        other['evidence_sources'][0]['description']='Alex implemented Redis in Beacon.'
        sources,_,allowed=collect_sources([original,other],'cand_test')
        hits=GroundingService(retriever=AllSources()).retrieve([CLAIM],sources,allowed,'cand_test')
        self.assertEqual([h['experience_id'] for h in hits['claim_atlas']],['exp_atlas'])

    def test_foreign_candidate_and_draft_cannot_supply_proof(self):
        original=experience();original['candidate_id']='cand_other'
        self.assertEqual(self.run_service(items=[original])[1][0]['state'],'BLOCKED')
        original=experience();original['evidence_sources'][0]['evidence_id']='ev_draft_unknown'
        self.assertEqual(self.run_service(items=[original])[1][0]['state'],'BLOCKED')

    def test_same_experience_correction_is_searchable_and_revoked_required_ref_blocks(self):
        original=experience()
        original['evidence_sources'].append({'evidence_id':'ev_correction','description':'Correction: Java only.',
            'verification_status':'VERIFIED'})
        self.assertEqual(len(collect_sources([original],'cand_test')[2]['claim_atlas']),2)
        original['evidence_sources'][0]['verification_status']='CONFLICTING'
        self.assertEqual(collect_sources([original],'cand_test')[2]['claim_atlas'],[])

    def test_three_search_channels_and_atomic_server_floor(self):
        self.assertEqual([q[0] for q in search_queries(TEXT)],['support','refutation','correction'])
        with patch.dict(os.environ,{'APPLYGUARD_GROUNDING_MODE':'sag_atomic'}):
            self.assertEqual(grounding_mode({'grounding_mode':'off'}),'sag_atomic')

    def test_truncated_valid_json_is_rejected_by_grounding_transport(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({
            'choices':[{'finish_reason':'length','message':{'content':'{"items":[]}'}}]}).encode()
        with patch('urllib.request.urlopen',return_value=response), self.assertRaises(ModelFailure):
            HttpModelClient(api_key='test-only',require_complete=True).complete_json('s','u')

class GroundingHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'APPLYGUARD_EVIDENCE_DIR':self.tmp.name,
            'APPLYGUARD_LOCAL_DIR':self.tmp.name,'APPLYGUARD_GROUNDING_MODE':'off'})
        self.env.start()
        ws=ew.create_workspace('Fictional integration')
        self.file=ew.import_files(ws['workspace_id'],[{'relative_path':'atlas.md',
            'content_base64':base64.b64encode(TEXT.encode()).decode()}])['files'][0]
        self.eid=self.file['evidence_id']
        ew.review_evidence(self.eid,{'normalized_fields':{},'review_state':'REVIEWED'})
        ew.create_link({'target_type':'project','target_id':'atlas','evidence_id':self.eid})
        self.form={'candidateId':'cand_test','projects':[{'id':'atlas','title':'Atlas',
            'organization':'Fictional Lab','start':'2025-01','end':'2025-06','description':TEXT}],
            'internships':[],'awards':[]}
        self.request={'candidate_id':'cand_test','jd_text':JD,'resume_draft':self.form,
            'grounding_mode':'sag_atomic','claims':[CLAIM]}
        self.service=GroundingService(retriever=AllSources(),model=ScriptedModel())
        self.mock=patch('backend.services.grounded_workflow.GroundingService',return_value=self.service)
        self.mock.start()
        self.server=app.create_server('127.0.0.1',0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.mock.stop();self.env.stop();self.tmp.cleanup()
    def post(self,path,payload=None):
        req=urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}/api/v1/{path}',
            json.dumps(payload or self.request).encode(),{'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=10) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_reverify_ignores_forged_refs_and_displays_original_position(self):
        status, result=self.post('workflow/reverify')
        self.assertEqual(status,200)
        self.assertEqual(result['claim_verification'][0]['state'],'VERIFIED')
        quote=result['grounding']['results']['claim_atlas']['atoms'][0]['citations'][0]
        self.assertEqual(quote['file_version'],1);self.assertTrue(quote['positions'])
        self.request['claims']=[{'claim_id':'claim_unknown','text':TEXT,'state':'VERIFIED','evidence_ids':[self.eid]}]
        self.assertEqual(self.post('workflow/reverify')[1]['claim_verification'][0]['state'],'BLOCKED')
    def test_polish_endpoint_and_sag_preview(self):
        self.request['grounding_mode']='sag'
        status,result=self.post('resume/polish')
        self.assertEqual(status,200)
        self.assertEqual(result['claim_verification'][0]['state'],'NEEDS_REVIEW')
        self.assertNotIn('CONFIRM',result['human_confirmation']['allowed_actions'])
    def test_export_requires_human_and_fresh_atomic_check(self):
        self.assertEqual(self.post('resume/export')[0],422)
        self.request.update(human_confirmed=True,grounding_mode='sag',export_text='forged')
        status,result=self.post('resume/export')
        self.assertEqual(status,200);self.assertEqual(result['text'],TEXT)
        self.service.model=ScriptedModel(complete=False)
        self.assertEqual(self.post('resume/export')[0],422)
    def test_revoked_link_and_midflight_change_invalidate_result(self):
        self.service.model=ScriptedModel(callback=lambda:ew.create_link({
            'target_type':'project','target_id':'atlas','evidence_id':self.eid,'link_state':'REJECTED'}))
        _,result=self.post('workflow/reverify')
        self.assertTrue(result['grounding']['error'])
        self.assertEqual(result['claim_verification'][0]['state'],'NEEDS_REVIEW')
        self.assertNotIn('CONFIRM',result['human_confirmation']['allowed_actions'])
        self.request['human_confirmed']=True
        self.assertEqual(self.post('resume/export')[0],422)

if __name__=='__main__':unittest.main()
