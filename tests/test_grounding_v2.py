"""Structural and edit safety regressions; never used as model quality scores."""
import copy,json,unittest
from unittest.mock import patch
from backend.services.atomic_verifier import AtomicVerifier
from backend.services.structured_verifier import missing_numeric_qualifiers
from backend.services.grounded_workflow import GroundingService,collect_sources,high_risk_edit
from backend.services.sag_grounding import SAGRetriever,evidence_snapshot,GroundingUnavailable
from tests.test_grounding import AllSources,experience,CLAIM,TEXT

class Model:
    def __init__(self,*,proposal=None,loss=False,missing=False,badquote=False,fullbad=False):
        self.proposal,self.loss,self.missing,self.badquote,self.fullbad=proposal,loss,missing,badquote,fullbad
        self.calls=[]
    def complete_structured(self,prompt,data,schema):
        data=json.loads(data);self.calls.append(prompt)
        if prompt.startswith('Polish'):
            return {c['id']:{'text':self.proposal or c['draft']} for c in data['items']}
        if prompt.startswith('Compare'):
            return {cid:{'lost_supported_details':['Python'] if self.loss else [],'reason':'test'} for cid in data}
        if prompt.startswith('Split'):
            return {cid:{'assertions':[row['full_claim']]} for cid,row in data.items()}
        out={}
        for cid,row in data.items():
            source=row['sources'][0]
            relation='CONTRADICTED' if '900%' in row['full_claim'] else 'SUPPORTED'
            verdict={'relation':relation,'reason':'fixture','citations':[{'source_id':source['source_id'],
                'quote':'fabricated quote' if self.badquote else source['text']}]}
            out[cid]={'full_claim':{**verdict,'relation':'CONTRADICTED' if self.fullbad else relation},
                'atoms':{aid:{**verdict, 'claim_excerpt':row['full_claim']} for aid in row['atoms']},'missing_assertions':['omitted fact'] if self.missing else []}
        return out

