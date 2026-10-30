"""Same-model fixed-hit replay isolates verifier changes from model/retrieval changes."""
import importlib.util,json,sys,time
from run_grounded import configure,ROOT
sys.path.insert(0,str(ROOT))
from backend.services.model_client import HttpModelClient

def main():
    configure();spec=importlib.util.spec_from_file_location('frozen_atomic',ROOT/'eval/frozen-v1/atomic_verifier.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    old=json.loads((ROOT/'output/integration-live.json').read_text(encoding='utf-8'))
    client=HttpModelClient(max_tokens=6000,timeout=110,require_complete=True);runs={}
    for kind in ['good','bad']:
        claims=[];hits={};contexts={}
        for cid,row in old['runs'][kind]['response']['grounding']['results'].items():
            claims.append({'claim_id':cid,'text':row['final_text']});hits[cid]=row['retrieved_sources'];source=hits[cid][0]
            contexts[cid]={'candidate_id':source['candidate_id'],'experience_id':source['experience_id'],'project':source['title']}
        start=time.monotonic()
        try:results=module.AtomicVerifier(client).verify(claims,contexts,hits);error=None
        except Exception as e:results={};error=type(e).__name__
        runs[kind]={'elapsed':time.monotonic()-start,'results':results,'error':error}
        print(kind,[(k,v['relation'],v['complete']) for k,v in results.items()],flush=True)
        (ROOT/'output/expanded-eval/dev-v1-gpt-4.1-mini.json').write_text(json.dumps({'runs':runs,'usage':client.usage},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
