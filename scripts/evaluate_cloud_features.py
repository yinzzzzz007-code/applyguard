"""Exercise cloud features with one authorized CV and a bounded Gemini test budget.

Use an existing isolated personal-flow directory. Never saves the API key, changes
the saved resume, publishes material, or substitutes recorded model responses.
"""
from __future__ import annotations
import argparse,base64,getpass,json,os,subprocess,sys,threading,time
from decimal import Decimal
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8',errors='replace')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--resume',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--grounding-cache',type=Path,required=True)
    parser.add_argument('--budget-cny',type=float,default=10)
    parser.add_argument('--harness',action='store_true')
    parser.add_argument('--refchecker-fixture',action='store_true',help='One author-labelled fictional atom; isolates the optional checker transport from upstream verification')
    parser.add_argument('--only',action='append',choices=['strict_export_conflicting_draft','user_confirmed_draft_export','ai_resume_parse','ai_jd_and_semantic_match','atomic_reverification','ai_resume_polish','strict_export_selected_award','interview','optional_job_ai_explanation','optional_refchecker_audit','harness_tool_flow'])
    parser.add_argument('--claim-id',action='append',help='Limit review and polish to these claim IDs; repeat for multiple items')
    parser.add_argument('--review-edits',type=Path,help='Optional JSON object mapping selected claim IDs to simulated reviewer edits; changes only the request')
    parser.add_argument('--bind-target',action='store_true',help='Validate the saved target job using the isolated job database')
    parser.add_argument('--model-timeout',type=int,default=60)
    args=parser.parse_args()
    wanted=set(args.only or ['ai_resume_parse','ai_jd_and_semantic_match','atomic_reverification','ai_resume_polish','strict_export_selected_award','interview','optional_job_ai_explanation','optional_refchecker_audit','harness_tool_flow'])
    if not 0<args.budget_cny<=10:parser.error('budget must be within 0–10 CNY')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    run=args.run.resolve();key=getpass.getpass('ChatAnywhere key (hidden, process only): ').strip()
    os.environ.update(APPLYGUARD_LOCAL_DIR=str(run/'local'),APPLYGUARD_EVIDENCE_DIR=str(run/'evidence'),
        APPLYGUARD_GROUNDING_DIR=str(args.grounding_cache.resolve()),APPLYGUARD_GROUNDING_MODE='off',
        APPLYGUARD_AI_API_KEY=key,APPLYGUARD_AI_BASE_URL='https://api.chatanywhere.tech/v1',
        APPLYGUARD_AI_MODEL='gemini-3.1-flash-lite-preview',APPLYGUARD_COMPLEX_AI_MODEL='gemini-3.1-flash-lite-preview',
        APPLYGUARD_STRONG_AI_MODEL='gemini-3.1-flash-lite-preview',APPLYGUARD_AI_TIMEOUT=str(args.model_timeout),
        APPLYGUARD_AI_MAX_TOKENS='8192',APPLYGUARD_JOB_AI_MATCH='true',APPLYGUARD_JOBS_AUTO_REFRESH='false')
    temp=output/'temp';temp.mkdir();os.environ['TEMP']=os.environ['TMP']=str(temp)
    report={'budget_cny':args.budget_cny,'model':os.environ['APPLYGUARD_AI_MODEL'],'stages':{},'text_calls':[],
        'notice':'Real calls; one personal resume with selected sources. Missing evidence is not waived. Source authenticity is not independently established.'}
    lock=threading.Lock();reserved=Decimal('0');non_text_reserve=Decimal('1.5')
    def save(name,value):
        (output/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def balance():
        request=Request('https://api.chatanywhere.tech/v1/query/balance',b'{}',{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with urlopen(request,timeout=20) as response:data=json.load(response)
        data=data.get('data',data)
        return Decimal(str(data['apiKeyUsed']))
    initial=balance();report['key_used_ca_before']=str(initial)
    if initial>=Decimal(str(args.budget_cny)):raise SystemExit('Key cumulative usage already reaches this conservative test cap; stopped before model calls.')
    from backend.services.model_client import HttpModelClient,ModelFailure
    original=HttpModelClient._complete
    def bounded(client,system_prompt,user_prompt,*,schema=None):
        nonlocal reserved
        if client.model!=report['model']:raise ModelFailure('Test model differs from the authorized Gemini model',retryable=False)
        upper=len((system_prompt+user_prompt+json.dumps(schema or {})).encode('utf-8'))+4096
        amount=Decimal(upper)*Decimal('.000001')+Decimal(client.max_tokens)*Decimal('.000006')
        with lock:
            if initial+reserved+amount+non_text_reserve>Decimal(str(args.budget_cny)) or len(report['text_calls'])>=120:
                raise ModelFailure('测试预算上限已达到；已在请求前停止。',retryable=False)
            reserved+=amount
            row={'reserved_ca':float(amount),'input_bytes_upper':upper,'max_output_tokens':client.max_tokens,'status':'running'}
            report['text_calls'].append(row);report['reserved_text_ca']=float(reserved);save('report',report)
        try:
            result=original(client,system_prompt,user_prompt,schema=schema)
            row.update(status='complete',shared_client_usage_snapshot=dict(client.usage))
            return result
        except Exception as exc:
            row.update(status='failed',error_type=type(exc).__name__,http_status=getattr(exc,'http_status',None),retryable=getattr(exc,'retryable',None))
            raise
        finally:
            with lock:save('report',report)
    HttpModelClient._complete=bounded
    from backend import app
    from backend.services.local_store import load_resume_draft,load_workflow_draft
    form=load_resume_draft();saved=load_workflow_draft()
    workflow=saved['workflow']
    request={'candidate_id':form['candidateId'],'application_id':workflow['application_id'],
        'resume_draft':form,'jd_text':saved['jd'],'claims':[{k:c[k] for k in ('claim_id','text')} for c in workflow['resume_claims']],
        'local_only':False,'grounding_mode':'sag_atomic'}
    if args.bind_target and workflow.get('target_job'):
        request['target_job']=workflow['target_job']
    if args.claim_id:
        requested=set(args.claim_id)
        request['claims']=[claim for claim in request['claims'] if claim['claim_id'] in requested]
        found={claim['claim_id'] for claim in request['claims']}
        if found != requested:raise ValueError('Unknown claim IDs: '+', '.join(sorted(requested-found)))
    if args.review_edits:
        edits=json.loads(args.review_edits.read_text(encoding='utf8'))
        selected={row['claim_id'] for row in request['claims']}
        if not isinstance(edits,dict) or not set(edits)<=selected:
            raise ValueError('Review edits must map selected claim IDs to text')
        if any(not isinstance(text,str) or not 0<len(text.strip())<=420 for text in edits.values()):
            raise ValueError('Review edits must contain 1–420 characters')
        for row in request['claims']:
            row['text']=edits.get(row['claim_id'],row['text'])
    save('request',request)
    server=app.create_server('127.0.0.1',0);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    opener=build_opener(ProxyHandler({}));base=f'http://127.0.0.1:{server.server_port}/api/v1/'
    def post(path,body):
        start=time.monotonic();req=Request(base+path,json.dumps(body).encode(),{'Content-Type':'application/json'})
        try:
            with opener.open(req,timeout=600) as response:status,result=response.status,json.load(response)
        except HTTPError as error:status,result=error.code,json.load(error)
        return status,result,round(time.monotonic()-start,2)
    def record(name,status,result,elapsed,extra):
        save(name,result)
        used=balance();report['key_used_ca_after']=str(used);report['new_spend_ca']=str(used-initial)
        report['stages'][name]={'http':status,'seconds':elapsed,**extra}
        save('report',report);print(name+': '+json.dumps(report['stages'][name],ensure_ascii=False)[:1300],flush=True)
        if used>=Decimal(str(args.budget_cny)):raise RuntimeError('Budget reached; no further requests')
    try:
        if 'ai_resume_parse' in wanted:
            status,result,elapsed=post('resume/parse',{'pdf_base64':base64.b64encode(args.resume.read_bytes()).decode(),'filename':args.resume.name,'parse_mode':'dynamic'})
            record('ai_resume_parse',status,result,elapsed,{'extractor':result.get('extractor'),'notice':result.get('notice'),'field_issues':result.get('model_field_issues',[]),'counts':{k:len(result.get('form',{}).get(k,[])) for k in ('education','projects','internships','awards')},'warnings':result.get('warnings',[])})
        if 'ai_jd_and_semantic_match' in wanted:
            status,result,elapsed=post('workflow/mock',{**request,'parse_mode':'dynamic','grounding_mode':'off'})
            record('ai_jd_and_semantic_match',status,result,elapsed,{'modes':result.get('component_modes'),'trace':[{k:s.get(k) for k in ('step','fallback_reason')} for s in result.get('step_trace',[])]})
        if 'atomic_reverification' in wanted:
            status,result,elapsed=post('workflow/reverify',request)
            record('atomic_reverification',status,result,elapsed,{'error':(result.get('grounding') or {}).get('error'),'states':[{k:v.get(k) for k in ('claim_id','state')} for v in result.get('claim_verification',[])]})
        if 'ai_resume_polish' in wanted:
            status,result,elapsed=post('resume/polish',request)
            ground=result.get('grounding') or {}
            rows=ground.get('results') or {}
            experience_rows=[row for row in rows.values() if row.get('verification_scope')!='personal']
            conflicts=[row for row in experience_rows if (row.get('original_check') or {}).get('relation')=='CONTRADICTED']
            eligible=[row for row in experience_rows if row not in conflicts]
            count=sum(bool(row.get('proposed_text')) for row in eligible)
            from backend.services.asu_resume import polish_quality
            changed=sum(bool(row.get('proposed_text')) and not polish_quality(row.get('original_text',''),row.get('proposed_text')) for row in eligible)
            passed=(status==200 and not ground.get('error') and set(rows)=={claim['claim_id'] for claim in request['claims']} and bool(experience_rows) and changed==len(eligible) and all(row.get('final_text')==row.get('original_text') and row.get('proposed_text') in (None,row.get('original_text')) for row in conflicts))
            record('ai_resume_polish',status,result,elapsed,{'passed':passed,'error':ground.get('error'),'failure_stage':ground.get('failure_stage'),'upstream':(ground.get('polish_source') or {}).get('name'),'proposals':count,'changed_proposals':changed,'expected_proposals':len(eligible),'conflicts_skipped':len(conflicts),'wording_reviews':sum(bool(v.get('wording_review')) for v in rows.values())})
        if 'strict_export_conflicting_draft' in wanted:
            status,result,elapsed=post('resume/export',{**request,'human_confirmed':True,'export_policy':'verified'})
            error=result.get('error') or {}
            passed=(status==422 and error.get('code')=='VALIDATION_ERROR' and '全部事实通过原子核验' in error.get('message','') and 'text' not in result)
            record('strict_export_conflicting_draft',status,result,elapsed,{'passed':passed,'claims':len(request['claims']),'error_code':error.get('code'),'message':error.get('message')})
        if 'user_confirmed_draft_export' in wanted:
            import hashlib
            digest=hashlib.sha256('\n'.join(c['text'] for c in request['claims']).encode()).hexdigest()
            status,result,elapsed=post('resume/export',{**request,'human_confirmed':True,'acknowledge_unverified':True,
                'confirmed_text_sha256':digest,'export_policy':'user_confirmed'})
            records=(result.get('review_record') or {}).get('claims',[])
            passed=(status==200 and result.get('sha256')==digest and result.get('material_support')=='NOT_ATOMICALLY_VERIFIED'
                and len(records)==len(request['claims']) and all(row.get('material_support')=='NOT_ATOMICALLY_VERIFIED' for row in records))
            record('user_confirmed_draft_export',status,result,elapsed,{'passed':passed,'claims':len(records),'material_support':result.get('material_support'),'scope':'Simulated confirmation on the isolated test draft'})
        if 'strict_export_selected_award' in wanted:
            # One corrected award proves the positive strict-export branch without inventing support for other projects.
            award=next((c for c in request['claims'] if c['claim_id'].startswith('claim_awards_') and '/' in c['text']),None)
            if award:
                status,result,elapsed=post('resume/export',{**request,'claims':[award],'human_confirmed':True,'export_policy':'verified'})
                record('strict_export_selected_award',status,result,elapsed,{'passed':status==200,'error':result.get('error'),'scope':'Selected corrected award only; other resume claims are excluded from this subtest'})
        if 'interview' in wanted:
            resume={'name':form['basic'].get('name',''),'skills':form.get('extras',{}).get('skills',''),'summary':form.get('extras',{}).get('summary',''),
                'education':form['education'],'projects':form['projects'],'internships':form['internships']}
            status,result,elapsed=post('interview/generate',{'jd_text':request['jd_text'],'resume':resume})
            record('interview',status,result,elapsed,{'questions':len(result.get('questions',[])),'coverage':sorted({q['project_index'] for q in result.get('questions',[]) if q.get('project_index')}),'error':result.get('error')})
        if 'optional_job_ai_explanation' in wanted:
            from backend.services.job_matching import explain_job
            start=time.monotonic();result=explain_job({'title':'Python 后端研发实习生（功能测试样例）','requirements':request['jd_text']},{'score':60,'level':'medium','reasons':['功能测试给定的规则结果'],'missing':[]})
            record('optional_job_ai_explanation',200,result,round(time.monotonic()-start,2),{'has_ai_explanation':bool(result.get('ai_explanation')),'scope':'Synthetic rule result, real model explanation; not a job ranking accuracy test'})
        if 'optional_refchecker_audit' in wanted:
            from backend.services.refchecker_review import review_refchecker
            if args.refchecker_fixture:
                text='Demo Applicant built a Python document search API for Atlas and wrote 12 Python unit tests.'
                reference=(ROOT/'eval/public-demo/atlas-evidence.md').read_text(encoding='utf-8')
                if text not in reference:raise ValueError('The labelled fixture quote changed')
                check={'relation':'SUPPORTED','complete':True,'atoms':[{'text':text,'relation':'SUPPORTED','citations':[{'quote':text}]}]}
                elapsed=0;status=200
                scope='Author-labelled fictional atom; real optional checker call only, not fresh-verification end-to-end or model accuracy'
            else:
                award=next(c for c in request['claims'] if c['claim_id'].startswith('claim_awards_') and '/' in c['text'])
                text=award['text']
                status,current,elapsed=post('workflow/reverify',{**request,'claims':[award]})
                check=(current.get('grounding') or {}).get('results',{}).get(award['claim_id'],{})
                scope='One freshly verified corrected award; optional audit cannot grant verification'
            start=time.monotonic()
            result=review_refchecker(HttpModelClient(task='complex',max_tokens=512),text,check)
            record('optional_refchecker_audit',status,result,round(elapsed+time.monotonic()-start,2),
                {'relation':result['relation'],'atomic_labels':result.get('atomic_labels',[]),'scope':scope})
        if 'harness_tool_flow' in wanted:
            if args.harness:
                # The shared text budget reserves a separate 1.5 CA for retrieval and this one 240-second tool run.
                start=time.monotonic();probe=subprocess.run([sys.executable,str(ROOT/'scripts/harness_agent_probe.py'),'--timeout','240'],cwd=ROOT,env=os.environ,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=270)
                (output/'harness.log').write_text(probe.stdout.replace(key,'<redacted>'),encoding='utf-8')
                record('harness_tool_flow',200,{'exit_code':probe.returncode},round(time.monotonic()-start,2),{'passed':probe.returncode==0})
        from scripts.summarize_cloud_features import outcome
        report['missing_stages']=sorted(wanted-set(report['stages']))
        report['stage_outcomes']={name:outcome(name,row) for name,row in report['stages'].items()}
        report['completed']=not report['missing_stages'] and all(value=='COMPLETED' for value in report['stage_outcomes'].values())
        save('report',report)
    finally:
        HttpModelClient._complete=original
        server.shutdown();server.server_close();worker.join()
    print('REPORT '+str(output/'report.json'),flush=True)
    return 0 if report['completed'] else 1

if __name__=='__main__':raise SystemExit(main())
