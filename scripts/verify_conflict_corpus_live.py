"""Run real cloud verification on the user's locally supplied simulated conflicts."""
import base64, getpass, json, os, sys, threading, time, traceback
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from start_recording_workspace import configure
from session_budget import install

root=ROOT/'output'/'desktop-check'/'live-conflict-review'
root.mkdir(parents=True,exist_ok=True)
configure(root/'workspace',root/'sag',0)
os.environ.update(APPLYGUARD_GROUNDING_STRATEGY='vector',APPLYGUARD_AI_MAX_TOKENS='4096',
                  APPLYGUARD_EMBEDDING_MODEL='text-embedding-3-small',APPLYGUARD_OCR_BACKEND='rapidocr')
os.environ['APPLYGUARD_AI_API_KEY']=getpass.getpass('Model API key (hidden): ').strip()
if not os.environ['APPLYGUARD_AI_API_KEY']: raise SystemExit('No API key')
install(ROOT/'output'/'desktop-check'/'session-budget.json',Decimal('20'))
from backend import app
from backend.services import evidence_workspace as ew
from backend.services.resume_draft_vault import experiences_from_resume_draft

server=app.create_server('127.0.0.1',0)
threading.Thread(target=server.serve_forever,daemon=True).start()
opener=build_opener(ProxyHandler({}))
def post(path,payload):
    req=Request(f'http://127.0.0.1:{server.server_port}/api/v1/{path}',
                json.dumps(payload,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
    try:
        with opener.open(req,timeout=420) as res:return json.load(res)
    except HTTPError as exc:
        try:return {'http_status':exc.code,**json.load(exc)}
        except Exception:return {'http_status':exc.code,'error':'HTTP request failed'}

pack=lambda b:base64.b64encode(b).decode()
cases=[(1,2,('编译器','12%')),(2,5,('Capstone',)),(3,8,('Innovator-VL',)),
       (4,13,('CoachWell',)),(5,15,('Llama3',)),(6,18,('Agent','翻译')),
       (7,21,('Copilot','SQL')),(8,27,('Sentiment','评论')),(10,32,('2021','ByteDance')),
       (11,35,('Gym Reservation',)),(12,43,('Github Visualization','Git log')),
       (13,45,('Software Development Engineer Il','95%')),(14,48,('GEMM','CUDAFP32'))]
metric_terms={1:'12%',2:'92%',3:'500万',4:'30%',5:'GQA',6:'Chroma',7:'92%',8:'0.75',
              10:'10%',11:'1l AM',12:'D3',13:'95%',14:'74.56'}
corpus=json.loads((ROOT/'output/desktop-check/conflict-corpus-final-private.json').read_text(encoding='utf8'))
source=Path(r'E:\pdf-collection\01_AI-Infra_演示材料')
report=json.loads((root/'report-private.json').read_text(encoding='utf8')) if (root/'report-private.json').exists() else []
only={int(value) for value in sys.argv[1:]}
def save(): (root/'report-private.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
try:
 for number,folder_number,terms in cases:
    if only and number not in only:continue
    started=time.monotonic(); result={'case':number,'material_folder_number':folder_number}
    try:
        parsed=next(r for r in corpus if r['case']==number)
        choices=[]
        for collection in ('projects','internships'):
            for item in parsed.get(collection,[]):
                text=(item.get('title','')+'\n'+item.get('description','')).casefold()
                hits=sum(t.casefold() in text for t in terms)
                if hits:choices.append((hits,collection,item))
        choices.sort(key=lambda a:a[0],reverse=True)
        if not choices:
            result.update(stage='import',error='对应项目未能从简历中提取'); report.append(result);save();print(number,'IMPORT_MISSING',flush=True);continue
        _,collection,item=choices[0]
        item=dict(item);item['id']=f'case_{number}_target'
        form={'candidateId':f'cand_conflict_{number}','basic':{},'education':[],
              'projects':[],'internships':[],'awards':[],'extras':{}}
        form[collection]=[item]
        experiences=experiences_from_resume_draft(form)
        target=experiences[0];claim=target['claims'][0]
        lines=item.get('description','').splitlines()
        hit=next((i for i,line in enumerate(lines) if metric_terms[number].casefold() in line.casefold()),None)
        if hit is None:
            result.update(stage='import',error='目标冲突细节未被 OCR 提取');report.append(result);save();print(number,'METRIC_MISSING',flush=True);continue
        excerpt='\n'.join(lines[max(0,hit-1):min(len(lines),hit+2)])
        folder=next(p for p in source.glob(f'{folder_number:02}_*') if p.is_dir())
        readme=next(folder.rglob('README.md'))
        workspace=ew.create_workspace(f'模拟冲突复测 {number}')
        imported=ew.import_files(workspace['workspace_id'],[{'relative_path':f'{folder.name}/README.md',
                                                               'content_base64':pack(readme.read_bytes())}])['files'][0]
        eid=imported['evidence_id']
        ew.review_evidence(eid,{'normalized_fields':{},'review_state':'REVIEWED'})
        post('resume/draft',form)
        link={'evidence_id':eid,'target_type':'project' if collection=='projects' else 'internship',
              'target_id':item['id']}
        try:
            ew.create_link(link)
            result['association']='automatic'
        except ValueError as exc:
            if '无法自动确认材料属于该经历' not in str(exc):raise
            ew.create_link({**link,'association_confirmed':True})
            result['association']='manually_confirmed_test_pair'
        payload={'candidate_id':form['candidateId'],'application_id':f'app_case_{number}',
                 'resume_draft':form,'jd_text':'算法工程师岗位职责：参与模型训练和系统研发，负责数据处理、性能优化与结果评估。任职要求：熟悉 Python 和深度学习，有模型训练或工程开发经验。',
                 'claims':[{'claim_id':claim['claim_id'],'text':excerpt}],
                 'grounding_mode':'sag_atomic','local_only':False}
        out=post('workflow/reverify',payload)
        grounding=out.get('grounding',{});v=grounding.get('results',{}).get(claim['claim_id'],{})
        result.update(stage='verify',title=item.get('title') or item.get('organization'),
                      status=v.get('state'),material_status=v.get('material_status'),
                      sources=len(v.get('retrieved_sources',[])),run_id=grounding.get('run_id'),
                      error=out.get('error') or grounding.get('error'),http_status=out.get('http_status'),
                      atoms=v.get('atoms',[]),original=excerpt)
        if number==3:
            empty=dict(form);empty['candidateId']='cand_no_material_case_3';empty['projects']=[dict(item,id='unlinked_3')]
            unlinked=experiences_from_resume_draft(empty)[0]['claims'][0]
            no_source=post('workflow/reverify',{**payload,'candidate_id':empty['candidateId'],'resume_draft':empty,
                'claims':[{'claim_id':unlinked['claim_id'],'text':excerpt}]})
            ng=no_source.get('grounding',{});nv=ng.get('results',{}).get(unlinked['claim_id'],{})
            result['no_material_control']={'status':nv.get('state'),'material_status':nv.get('material_status'),
                'sources':len(nv.get('retrieved_sources',[])),'error':no_source.get('error') or ng.get('error')}
    except Exception as exc:
        result.update(stage='exception',error=f'{type(exc).__name__}: {str(exc)[:240]}',traceback=traceback.format_exc())
    result['elapsed_seconds']=round(time.monotonic()-started,1)
    report.append(result);save()
    print(number,result.get('stage'),result.get('status'),result.get('error'),flush=True)
finally:
 server.shutdown();server.server_close()
