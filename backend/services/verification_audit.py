"""Detailed evidence stays in the workspace of the local backend."""
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from backend.services.local_store import local_dir


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
