"""Small explicitly started live probe; synthetic facts only, hidden in-memory key."""
import argparse,getpass,json,os,sys,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.services.grounded_workflow import GroundingService
from backend.services.model_client import HttpModelClient,ModelFailure

class AllSources:
    def retrieve_many(self,queries,sources,candidate_id):
        return {q['claim_id']:[s for s in sources if s['source_id'] in q['source_ids']] for q in queries}

class BoundedClient(HttpModelClient):
    attempts=0
    def _complete(self,*args,**kwargs):
        self.attempts+=1
        if self.attempts>12:raise ModelFailure('Live probe request limit reached',retryable=False)
        return super()._complete(*args,**kwargs)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');parser.add_argument('--serve-only',action='store_true');args=parser.parse_args()
    key=getpass.getpass('API key (hidden, memory only): ').strip()
    os.environ['APPLYGUARD_AI_API_KEY']=key
    os.environ['APPLYGUARD_AI_BASE_URL']='https://api.chatanywhere.tech/v1'
    os.environ['APPLYGUARD_AI_MODEL']='gpt-4.1-mini'
    if args.serve_only:
        os.environ['APPLYGUARD_PORT']='8897'
        from backend.app import main as serve
        serve()
        return 0
    rows=[('atlas','Alex wrote Python interface tests for Atlas; the tests ran offline, and Alex did not deploy the service.'),
          ('maple','林同学在枫叶项目中负责SQL分析与方案测算，测算预计成本下降12%，尚未实施；项目由周同学负责。'),
          ('mosaic','苏同学负责拼图项目的评测，准确率从80%变为84%，即提高4个百分点；未参与模型训练。')]
    claims=[];items=[]
    for name,text in rows:
        claim={'claim_id':'claim_'+name,'text':text,'evidence_ids':['ev_'+name]};claims.append(claim)
        items.append({'candidate_id':'cand_synthetic','experience_id':'exp_'+name,'title':name,'organization':'虚构实验组',
            'claims':[dict(claim)],'evidence_sources':[{'evidence_id':'ev_'+name,'description':text,
             'verification_status':'VERIFIED','confidence':1,'type':'DOCUMENT','_version':'synthetic-v1'}]})
    zone=timezone(timedelta(hours=8));started=datetime.now(zone)
    directory=ROOT/'output/test-reports'/(started.strftime('%Y%m%d_%H%M%S_%f')+'_asu-live-3');directory.mkdir(parents=True)
    client=BoundedClient(max_tokens=3000,timeout=90,require_complete=True)
    tick=time.monotonic()
    final,checks,grounding=GroundingService(retriever=AllSources(),model=client).run(claims,items,'cand_synthetic','sag_atomic',
        jd='后端与数据分析岗位，突出有证据的技术、交付和个人贡献。',polish=True)
    report={'started_at':started.isoformat(),'finished_at':datetime.now(zone).isoformat(),'elapsed_seconds':round(time.monotonic()-tick,3),
        'status':'FAIL' if grounding['error'] or not grounding.get('polish_source') else 'COMPLETED_REQUIRES_REVIEW',
        'model':'gpt-4.1-mini','cases':3,'usage':client.usage,'attempts':client.attempts,'grounding':grounding,'checks':checks,
        'limitations':['Synthetic only; manual inspection is descriptive, not independent benchmark accuracy.',
                       'AllSources fixture isolates writing/verification; no SAG engine or Harness evaluated here.']}
    (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:report[k] for k in ['status','cases','elapsed_seconds','usage','attempts']}),flush=True)
    print('REPORT '+str(directory),flush=True)
    if args.serve:
        os.environ['APPLYGUARD_PORT']='8897'
        from backend.app import main as serve
        serve()
    return 0 if report['status']!='FAIL' else 1

if __name__=='__main__':raise SystemExit(main())