class GroundingV2Tests(unittest.TestCase):
    def verify(self,model):
        sources,ctx,_=collect_sources([experience()],'cand_test')
        return AtomicVerifier(model).verify([CLAIM],ctx,{CLAIM['claim_id']:sources})[CLAIM['claim_id']]
    def test_strict_output_deterministic_id_and_exact_quote(self):
        row=self.verify(Model());self.assertEqual(row['atoms'][0]['atom_id'],'a1');self.assertEqual(row['relation'],'SUPPORTED')
        self.assertEqual(self.verify(Model(badquote=True))['relation'],'INSUFFICIENT')
    def test_highlight_requires_a_unique_verbatim_excerpt_in_the_draft(self):
        class LocatedModel(Model):
            def complete_structured(self, prompt, data, schema):
                rows = super().complete_structured(prompt, data, schema)
                if prompt.startswith('Check'):
                    for row in rows.values():
                        for verdict in row['atoms'].values():
                            verdict['claim_excerpt'] = self.excerpt
                return rows

        model = LocatedModel()
        for excerpt, expected in [('Python interface tests', True), ('invented phrase', False), ('te', False)]:
            with self.subTest(excerpt=excerpt):
                model.excerpt = excerpt
                atom = self.verify(model)['atoms'][0]
                self.assertEqual(atom.get('claim_excerpt'), excerpt if expected else TEXT)
                self.assertEqual(atom['relation'], 'SUPPORTED')

    def test_whole_only_contradiction_requires_review(self):
        self.assertEqual(self.verify(Model(fullbad=True))['relation'],'INSUFFICIENT')
    def test_coverage_repairs_are_bounded(self):
        model=Model(missing=True);row=self.verify(model)
        self.assertEqual(row['relation'],'INSUFFICIENT');self.assertEqual(row['coverage_repairs'],1)
        self.assertEqual(len(model.calls),4)
    def test_atomic_requests_keep_each_claim_in_its_own_batch(self):
        from backend.services.structured_verifier import StructuredVerifier
        verifier=StructuredVerifier(Model())
        claims=[{'claim_id':'a','text':'first'},{'claim_id':'b','text':'second'}]
        calls=[]
        def observed(rows,contexts,hits):
            calls.append([row['claim_id'] for row in rows])
            return {row['claim_id']:{'relation':'INSUFFICIENT'} for row in rows}
        with patch.object(verifier,'_verify_batch',side_effect=observed):
            result=verifier.verify(claims,{}, {})
        self.assertEqual(sorted(calls),[['a'],['b']])
        self.assertEqual(set(result),{'a','b'})

    def test_model_payload_keeps_all_source_text_but_local_citations_keep_positions(self):
        sources,contexts,_=collect_sources([experience()],'cand_test')
        source=sources[0]
        source['text_offset']=20
        source['positions']=[{'start':20,'end':20+len(source['text']),'page':2}]
        class Observed(Model):
            def complete_structured(self,prompt,data,schema):
                if prompt.startswith('Check'):
                    sent=json.loads(data)[CLAIM['claim_id']]['sources'][0]
                    self_outer.assertEqual(sent['text'],source['text'])
                    self_outer.assertEqual(sent['experience_id'],source['experience_id'])
                    self_outer.assertNotIn('positions',sent)
                    self_outer.assertNotIn('sha256',sent)
                return super().complete_structured(prompt,data,schema)
        self_outer=self
        result=AtomicVerifier(Observed()).verify([CLAIM],contexts,{CLAIM['claim_id']:sources})[CLAIM['claim_id']]
        citation=result['atoms'][0]['citations'][0]
        self.assertEqual(citation['start'],20)
        self.assertEqual(citation['positions'],source['positions'])
        self.assertEqual(citation['source_sha256'],source['sha256'])
        self.assertEqual(result['relation'],'SUPPORTED')

    def test_numeric_coverage_in_chinese(self):
        self.assertEqual(missing_numeric_qualifiers('通过18/20条，准确率90%，提高4个百分点',['通过18条']),['20','4个百分点','90%'])
    def test_thousands_grouping_does_not_look_like_dropped_numbers(self):
        self.assertEqual(missing_numeric_qualifiers('排名247/5,255',['排名247，总队伍5255']),[])
        self.assertEqual(missing_numeric_qualifiers('处理1,024,000条',['处理1024000条']),[])
        self.assertTrue(missing_numeric_qualifiers('排名247/5,255',['排名246，总队伍5255']))
        self.assertIn('5255',missing_numeric_qualifiers('排名247/5,255',['排名247，总队伍5252']))
        self.assertTrue(missing_numeric_qualifiers('数值4,18',['数值418']))
        self.assertTrue(missing_numeric_qualifiers('通过率4.185%',['通过率5255%']))
        from backend.services.fact_lock import wording_invariants
        self.assertFalse(wording_invariants('Processed 5,255 records.','Processed 5255 records.'))
        self.assertTrue(wording_invariants('Processed 5,255 records.','Processed 5252 records.'))

    def test_missing_atom_ids_never_pass(self):
        model=Model();original=model.complete_structured
        def incomplete(prompt,data,schema):
            out=original(prompt,data,schema)
            if prompt.startswith('Check'):
                for row in out.values():row['atoms']={}
            return out
        model.complete_structured=incomplete
        with self.assertRaises(GroundingUnavailable):self.verify(model)
    def test_polish_covers_manual_and_vault_claims_without_marking_manual_verified(self):
        class Observed(Model):
            def complete_structured(self,prompt,data,schema):
                if prompt.startswith('Polish'):
                    payload=json.loads(data)
                    if not hasattr(self,'ids'):
                        self.ids=[entry['id'] for entry in payload['items']]
                        self.manual_sources=next(entry['sources'] for entry in payload['items'] if entry['id']=='claim_manual_demo')
                return super().complete_structured(prompt,data,schema)
        model=Observed()
        manual={'claim_id':'claim_manual_demo','text':'I used Python for a prototype.','evidence_ids':[]}
        _,checks,report=GroundingService(retriever=AllSources(),model=model).run(
            [copy.deepcopy(CLAIM),manual],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(set(model.ids),{CLAIM['claim_id'],'claim_manual_demo'})
        self.assertEqual(model.manual_sources,[])
        self.assertIsNotNone(report['results']['claim_manual_demo'].get('proposed_text'))
        self.assertEqual(next(row for row in checks if row['claim_id']=='claim_manual_demo')['state'],'NEEDS_REVIEW')
        self.assertNotEqual(report['results']['claim_manual_demo']['relation'],'SUPPORTED')

    def test_verification_503_keeps_unverified_asu_suggestion(self):
        from backend.services.model_client import ModelFailure
        model=Model(proposal='Alex developed Python interface tests for Atlas.')
        with patch.object(AtomicVerifier,'verify',side_effect=ModelFailure('unavailable',http_status=503)):
            claims,checks,report=GroundingService(retriever=AllSources(),model=model).run(
                [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        result=report['results'][CLAIM['claim_id']]
        self.assertEqual(claims[0]['text'],TEXT)
        self.assertNotEqual(checks[0]['state'],'VERIFIED')
        self.assertEqual(report['failure_stage'],'原文原子核验')
        self.assertIn('尚未核验',report['error'])
        self.assertEqual(result['proposed_text'],'Alex developed Python interface tests for Atlas.')
        self.assertIsNone(result['proposal_check'])
        self.assertFalse(result['proposal_applied'])

    def test_failed_retrieval_still_offers_unverified_restatement(self):
        model=Model(proposal='Alex developed Python interface tests for Atlas.')
        service=GroundingService(retriever=AllSources(),model=model)
        with patch.object(service,'retrieve',side_effect=GroundingUnavailable('检索未完成')):
            claims,checks,report=service.run([copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(claims[0]['text'],TEXT)
        self.assertNotEqual(checks[0]['state'],'VERIFIED')
        self.assertEqual(report['failure_stage'],'材料检索')
        self.assertTrue(report['results'][CLAIM['claim_id']]['proposed_text'])

    def test_failed_wording_review_does_not_discard_generated_proposal(self):
        from backend.services.model_client import ModelFailure
        model=Model(proposal='Alex developed Python interface tests for Atlas.')
        with patch('backend.services.grounded_workflow.review_edit',side_effect=ModelFailure('unavailable',http_status=503)):
            claims,checks,report=GroundingService(retriever=AllSources(),model=model).run(
                [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(claims[0]['text'],TEXT)
        self.assertNotEqual(checks[0]['state'],'VERIFIED')
        self.assertEqual(report['failure_stage'],'改写核验')
        self.assertTrue(report['results'][CLAIM['claim_id']]['proposed_text'])
    def test_local_only_never_calls_retrieval_or_fact_model(self):
        model = Model()
        service = GroundingService(retriever=AllSources(), model=model)
        with patch.object(service, 'retrieve', side_effect=AssertionError('Unexpected remote retrieval')):
            for polish in (False, True):
                with self.subTest(polish=polish):
                    _, checks, report = service.run([copy.deepcopy(CLAIM)], [experience()],
                                                     'cand_test', 'sag_atomic', polish=polish, local_only=True)
                    self.assertEqual(model.calls, [])
                    self.assertNotEqual(checks[0]['state'], 'VERIFIED')
                    self.assertTrue(report['error'])

    def test_rejected_edit_restores_and_rechecks_original(self):
        model=Model(proposal='Alex increased throughput by 900%.')
        claims,checks,report=GroundingService(retriever=AllSources(),model=model).run([copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(claims[0]['text'],TEXT);self.assertEqual(checks[0]['state'],'VERIFIED')
        self.assertTrue(report['results'][CLAIM['claim_id']]['proposal_rejected'])
        self.assertGreaterEqual(sum(p.startswith('Check') for p in model.calls),2)
    def test_reverting_a_bad_original_does_not_make_it_verified(self):
        bad={**CLAIM,'text':'Alex increased throughput by 900%.'}
        model=Model(proposal='Alex alone increased throughput by 900%.')
        _,checks,_=GroundingService(retriever=AllSources(),model=model).run([bad],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(checks[0]['state'],'NEEDS_REVIEW')
    def test_supported_detail_loss_rejects_even_supported_proposal(self):
        model=Model(proposal='Alex wrote tests for Atlas.',loss=True)
        claims,_,report=GroundingService(retriever=AllSources(),model=model).run([copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(claims[0]['text'],TEXT);self.assertTrue(report['results'][CLAIM['claim_id']]['proposal_rejected'])
    def test_sag_preview_cannot_replace_original(self):
        claims,checks,_=GroundingService(retriever=AllSources(),model=Model(proposal='New text')).run([copy.deepcopy(CLAIM)],[experience()],'cand_test','sag',polish=True)
        self.assertEqual(claims[0]['text'],TEXT);self.assertEqual(checks[0]['state'],'NEEDS_REVIEW')
    def test_cache_key_binds_strategy_query_scope_and_source_version(self):
        q={'text':TEXT,'source_ids':['a']}
        self.assertNotEqual(SAGRetriever.cache_key(q,'vector'),SAGRetriever.cache_key(q,'full_expand'))
        self.assertNotEqual(SAGRetriever.cache_key(q,'vector'),SAGRetriever.cache_key({**q,'source_ids':['b']},'vector'))
        s,_,_=collect_sources([experience()],'cand_test');changed=copy.deepcopy(s);changed[0]['version']='v2'
        self.assertNotEqual(evidence_snapshot(s),evidence_snapshot(changed))
    def test_high_risk_edit_routes_to_strong_judge_and_cannot_override_primary(self):
        proposal='Alex led Python interface tests for Atlas.'
        self.assertTrue(high_risk_edit(TEXT,proposal))
        self.assertTrue(high_risk_edit(TEXT,TEXT.replace('Alex','Morgan')))
        self.assertFalse(high_risk_edit(TEXT,TEXT.replace('Atlas.','Atlas!')))
        with patch.dict('os.environ',{'APPLYGUARD_STRONG_AI_MODEL':'strong-test'}), patch(
                'backend.services.grounded_workflow.HttpModelClient',return_value=Model(fullbad=True)) as constructor:
            claims,checks,report=GroundingService(retriever=AllSources(),model=Model(proposal=proposal)).run(
                [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        constructor.assert_called_once()
        self.assertEqual(claims[0]['text'],TEXT)
        self.assertTrue(report['results'][CLAIM['claim_id']]['proposal_rejected'])
        self.assertEqual(report['results'][CLAIM['claim_id']]['risk_escalation']['relation'],'INSUFFICIENT')
        self.assertEqual(checks[0]['state'],'VERIFIED')
    def test_strong_judge_failure_keeps_original(self):
        proposal='Alex led Python interface tests for Atlas.'
        with patch.dict('os.environ',{'APPLYGUARD_STRONG_AI_MODEL':'strong-test'}), patch(
                'backend.services.grounded_workflow.HttpModelClient',side_effect=OSError('unavailable')):
            claims,_,report=GroundingService(retriever=AllSources(),model=Model(proposal=proposal)).run(
                [copy.deepcopy(CLAIM)],[experience()],'cand_test','sag_atomic',polish=True)
        self.assertEqual(claims[0]['text'],TEXT)
        self.assertTrue(report['results'][CLAIM['claim_id']]['proposal_rejected'])
        self.assertIn('error',report['results'][CLAIM['claim_id']]['risk_escalation'])

if __name__=='__main__':unittest.main()
