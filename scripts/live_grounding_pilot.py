"""Real app HTTP + SAG + model pilot on invented materials only.

Labels are authored smoke cases, NOT independently annotated evaluation.
Uses persistent local pilot-only workspace for repeatability; no user documents.
"""
import base64
import copy
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path
from run_grounded import configure, ROOT

CASEBOOK = [
    {'id':'atlas','original':'Alex wrote Python API tests for Atlas.',
     'sources':['Atlas project record. Alex wrote Python API tests. Priya was project lead. No Redis was used in Atlas.'],
     'good':'Alex contributed Python API testing to Atlas.',
     'bad':'Alex implemented Redis caching in Atlas.','category':'cross_project_technology'},
    {'id':'beacon','original':'Alex implemented Redis caching for Beacon.',
     'sources':['Project registry: Beacon and BRV-7 are the same project.',
                'BRV-7 record: Alex implemented Redis caching. Priya led the project and implemented React.'],
     'good':'Alex implemented Redis caching for Beacon.',
     'bad':'Alex led Beacon and implemented its React frontend.','category':'role_and_attribution'},
    {'id':'delta','original':'Dana wrote Java API tests for Delta.',
     'sources':['Delta superseded draft: Dana wrote Python API tests. Correction: The previous draft is wrong. Delta used Java exclusively. Dana wrote Java API tests. The Python claim is withdrawn.'],
     'good':'Dana wrote Java API tests for Delta.',
     'bad':'Dana wrote Python API tests for Delta.','category':'superseded_statement'},
    {'id':'forge','original':'林青编写了Forge的Kubernetes部署方案。',
     'sources':['Forge项目记录：林青于2026年编写Kubernetes部署方案，计划于2027年实施。实际部署尚未开始；已完成的工作仅为编写方案。'],
     'good':'林青于2026年编写了Forge的Kubernetes部署方案。',
     'bad':'林青于2026年完成了Forge的Kubernetes生产部署。','category':'planned_vs_completed'},
    {'id':'cedar','original':'Alex measured a 25% median latency reduction in the Cedar local benchmark.',
     'sources':['Cedar benchmark: Alex ran local prototype tests. Median latency decreased from 200 ms to 150 ms, a 25% relative reduction. No production deployment or throughput measurement occurred.'],
     'good':'Alex measured a 25% relative reduction in median latency in Cedar local prototype tests.',
     'bad':'Alex increased Cedar production throughput by 50%.','category':'metric_and_scope'},
]

def main():
    configure()
    directory=ROOT/'data/local/integration-pilot'
    directory.mkdir(parents=True,exist_ok=True)
    os.environ['APPLYGUARD_EVIDENCE_DIR']=str(directory/'evidence')
    os.environ['APPLYGUARD_LOCAL_DIR']=str(directory/'drafts')
    os.environ['APPLYGUARD_GROUNDING_DIR']=str(directory/'sag')
    # Allow both experimental arms; deployment launcher defaults to atomic floor.
    os.environ['APPLYGUARD_GROUNDING_MODE']='off'
    from backend import app
    from backend.services import evidence_workspace as ew
    state=directory/'workspace.json'
    if state.exists():ws=json.loads(state.read_text(encoding='utf-8'))
    else:
        ws=ew.create_workspace('Fictional SAG integration pilot')
        state.write_text(json.dumps(ws),encoding='utf-8')
    draft={'candidateId':'cand_pilot','projects':[],'internships':[],'awards':[]}
    for case in CASEBOOK:
        draft['projects'].append({'id':case['id'],'title':case['id'].title(),
            'organization':'Fictional Lab','start':'2026-01','end':'2026-10','description':case['original']})
        for index,text in enumerate(case['sources']):
            file=ew.import_files(ws['workspace_id'],[{'relative_path':f"{case['id']}-{index}.md",
                'content_base64':base64.b64encode(text.encode()).decode()}])['files'][0]
            ew.review_evidence(file['evidence_id'],{'normalized_fields':{},'review_state':'REVIEWED'})
            ew.create_link({'target_type':'project','target_id':case['id'],'evidence_id':file['evidence_id']})
    request={'candidate_id':'cand_pilot','jd_text':'Backend developer requires Python API testing, Redis caching, Java and Kubernetes planning.',
        'resume_draft':draft,'grounding_mode':'sag_atomic'}
    server=app.create_server('127.0.0.1',0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    results={'annotation':'Author-labelled synthetic integration pilot; not independent evaluation',
        'model':os.environ['APPLYGUARD_AI_MODEL'],'cases':CASEBOOK,'runs':{}}
    output=ROOT/'output';output.mkdir(exist_ok=True)
    def post(path,body):
        start=time.monotonic()
        req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/v1/{path}',
            json.dumps(body).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=1200) as response:data=json.load(response)
        return {'elapsed_seconds':round(time.monotonic()-start,2),'response':data}
    try:
        for name in ['good','bad','sag_polish']:
            print('Running '+name,flush=True)
            body={**request,'claims':[{'claim_id':'claim_'+c['id'],'text':c['bad' if name=='sag_polish' else name]} for c in CASEBOOK]}
            if name=='sag_polish':body['grounding_mode']='sag'
            result=post('resume/polish' if name=='sag_polish' else 'workflow/reverify',body)
            results['runs'][name]=result
            (output/'integration-live.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            print(name+': '+json.dumps([(r['claim_id'],r['state']) for r in result['response']['claim_verification']]),flush=True)
        good=results['runs']['good']['response']['claim_verification']
        bad=results['runs']['bad']['response']['claim_verification']
        results['metrics']={'unsupported_accepted':sum(r['state']=='VERIFIED' for r in bad),
            'unsupported_total':len(bad),'supported_blocked':sum(r['state']=='BLOCKED' for r in good),
            'supported_total':len(good),'review_total':sum(r['state']=='NEEDS_REVIEW' for r in good+bad),
            'total':len(good+bad),'supported_accepted':sum(r['state']=='VERIFIED' for r in good)}
        (output/'integration-live.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(results['metrics']),flush=True)
    finally:
        server.shutdown();server.server_close();worker.join()

if __name__=='__main__':main()
