"""Structural and edit safety regressions; never used as model quality scores."""
import copy,json,unittest
from unittest.mock import patch
from backend.services.atomic_verifier import AtomicVerifier
from backend.services.structured_verifier import missing_numeric_qualifiers
from backend.services.grounded_workflow import GroundingService,collect_sources
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
                'atoms':{aid:verdict for aid in row['atoms']},'missing_assertions':['omitted fact'] if self.missing else []}
        return out

class GroundingV2Tests(unittest.TestCase):
    def verify(self,model):
        sources,ctx,_=collect_sources([experience()],'cand_test')
        return AtomicVerifier(model).verify([CLAIM],ctx,{CLAIM['claim_id']:sources})[CLAIM['claim_id']]
    def test_strict_output_deterministic_id_and_exact_quote(self):
        row=self.verify(Model());self.assertEqual(row['atoms'][0]['atom_id'],'a1');self.assertEqual(row['relation'],'SUPPORTED')
        self.assertEqual(self.verify(Model(badquote=True))['relation'],'INSUFFICIENT')
    def test_full_claim_can_block_even_if_atoms_pass(self):
        self.assertEqual(self.verify(Model(fullbad=True))['relation'],'CONTRADICTED')
    def test_coverage_repairs_are_bounded(self):
        model=Model(missing=True);row=self.verify(model)
        self.assertEqual(row['relation'],'INSUFFICIENT');self.assertEqual(row['coverage_repairs'],1)
        self.assertEqual(len(model.calls),4)
    def test_numeric_coverage_in_chinese(self):
        self.assertEqual(missing_numeric_qualifiers('通过18/20条，准确率90%，提高4个百分点',['通过18条']),['20','4个百分点','90%'])
    def test_missing_atom_ids_never_pass(self):
        model=Model();original=model.complete_structured
        def incomplete(prompt,data,schema):
            out=original(prompt,data,schema)
            if prompt.startswith('Check'):
                for row in out.values():row['atoms']={}
            return out
        model.complete_structured=incomplete
        with self.assertRaises(GroundingUnavailable):self.verify(model)
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
        self.assertEqual(checks[0]['state'],'BLOCKED')
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

if __name__=='__main__':unittest.main()
