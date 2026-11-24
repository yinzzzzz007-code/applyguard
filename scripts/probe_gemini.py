"""Probe Gemini using synthetic text, after checking the API key's cumulative spend."""
import argparse
import getpass
import json
import time
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--structured',action='store_true',help='Test the structured JSON format used by ApplyGuard')
parser.add_argument('--cumulative-limit',type=Decimal,default=Decimal('9.5'))
args=parser.parse_args()
if args.cumulative_limit<=0 or args.cumulative_limit>Decimal('9.5'):
    parser.error('cumulative-limit must be within 0–9.5 CA')
key=getpass.getpass('ChatAnywhere key (hidden): ').strip()
base='https://api.chatanywhere.tech/v1'
headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'}
def post(path,body):
    request=Request(base+path,json.dumps(body).encode(),headers)
    with urlopen(request,timeout=35) as response:
        return response.status,json.load(response)
def balance():
    _,result=post('/query/balance',{})
    return Decimal(str(result.get('data',result)['apiKeyUsed']))
report={'model':'gemini-3.1-flash-lite-preview','attempts':[],'contains_personal_data':False}
try:
    before=balance();report['cumulative_before_ca']=str(before)
    if before>=args.cumulative_limit:
        report['stopped']='cumulative usage already at test limit'
    else:
        if args.structured:report['request_format']='json_schema'
        for _ in range(2):
            if balance()>=args.cumulative_limit:
                report['stopped']='cumulative test limit reached';break
            started=time.monotonic()
            try:
                payload={'model':report['model'],'messages':[{'role':'user','content':'Return JSON with text set to OK.' if args.structured else 'Reply with exactly the word OK.'}],'max_tokens':128,'temperature':0}
                if args.structured:payload['response_format']={'type':'json_schema','json_schema':{'name':'applyguard_checked_output','strict':True,'schema':{'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False}}}
                status,response=post('/chat/completions',payload)
                message=response.get('choices',[{}])[0].get('message',{})
                content=message.get('content')
                try: structured_ok=bool(args.structured and json.loads(content)=={'text':'OK'})
                except (ValueError,TypeError): structured_ok=False
                report['attempts'].append({'http_status':status,'seconds':round(time.monotonic()-started,2),'nonempty_response':bool(content),'reply_is_ok':isinstance(content,str) and content.strip().upper()=='OK','structured_valid':structured_ok if args.structured else None,'finish_reason':response.get('choices',[{}])[0].get('finish_reason')})
                break
            except HTTPError as exc:
                report['attempts'].append({'http_status':exc.code,'seconds':round(time.monotonic()-started,2)})
                if exc.code not in (429,500,502,503,504):break
            except (URLError,TimeoutError,OSError,ValueError,KeyError) as exc:
                report['attempts'].append({'error_type':type(exc).__name__,'seconds':round(time.monotonic()-started,2)})
                break
    report['cumulative_after_ca']=str(balance())
except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError) as exc:
    report['stopped']='balance query failed; probe stopped' if not report['attempts'] else 'final balance query failed'
    report['error_type']=type(exc).__name__
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
