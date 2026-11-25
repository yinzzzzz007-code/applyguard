"""Inspect material association; --sag explicitly permits model-backed discovery."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sag',action='store_true',help='Send current experience and imported materials to the configured model service')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    from backend import app
    from backend.services.local_store import load_resume_draft,load_workflow_draft
    from backend.services import evidence_workspace as ew
    form=load_resume_draft()
    if not form:parser.error('No local resume draft; configure APPLYGUARD_LOCAL_DIR first')
    if args.sag:
        from backend.services.material_discovery import discover
        from backend.services.resume_draft_vault import experiences_from_resume_draft
        items=experiences_from_resume_draft(form)
        workflow=(load_workflow_draft() or {}).get('workflow') or {}
        claims=workflow.get('resume_claims') or [c for item in items for c in item['claims']]
        result=discover({'candidate_id':items[0]['candidate_id'],'resume_draft':form,'claims':claims,'local_only':False})
    else:
        result={'mode':'local','workspaces':[ew.match_resume(space['workspace_id'],{**form,'awards':[{**a,'award_id':a['id']} for a in form.get('awards',[])]}) for space in ew.list_workspaces()]}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k in {'mode','run_id','engine','source_count','query_count','stats'}},ensure_ascii=False))
    if not args.sag:print(json.dumps([space['summary'] for space in result['workspaces']],ensure_ascii=False))

if __name__=='__main__':main()
