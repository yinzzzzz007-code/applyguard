"""Recheck the real SAG polishing output through the app's atomic endpoint."""
import json
import os
import threading
import time
import urllib.request
from run_grounded import configure, ROOT
from live_grounding_pilot import CASEBOOK

def main():
    configure()
    directory=ROOT/'data/local/integration-pilot'
    for name,path in [('APPLYGUARD_EVIDENCE_DIR','evidence'),('APPLYGUARD_LOCAL_DIR','drafts'),('APPLYGUARD_GROUNDING_DIR','sag')]:
        os.environ[name]=str(directory/path)
    os.environ['APPLYGUARD_GROUNDING_MODE']='sag_atomic'
    output=ROOT/'output/integration-live.json'
    results=json.loads(output.read_text(encoding='utf-8'))
    draft={'candidateId':'cand_pilot','projects':[{'id':c['id'],'title':c['id'].title(),
        'organization':'Fictional Lab','start':'2026-01','end':'2026-10','description':c['original']}
        for c in CASEBOOK],'internships':[],'awards':[]}
    request={'candidate_id':'cand_pilot','jd_text':'Backend developer requires Python API testing, Redis caching, Java and Kubernetes planning.',
        'resume_draft':draft,'grounding_mode':'sag_atomic','claims':[
            {'claim_id':c['claim_id'],'text':c['text']} for c in results['runs']['sag_polish']['response']['resume_claims']]}
    from backend import app
    server=app.create_server('127.0.0.1',0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        print('Rechecking polished text with original evidence',flush=True)
        start=time.monotonic()
        req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/v1/workflow/reverify',
            json.dumps(request).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=1200) as response:result=json.load(response)
        results['runs']['polish_atomic']={'elapsed_seconds':round(time.monotonic()-start,2),'response':result}
        output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps([(r['claim_id'],r['state']) for r in result['claim_verification']]),flush=True)
    finally:
        server.shutdown();server.server_close();worker.join()

if __name__=='__main__':main()
