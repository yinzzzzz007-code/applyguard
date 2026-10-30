"""Development-only fixed-evidence replay of the original ten cases."""
import json,time,sys,os
from pathlib import Path
from run_grounded import configure,ROOT
sys.path.insert(0,str(ROOT))
from backend.services.model_client import HttpModelClient
from backend.services.atomic_verifier import AtomicVerifier

def main():
    configure()
    old=json.loads((ROOT/'output/integration-live.json').read_text(encoding='utf-8'))
    client=HttpModelClient(max_tokens=6000,timeout=110,require_complete=True)
    runs={}
    for kind in ['good','bad']:
        result=old['runs'][kind]['response'];hits={};contexts={};claims=[]
        for cid,row in result['grounding']['results'].items():
            claims.append({'claim_id':cid,'text':row['final_text']})
            hits[cid]=row['retrieved_sources'];s=hits[cid][0]
            contexts[cid]={'candidate_id':s['candidate_id'],'experience_id':s['experience_id'],'project':s['title']}
        start=time.monotonic();checked=AtomicVerifier(client).verify(claims,contexts,hits)
        runs[kind]={'elapsed':time.monotonic()-start,'results':checked}
        print(kind,[(k,v['relation'],v['complete']) for k,v in checked.items()],flush=True)
        (ROOT/('output/expanded-eval/dev-v2-'+client.model+'.json')).write_text(json.dumps({'runs':runs,'usage':client.usage},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
