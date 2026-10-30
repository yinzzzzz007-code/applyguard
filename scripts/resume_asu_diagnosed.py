"""Resume a frozen run; retain sanitized service error reasons, never headers."""
import json,re,runpy,sys,threading,urllib.request,urllib.error
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
original=urllib.request.urlopen
stopped=threading.Event()
def observed(request,*args,**kwargs):
    if stopped.is_set():
        from backend.services.model_client import ModelFailure
        raise ModelFailure('Service authorization failure; remaining requests paused',retryable=False)
    try:return original(request,*args,**kwargs)
    except urllib.error.HTTPError as exc:
        if exc.code in (401,402,403):stopped.set()
        raw=exc.read(6000).decode('utf8','replace')
        value={'date':datetime.now(timezone(timedelta(hours=8))).isoformat(),'status':exc.code,
               'error':re.sub(r'sk-[A-Za-z0-9_-]+','[REDACTED]',raw)}
        if '--resume' in sys.argv:
            folder=Path(sys.argv[sys.argv.index('--resume')+1])
            with (folder/'http-errors.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps(value,ensure_ascii=False)+'\n')
        print(json.dumps(value,ensure_ascii=True),flush=True)
        raise
urllib.request.urlopen=observed
runpy.run_path(str(ROOT/'scripts/evaluate_asu_ablation.py'),run_name='__main__')
