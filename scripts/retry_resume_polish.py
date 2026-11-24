"""Retry polish against an existing isolated test run; reuse its exact source versions."""
import argparse,json,os,sys,threading,time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run',type=Path,required=True)
parser.add_argument('--grounding-cache',type=Path,required=True)
args=parser.parse_args();directory=args.run.resolve()
os.environ.update(APPLYGUARD_LOCAL_DIR=str(directory/'local'),APPLYGUARD_EVIDENCE_DIR=str(directory/'evidence'),
 APPLYGUARD_GROUNDING_DIR=str(args.grounding_cache.resolve()),APPLYGUARD_GROUNDING_MODE='off',
 APPLYGUARD_AI_BASE_URL='https://api.chatanywhere.tech/v1',APPLYGUARD_AI_MODEL='gemini-3.1-flash-lite-preview',
 APPLYGUARD_COMPLEX_AI_MODEL='gemini-3.1-flash-lite-preview',APPLYGUARD_AI_TIMEOUT='45',APPLYGUARD_AI_MAX_TOKENS='8192')
from scripts.run_grounded import configure
from backend import app
from backend.services.local_store import load_resume_draft
body=json.loads((directory/'workflow-request.json').read_text(encoding='utf-8'))
body['local_only']=False
configure()
server=app.create_server('127.0.0.1',0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
started=time.monotonic()
try:
 request=Request(f'http://127.0.0.1:{server.server_port}/api/v1/resume/polish',json.dumps(body).encode(),{'Content-Type':'application/json'})
 try:
  with build_opener(ProxyHandler({})).open(request,timeout=300) as response:result=json.load(response);status=response.status
 except HTTPError as error:status=error.code;result=json.load(error)
 output=directory/('polish-retry-'+time.strftime('%H%M%S')+'.json')
 output.write_text(json.dumps({'http':status,'seconds':round(time.monotonic()-started,2),'response':result},ensure_ascii=False,indent=2),encoding='utf-8')
 ground=result.get('grounding') or {}
 print(json.dumps({'http':status,'seconds':round(time.monotonic()-started,2),'error':ground.get('error') or result.get('error'),
  'upstream':(ground.get('polish_source') or {}).get('name'),
  'proposals':[{k:row.get(k) for k in ('original_text','proposed_text','proposal_notice','state')} for row in ground.get('results',{}).values()],
  'report':str(output)},ensure_ascii=False),flush=True)
finally:server.shutdown();server.server_close();thread.join()
