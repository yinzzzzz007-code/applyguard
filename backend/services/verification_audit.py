"""Detailed evidence stays in the workspace of the local backend."""
from datetime import datetime, timezone
import hashlib
import json
import os
import traceback
from uuid import uuid4
from backend.services.local_store import local_dir


def current_conflict(candidate, claims, snapshot):
    directory = local_dir() / 'verification-runs'
    if not directory.exists():
        return None
    candidate_hash = hashlib.sha256(candidate.encode()).hexdigest()
    texts = {claim['claim_id']:claim['text'] for claim in claims}
    for path in sorted(directory.glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if (record.get('candidate_hash') != candidate_hash or record.get('snapshot') != snapshot
                or record.get('operation') != 'verify' or record.get('mode') != 'sag_atomic'
                or record.get('error')):
            continue
        for cid, row in record.get('results', {}).items():
            if (row.get('state') == 'BLOCKED' and cid in texts and row.get('final_text') == texts[cid]
                    and any(atom.get('relation') == 'CONTRADICTED' and atom.get('citations')
                            for atom in row.get('atoms', []))):
                return record.get('run_id')
    return None


def save_failure(stage, error):
    directory = local_dir() / 'verification-failures'
    directory.mkdir(parents=True, exist_ok=True)
    identifier = uuid4().hex
    detail = ''.join(traceback.format_exception(error))[-16000:]
    key = os.getenv('APPLYGUARD_AI_API_KEY', '')
    if key:
        detail = detail.replace(key, '[REDACTED]')
    record = {'at':datetime.now(timezone.utc).isoformat(), 'stage':stage,
              'type':type(error).__name__, 'traceback':detail}
    (directory / (identifier + '.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return identifier


def save_run(report, candidate, *, polish):
    directory = local_dir() / 'verification-runs'
    directory.mkdir(parents=True, exist_ok=True)
    run_id = uuid4().hex
    report.update(run_id=run_id, at=datetime.now(timezone.utc).isoformat(), operation='polish' if polish else 'verify')
    record = {
              'candidate_hash':hashlib.sha256(candidate.encode()).hexdigest(), **report}
    temp = directory / (run_id + '.tmp')
    with temp.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, ensure_ascii=False)
    temp.replace(directory / (run_id + '.json'))
