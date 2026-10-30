"""Small authorized service diagnosis; records only sanitized error information."""
import getpass,json,re,sys,urllib.request,urllib.error
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
now=datetime.now(timezone(timedelta(hours=8)))
directory=ROOT/'output/test-reports'/(now.strftime('%Y%m%d_%H%M%S_%f')+'_model-http-diagnosis');directory.mkdir(parents=True)
key=getpass.getpass('API key (hidden, memory only): ').strip()
payload={'model':'gpt-4.1-mini','temperature':0,'max_tokens':16,'messages':[{'role':'user','content':'Return JSON: {"ok":true}'}],'response_format':{'type':'json_object'}}
request=urllib.request.Request('https://api.chatanywhere.tech/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
report={'started_at':now.isoformat(),'model':'gpt-4.1-mini'}
try:
 with urllib.request.urlopen(request,timeout=45) as response:
  data=json.loads(response.read(10000));report.update(status=response.status,usage=data.get('usage'))
except urllib.error.HTTPError as exc:
 raw=exc.read(6000).decode('utf8','replace');raw=raw.replace(key,'[REDACTED]')
 report.update(status=exc.code,error=re.sub(r'sk-[A-Za-z0-9_-]+','[REDACTED]',raw))
except (OSError,ValueError) as exc:report.update(status='transport_error',error=type(exc).__name__)
report['finished_at']=datetime.now(timezone(timedelta(hours=8))).isoformat()
(directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=True),flush=True);print('REPORT '+str(directory),flush=True)
