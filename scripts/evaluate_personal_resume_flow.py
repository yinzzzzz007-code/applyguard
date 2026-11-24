"""Run one user-authorized CV flow with isolated data and explicitly selected sources.

Raw source text and personal output stay in the chosen gitignored output directory.
The API key is read from the process environment or hidden input and is never saved.
"""
from __future__ import annotations
import argparse,base64,copy,getpass,hashlib,json,os,re,sys,threading,time,zipfile
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8',errors='replace')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',type=Path,required=True)
    parser.add_argument('--evidence-root',type=Path,required=True)
    parser.add_argument('--github-user',default='')
    parser.add_argument('--github-email',default='')
    parser.add_argument('--repository',default='')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--all-claims',action='store_true')
    parser.add_argument('--project-match',default='')
    parser.add_argument('--award-match',default='')
    parser.add_argument('--interview',action='store_true')
    parser.add_argument('--grounding-cache',type=Path)
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    os.environ.update(APPLYGUARD_LOCAL_DIR=str(output/'local'),APPLYGUARD_EVIDENCE_DIR=str(output/'evidence'),
        APPLYGUARD_GROUNDING_DIR=str((args.grounding_cache or output/'grounding').resolve()),APPLYGUARD_GROUNDING_MODE='off',
        APPLYGUARD_AI_BASE_URL='https://api.chatanywhere.tech/v1',APPLYGUARD_AI_MODEL='gemini-3.1-flash-lite-preview',
        APPLYGUARD_COMPLEX_AI_MODEL='gemini-3.1-flash-lite-preview',APPLYGUARD_AI_TIMEOUT='45',
        APPLYGUARD_AI_MAX_TOKENS='8192',APPLYGUARD_GROUNDING_TIMEOUT='60')
    temp=output/'temp';temp.mkdir(exist_ok=True);os.environ['TEMP']=os.environ['TMP']=str(temp)
    if args.live and not os.getenv('APPLYGUARD_AI_API_KEY'):
        os.environ['APPLYGUARD_AI_API_KEY']=getpass.getpass('Model key (hidden, process only): ').strip()
    from backend import app
    from backend.services import evidence_workspace as ew,agent_bridge
    from backend.services.resume_draft_vault import experiences_from_resume_draft
    from backend.services.local_store import save_resume_draft
    from backend.services.job_recommendation import rank_jobs
    report={'scope':'Authorized personal CV with explicitly selected evidence; not an accuracy benchmark. Claims without supporting evidence remain unresolved.',
            'model':os.environ['APPLYGUARD_AI_MODEL'],'stages':{}}
    def save(name,value):
        (output/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def record(name,value):
        report['stages'][name]=value;save('report',report);print(name+': '+json.dumps(value,ensure_ascii=False)[:1100],flush=True)
    server=app.create_server('127.0.0.1',0);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base='http://127.0.0.1:'+str(server.server_port)
    opener=build_opener(ProxyHandler({}))
    def post(path,body):
        started=time.monotonic()
        request=Request(base+'/api/v1/'+path,json.dumps(body,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
        try:
            with opener.open(request,timeout=600) as response:return response.status,json.load(response),round(time.monotonic()-started,2)
        except HTTPError as exc:return exc.code,json.load(exc),round(time.monotonic()-started,2)
    try:
        status,parsed,elapsed=post('resume/parse',{'filename':args.resume.name,'content_base64':base64.b64encode(args.resume.read_bytes()).decode(),'parse_mode':'offline'})
        # Current API uses pdf_base64; fail explicitly rather than silently feeding a mock.
        if status!=200:
            status,parsed,elapsed=post('resume/parse',{'filename':args.resume.name,'pdf_base64':base64.b64encode(args.resume.read_bytes()).decode(),'parse_mode':'offline'})
        save('parsed-resume',parsed)
        if status!=200:raise ValueError('Resume parsing failed: '+str(parsed))
        form=parsed['form'];form['candidateId']='cand_personal_flow'
        form.setdefault('intention',{})
        for group in ('education','internships','projects','awards'):
            form.setdefault(group,[])
            for i,row in enumerate(form[group]):row['id']=f'{group}_{i}'
        save_resume_draft(form)
        record('import_and_save',{'http':status,'characters':parsed['char_count'],'counts':{g:len(form[g]) for g in ('education','projects','internships','awards')}})
        workspace=ew.create_workspace('Authorized personal resume flow')
        award=next(row for row in form['awards'] if args.award_match.casefold() in row['name'].casefold())
        project=next(row for row in form['projects'] if args.project_match.casefold() in row['title'].casefold())
        excerpts=[]
        for file in args.evidence_root.glob('*.docx'):
            with zipfile.ZipFile(file) as archive:node=ET.fromstring(archive.read('word/document.xml'))
            lines=[''.join(p.itertext()).strip() for p in node.findall('.//w:p',{'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'})]
            # Only the awards summary; exclude unrelated demographic, financial and academic fields.
            selected=[line for line in lines if line.startswith('主要奖项')]
            if selected:excerpts.append({'path':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'text':'\n'.join(selected)})
        if not excerpts:raise ValueError('No relevant award summary found in the explicitly selected folder')
        save('local-source-excerpts',excerpts)
        source_text='\n\n'.join(json.dumps({k:v for k,v in source.items() if k!='text'},ensure_ascii=False)+'\n'+source['text'] for source in excerpts)
        records=ew.import_files(workspace['workspace_id'],[{'relative_path':'award-original-excerpts.md','content_base64':base64.b64encode(source_text.encode()).decode()}])
        evidence=records['files'][0]['evidence_id']
        ew.review_evidence(evidence,{'normalized_fields':{},'review_state':'REVIEWED'})
        ew.create_link({'target_type':'award','target_id':award['id'],'evidence_id':evidence})
        record('local_evidence',{'source_files':len(excerpts),'imported':len(records['files']),'number_consistency':'Review original numbers in the local excerpts; conflicts are not automatically resolved','authenticity':'User supplied documents; not independently authenticated'})
        if args.github_user:
            try:
                repos=agent_bridge.ui_call({'action':'github_discover','query':args.github_user})
                save('public-repositories',repos);record('github_public_discovery',{'repositories':len(repos['items']),'private_access':False})
            except ValueError as exc:record('github_public_discovery',{'passed':False,'error':str(exc),'private_access':False})
        if args.github_email:
            try:
                accounts=agent_bridge.ui_call({'action':'github_discover','query':args.github_email,'kind':'email'})
                save('public-email-candidates',accounts);record('github_public_email',{'candidate_accounts':len(accounts['accounts']),'notice':accounts['notice']})
            except ValueError as exc:record('github_public_email',{'passed':False,'error':str(exc)})
        if args.repository:
            pinned=agent_bridge.ui_call({'action':'github_pin','repo':args.repository})
            from urllib.parse import quote
            url=f"https://raw.githubusercontent.com/{args.repository}/{pinned['sha']}/README.md"
            with build_opener().open(Request(url,headers={'User-Agent':'ApplyGuard-personal-flow'}),timeout=30) as response:raw=response.read(1000001)
            if len(raw)>1000000:raise ValueError('Selected public README exceeds limit')
            imported=ew.import_files(workspace['workspace_id'],[{'relative_path':'ledgerdemo-public-readme.md','content_base64':base64.b64encode(raw).decode()}])
            ev=imported['files'][0]['evidence_id'];ew.review_evidence(ev,{'normalized_fields':{},'review_state':'REVIEWED'})
            ew.create_link({'target_type':'project','target_id':project['id'],'evidence_id':ev})
            record('github_evidence',{'repository':pinned['repo'],'sha':pinned['sha'],'path':'README.md','notice':'Project documentation does not establish every individual contribution.'})
        items=experiences_from_resume_draft(form)
        wanted={project['id'],award['id']}
        claims=[{'claim_id':claim['claim_id'],'text':claim['text']} for item in items if args.all_claims or any(item['experience_id']=='exp_'+v.lower() for v in wanted) for claim in item['claims']]
        if not claims:raise ValueError('No imported claims to test')
        record('claim_scope',{'claims':len(claims),'all_imported_claims':args.all_claims})
        request={'candidate_id':form['candidateId'],'application_id':'app_personal_flow','resume_draft':form,
                 'jd_text':'大模型与智能体研发实习生：使用 Python、PyTorch 开发和评估 LLM，进行 LoRA SFT 训练、数据处理、RAG 检索与权限控制。',
                 'claims':claims,'grounding_mode':'sag_atomic','local_only':True}
        save('workflow-request',request)
        status,full,elapsed=post('workflow/mock',{**request,'parse_mode':'offline','local_only':True,'grounding_mode':'off'})
        save('workflow-complete-local',full)
        record('jd_match_ats',{'http':status,'seconds':elapsed,'jd_requirements':len((full.get('parsed_jd') or {}).get('requirements',[])),
            'resume_claims':len(full.get('resume_claims',[])),'ats_fields':len((full.get('ats_form_mapping') or {}).get('fields',[])),
            'trace':[row.get('step') for row in full.get('step_trace',[])]})
        status,local,elapsed=post('workflow/reverify',request);save('workflow-local',local)
        record('local_workflow',{'http':status,'seconds':elapsed,'states':[row['state'] for row in local.get('claim_verification',[])]})
        if args.live:
            print('Running real Gemini polish and atomic checks...',flush=True)
            status,polished,elapsed=post('resume/polish',{**request,'local_only':False})
            save('polish-live',polished)
            ground=polished.get('grounding') or {}
            record('live_polish',{'http':status,'seconds':elapsed,'error':ground.get('error') or polished.get('error'),
                'states':[row['state'] for row in polished.get('claim_verification',[])],
                'upstream':(ground.get('polish_source') or {}).get('name'),
                'proposals':[{k:row.get(k) for k in ('original_text','proposed_text','proposal_notice','state')} for row in ground.get('results',{}).values()]})
            status,strict,elapsed=post('resume/export',{**request,'local_only':False,'human_confirmed':True,'export_policy':'verified'})
            save('strict-export',strict);record('strict_export',{'http':status,'seconds':elapsed,'error':strict.get('error'),'passed':status==200})
        if args.live and args.interview:
            interview_form={'name':form['basic'].get('name',''),'skills':form.get('extras',{}).get('skills',''),'summary':form.get('extras',{}).get('summary',''),
                'education':form['education'],'projects':form['projects'],'internships':form['internships']}
            status,guide,elapsed=post('interview/generate',{'jd_text':request['jd_text'],'resume':interview_form})
            save('interview-live',guide);record('interview',{'http':status,'seconds':elapsed,'error':guide.get('error'),'questions':len(guide.get('questions',[])),
                'project_coverage':sorted({row.get('project_index') for row in guide.get('questions',[]) if row.get('project_index')})})
        text='\n'.join(row['text'] for row in claims)
        status,exported,elapsed=post('resume/export',{**request,'human_confirmed':True,'acknowledge_unverified':True,
            'export_policy':'user_confirmed','confirmed_text_sha256':hashlib.sha256(text.encode()).hexdigest()})
        save('user-export',exported)
        if status==200:(output/'user-confirmed-draft.txt').write_text(exported['text'],encoding='utf-8')
        record('user_confirmed_export',{'http':status,'material_support':exported.get('material_support'),'no_external_submission':True})
        with opener.open('http://127.0.0.1:8000/api/v1/jobs',timeout=15) as response:jobs=json.load(response)['items']
        from backend.services.job_matching import match_job
        for job in jobs:
            match=match_job(job,form);job.update(match_score=match['score'],match_level=match['level'])
        state=rank_jobs(jobs,form,{})
        deadline=time.monotonic()+120
        while state['state']=='loading' and time.monotonic()<deadline:
            time.sleep(.5);state=rank_jobs(jobs,form,{})
        ordered=sorted(jobs,key=lambda job:job['recommendation_rank'])
        ranking=[{'title':job['title'],'company':job['company'],'rank':job['recommendation_rank']+1,'score':job['recommendation_score'],'reasons':job['recommendation_reasons']} for job in ordered]
        save('job-ranking',ranking)
        record('semantic_recommendation',{'state':state['state'],'jobs':len(jobs),'top_five':ranking[:5],
            'materials_roles':[row for row in ranking if '材料' in row['title']]})
        report['completed']=True;save('report',report)
    finally:
        server.shutdown();server.server_close();worker.join()
    print('REPORT '+str(output/'report.json'),flush=True)

if __name__=='__main__':main()
