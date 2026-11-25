import base64,os,tempfile,unittest
from unittest.mock import patch
from backend.services import evidence_workspace as ew
from backend.services.material_discovery import discover

class MaterialDiscoveryTests(unittest.TestCase):
    def test_retrieval_preserves_actual_source_and_does_not_associate_or_verify(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'APPLYGUARD_EVIDENCE_DIR':root,'APPLYGUARD_LOCAL_DIR':root}):
            ws=ew.create_workspace('test')
            file=ew.import_files(ws['workspace_id'],[{'relative_path':'compiler/README.md','content_base64':base64.b64encode('# 编译器项目\n显存下降8%。'.encode()).decode()}])['files'][0]
            class Retriever:
                stats={'search_calls':1}
                def retrieve_many(self,queries,sources,candidate):
                    self.sources=sources
                    return {queries[0]['claim_id']:[sources[0],{'source_id':'outside','text':'虚构'}, {**sources[0],'text':'改写后的伪引文'}]}
            retriever=Retriever()
            request={'candidate_id':'cand_test','resume_draft':{'candidateId':'cand_test','projects':[{'id':'p1','title':'编译器项目','description':'显存下降12%'}]},'claims':[{'claim_id':'claim_p1'}],'local_only':False}
            result=discover(request,retriever)
            self.assertEqual(len(result['results']),1)
            self.assertEqual(result['results'][0]['evidence_id'],file['evidence_id'])
            self.assertIn('8%',result['results'][0]['quote'])
            self.assertEqual(ew.list_links()['links'],[])
            self.assertEqual(ew.get_evidence(file['evidence_id'])['review_state'],'UNREVIEWED')
            with self.assertRaises(ValueError):discover({**request,'local_only':True},retriever)
