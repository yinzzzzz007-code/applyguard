import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.services.verification_audit import current_conflict


class ExportConflictPreflightTests(unittest.TestCase):
    def test_only_current_owned_cited_conflict_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runs=root/'verification-runs';runs.mkdir()
            record={'candidate_hash':hashlib.sha256(b'candidate').hexdigest(),'snapshot':'current',
                    'operation':'verify','mode':'sag_atomic','run_id':'known','error':None,
                    'results':{'claim_1':{'final_text':'15%','state':'BLOCKED',
                        'atoms':[{'relation':'CONTRADICTED','citations':[{'quote':'10%'}]}]}}}
            path=runs/'known.json'
            with patch('backend.services.verification_audit.local_dir',return_value=root):
                path.write_text(json.dumps(record))
                self.assertEqual(current_conflict('candidate',[{'claim_id':'claim_1','text':'15%'}],'current'),'known')
                for candidate,text,snapshot in [('other','15%','current'),('candidate','10%','current'),('candidate','15%','changed')]:
                    self.assertIsNone(current_conflict(candidate,[{'claim_id':'claim_1','text':text}],snapshot))
                for mutation in ('error','citation','operation'):
                    changed=copy.deepcopy(record)
                    if mutation=='error':changed['error']='timeout'
                    elif mutation=='citation':changed['results']['claim_1']['atoms'][0]['citations']=[]
                    else:changed['operation']='polish'
                    path.write_text(json.dumps(changed))
                    self.assertIsNone(current_conflict('candidate',[{'claim_id':'claim_1','text':'15%'}],'current'))

    def test_strict_export_rejects_known_conflict_before_model(self):
        from backend.services.grounded_workflow import export_grounded
        with patch('backend.services.reverification.reverify_workflow',return_value={'resume_claims':[{'claim_id':'claim_1','text':'15%'}]}) as verify, patch('backend.services.grounded_workflow.load_grounding_experiences',return_value=[]), patch('backend.services.verification_audit.current_conflict',return_value='known'):
            with self.assertRaisesRegex(ValueError,'已记录冲突'):
                export_grounded(Path('unused'),{'candidate_id':'candidate','human_confirmed':True})
            self.assertEqual(verify.call_count,1)
            self.assertTrue(verify.call_args.kwargs['_skip_grounding'])
