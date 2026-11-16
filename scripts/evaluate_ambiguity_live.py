"""Run a selected synthetic wording matrix through the configured live model."""
import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import _load_dotenv
from backend.services.model_client import HttpModelClient
from backend.services.wording_review import review_edit


def run_status(rows, requested):
    if len(rows) != requested or any(row['outcome']=='error' for row in rows):
        return 'INCOMPLETE'
    if any((row['label']=='WRONG' and row['outcome']=='accepted_original_proposal') or
           (row['label']=='SAFE' and row['outcome']=='held_or_restored') for row in rows):
        return 'FAIL'
    if any(row['outcome']=='accepted_repair_needs_review' for row in rows):
        return 'REQUIRES_REVIEW'
    return 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New directory; never overwrites an earlier run')
    parser.add_argument('--sample-index', type=int, default=0, help='Template variant 0–9')
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    if not 0 <= args.sample_index <= 9:
        parser.error('sample index must be between 0 and 9')
    cases = json.loads(args.cases.read_text(encoding='utf8'))
    selected = [case for case in cases if case['id'].endswith((f'-{args.sample_index:02}-SAFE', f'-{args.sample_index:02}-WRONG'))]
    if not selected:
        parser.error('No cases matched the sample index')
    args.output.mkdir(parents=True, exist_ok=False)
    _load_dotenv(ROOT / '.env')
    if not os.getenv('APPLYGUARD_AI_API_KEY'):
        os.environ['APPLYGUARD_AI_API_KEY'] = getpass.getpass('Model API key (hidden, memory only): ').strip()
    if not os.environ['APPLYGUARD_AI_API_KEY']:
        raise SystemExit('No API key supplied')
    client = HttpModelClient(task='complex', timeout=70, require_complete=True)
    rows = []
    start = time.monotonic()

    def run(case):
        begun = time.monotonic()
        candidate, trace = review_edit(client.wording_step, case['original'], case['proposal'])
        outcome = ('error' if trace.get('error') else
                   'accepted_original_proposal' if trace['equivalent'] and candidate == case['proposal'] else
                   'accepted_repair_needs_review' if trace['equivalent'] else 'held_or_restored')
        return {**case, 'candidate':candidate, 'trace':trace, 'outcome':outcome,
                'seconds':round(time.monotonic()-begun, 2)}

    def save():
        counts = Counter(f"{row['label']}:{row['outcome']}" for row in rows)
        status = run_status(rows,len(selected))
        report = {'model':client.model, 'base_url':client.base_url, 'requested':len(selected),
                  'completed':len(rows), 'status':status, 'counts':counts, 'rows':sorted(rows,key=lambda row:row['id']),
                  'cases_sha256':hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                  'guard_sha256':hashlib.sha256((ROOT/'backend/services/fact_lock.py').read_bytes()).hexdigest(),
                  'scope':'Wording gate only; repaired text requires separate review and material verification.',
                  'elapsed':round(time.monotonic()-start, 2)}
        (args.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        return counts, status

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        tasks = {executor.submit(run,case):case for case in selected}
        for task in as_completed(tasks):
            try:
                row = task.result()
            except Exception as exc:
                row = {**tasks[task], 'outcome':'error', 'error':type(exc).__name__}
            rows.append(row)
            save()
            print(json.dumps({'done':len(rows),'total':len(selected),'id':row['id'],'outcome':row['outcome']},ensure_ascii=False),flush=True)
    counts, status = save()
    print(json.dumps({'status':status,'counts':counts,'report':str((args.output/'report.json').resolve())},ensure_ascii=False))
    return 0 if status == 'PASS' else 2 if status == 'REQUIRES_REVIEW' else 1


if __name__ == '__main__':
    raise SystemExit(main())
