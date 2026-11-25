"""Exercise model-backed review, export and interview APIs on an isolated sample."""
import getpass, hashlib, json, os, sys, threading
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'scripts')]
from start_recording_workspace import configure
from session_budget import install
out=root/'output/desktop-check/live-api-journey'
configure(out/'workspace',out/'sag',0)
os.environ.update(APPLYGUARD_GROUNDING_STRATEGY='vector',APPLYGUARD_AI_MAX_TOKENS='4096')
os.environ['APPLYGUARD_AI_API_KEY']=getpass.getpass('Model API key (hidden): ').strip()
install(root/'output/desktop-check/session-budget.json',Decimal('20'))
from backend import app
from backend.services.resume_draft_vault import experiences_from_resume_draft
server=app.create_server('127.0.0.1',0)
threading.Thread(target=server.serve_forever,daemon=True).start()
opener=build_opener(ProxyHandler({}))
def post(path,payload):
    req=Request(f'http://127.0.0.1:{server.server_port}/api/v1/{path}',json.dumps(payload,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
    try:
        with opener.open(req,timeout=420) as res:return {'http':res.status,**json.load(res)}
    except HTTPError as exc:
        try:return {'http':exc.code,**json.load(exc)}
        except Exception:return {'http':exc.code}
try:
    text='在模拟项目中使用 Python 实现模型评测流程，整理测试样本并分析错误类型。'
    form={'candidateId':'cand_journey','basic':{},'education':[],'awards':[],'internships':[],
          'projects':[{'id':'synthetic','title':'模型评测模拟项目','description':text}], 'extras':{}}
    claim=experiences_from_resume_draft(form)[0]['claims'][0]
    jd='算法工程师岗位职责：负责构建模型评测流程，整理测试数据，分析模型错误。任职要求：熟悉 Python，具备机器学习与评测经验。'
    payload={'candidate_id':'cand_journey','application_id':'app_journey','resume_draft':form,'jd_text':jd,
             'claims':[{'claim_id':claim['claim_id'],'text':text}],'grounding_mode':'sag_atomic','local_only':False}
    report={}
    polished=post('resume/polish',payload)
    ground=polished.get('grounding',{}); row=ground.get('results',{}).get(claim['claim_id'],{})
    report['polish']={'http':polished['http'],'error':polished.get('error') or ground.get('error'),
                      'rewritten':bool(row.get('proposed_text') and row['proposed_text']!=text),
                      'suggestion':row.get('proposed_text'),'state':row.get('state')}
    final_hash=hashlib.sha256(text.encode()).hexdigest()
    personal=post('resume/export',{**payload,'human_confirmed':True,'acknowledge_unverified':True,
                                  'confirmed_text_sha256':final_hash,'export_policy':'user_confirmed'})
    report['personal_export']={'http':personal['http'],'matches':personal.get('text')==text,'error':personal.get('error')}
    strict=post('resume/export',{**payload,'human_confirmed':True,'export_policy':'verified'})
    report['strict_export']={'http':strict['http'],'error':strict.get('error')}
    interview=post('interview/generate',{'jd_text':jd,'resume':{'projects':[{'title':'模型评测模拟项目','description':text}]}})
    report['interview']={'http':interview['http'],'questions':len(interview.get('questions',[])),
                         'has_practice':bool(interview.get('practice')),'error':interview.get('error')}
    out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
finally:
    server.shutdown();server.server_close()
