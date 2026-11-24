"""Local background polish jobs, scoped to the application and the submitted draft."""
import json
import logging
import threading
from uuid import uuid4

from backend.services.grounded_workflow import collect_sources, load_grounding_experiences, polish_workflow
from backend.services.local_store import local_dir
from backend.services.sag_grounding import evidence_snapshot, fingerprint

_lock = threading.Lock()
_running = set()


def job_file(request):
    claims = request.get('claims')
    if not request.get('application_id') or not request.get('candidate_id') or not request.get('jd_text'):
        raise ValueError('请选择申请和岗位后再进行润色。')
    if not isinstance(claims, list) or not 1 <= len(claims) <= 20:
        raise ValueError('请保留 1 至 20 条正文经历。')
    if any(not isinstance(row, dict) or not row.get('claim_id') or not isinstance(row.get('text'), str)
           or not 1 <= len(row['text']) <= 420 for row in claims):
        raise ValueError('正文经历格式无效。')
    form = request.get('resume_draft') or {}
    if not isinstance(form, dict):
        raise ValueError('经历库格式无效。')
    scope = {name: request.get(name) for name in ('candidate_id', 'application_id', 'jd_text', 'target_job', 'grounding_mode')}
    scope['claims'] = [(row['claim_id'], row['text']) for row in claims]
    scope['resume_draft'] = {k:v for k,v in form.items() if k not in ('savedAt','dirty')}
    return local_dir() / 'polish-jobs' / (fingerprint(scope) + '.json')


def save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.' + uuid4().hex + '.tmp')
    try:
        tmp.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def _read(path):
    return json.loads(path.read_text('utf-8')) if path.is_file() else {'state':'idle'}


def _run(path, vault, request):
    try:
        result = polish_workflow(vault, request)
        run_id = result['grounding']['run_id']
        record = {'state':'ready', 'run_id':run_id}
    except Exception:
        logging.exception('Background resume polish failed for %s', path.stem[:12])
        record = {'state':'failed', 'message':'后台润色未完成，可以重新发起。原文已保留。'}
    with _lock:
        try:
            save(path, record)
        finally:
            _running.discard(path)


def status(vault, request, *, start=False):
    path = job_file(request)
    with _lock:
        if path in _running:
            return {'state':'running'}
        record = _read(path)
        if start:
            if request.get('local_only') is not False:
                raise ValueError('使用云端润色需要确认。')
            # A repeated submit without having received the last completion is a read.
            if record.get('state') != 'ready' or request.get('known_run') == record.get('run_id'):
                save(path, {'state':'running'})
                _running.add(path)
                try:
                    threading.Thread(target=_run,args=(path,vault,request),daemon=True).start()
                except RuntimeError:
                    _running.discard(path)
                    raise
                return {'state':'running'}
    if record['state'] == 'running':
        return {'state':'failed','message':'后台服务曾重启，上次任务已中断。可以重新开始。'}
    if record['state'] != 'ready':
        return record
    run_id = record['run_id']
    if request.get('known_run') == run_id:
        return {'state':'seen','run_id':run_id}
    audit_dir = local_dir() / 'verification-runs'
    source = audit_dir / (run_id + '.json')
    if not source.is_file():
        return {'state':'failed','message':'本机的润色记录已移除。', 'run_id':run_id}
    known = request.get('known_run')
    if isinstance(known,str) and len(known)==32 and all(c in '0123456789abcdef' for c in known):
        previous = audit_dir / (known + '.json')
        if previous.is_file() and previous.stat().st_mtime_ns > source.stat().st_mtime_ns and not start:
            return {'state':'seen','run_id':run_id}
    report = json.loads(source.read_text('utf-8'))
    sources,_,_ = collect_sources(load_grounding_experiences(vault,request),request['candidate_id'])
    if report['snapshot'] != evidence_snapshot(sources):
        return {'state':'stale','run_id':run_id,'message':'材料或关联已更新。请按当前材料重新生成。'}
    return {'state':'ready','run_id':run_id,'grounding':report}
