"""Explicit restart after service recovery; preserve failed attempts and stop on fatal errors.
No calls occur until a key is entered. Algorithm/data must match the original frozen protocol.
"""
import hashlib,json,os,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
import expanded_grounding_eval as run

class StopRun(BaseException):pass
STOP=threading.Event()
BaseClient=run.HttpModelClient
def main():
    from backend.services.model_client import ModelFailure
    class Client(BaseClient):
        def _complete(self,*args,**kwargs):
            if STOP.is_set():raise StopRun('Service unavailable; no further model calls')
            try:return super()._complete(*args,**kwargs)
            except ModelFailure as error:
                if not error.retryable:
                    STOP.set();raise StopRun('Nonretryable model error; inspect provider account/configuration') from None
                raise
    protocol=json.loads((run.OUT/'protocol.json').read_text(encoding='utf-8'))
    for name,expected in protocol['code'].items():
        if hashlib.sha256((run.ROOT/name).read_bytes()).hexdigest()!=expected:
            raise SystemExit('Frozen algorithm changed: '+name+'; create a new protocol instead.')
    run.configure()
    if os.environ['APPLYGUARD_AI_MODEL']!=protocol['model']:raise SystemExit('Model differs from frozen protocol')
    data=json.loads((run.LOCAL/'frozen-dataset.json').read_text(encoding='utf-8'))
    if hashlib.sha256((run.LOCAL/'frozen-dataset.json').read_bytes()).hexdigest()!=protocol['dataset_sha256']:
        raise SystemExit('Dataset changed')
    os.environ['APPLYGUARD_GROUNDING_DIR']=str(run.LOCAL/'sag')
    client=Client(max_tokens=6000,timeout=110,require_complete=True)
    auditor=Client(model=protocol['auditor'],max_tokens=4000,timeout=110,require_complete=True)
    attempts=run.LOCAL/'attempts';attempts.mkdir(exist_ok=True)
    for path in (run.LOCAL/'results').glob('felm-*.json'):
        result=json.loads(path.read_text(encoding='utf-8'))
        if result.get('atomic_error') or result.get('whole_error'):
            destination=attempts/(path.stem+'-'+hashlib.sha256(path.read_bytes()).hexdigest()[:12]+'.json')
            if not path.resolve().is_relative_to(run.LOCAL.resolve()) or not destination.resolve().is_relative_to(run.LOCAL.resolve()):raise ValueError('Unsafe path')
            path.replace(destination)
    # Wrap retrieval errors separately because the SDK uses its own model client.
    from backend.services.sag_grounding import GroundingUnavailable
    def safe_task(fn,*args):
        if STOP.is_set():raise StopRun('Cancelled after service failure')
        try:return fn(*args)
        except GroundingUnavailable:
            STOP.set();raise StopRun('SAG failed; stopped before submitting more records') from None
    failures=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[]
        for record in data['career_records']:
            jobs.append(pool.submit(safe_task,run.career_task,record,[c for c in data['career'] if c['record_id']==record['id']],client,auditor,protocol['id']))
        for i in range(0,len(data['felm']),3):
            jobs.append(pool.submit(safe_task,run.felm_task,data['felm'][i:i+3],client,i//3,protocol['id']))
        for future in as_completed(jobs):
            try:future.result()
            except StopRun as error:
                if not failures:print(str(error),flush=True)
                failures.append('service_unavailable');STOP.set()
            except Exception as error:failures.append(type(error).__name__)
    run.write(run.OUT/'resume-status.json',{'protocol':protocol['id'],'failures':failures,
        'usage':client.usage,'auditor_usage':auditor.usage,'note':'SDK usage is not included; previous failures preserved in local attempts.'})
if __name__=='__main__':main()
