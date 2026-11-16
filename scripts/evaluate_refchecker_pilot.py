"""Compare explicit, pre-split fictional claims using RefChecker's original prompt."""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.refchecker_review import LABELS, SYSTEM, aggregate_case_labels


def evaluate(client, cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError('cases must be a nonempty list')
    rows = []
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get('id'), str)
                or not isinstance(case.get('reference'), str) or not case['reference'].strip()
                or not isinstance(case.get('claim'), str) or not case['claim'].strip()
                or case.get('expected') not in LABELS):
            raise ValueError('each case needs id, reference, claim and an expected label')
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('duplicate case id')
    for case in cases:
        error = None
        try:
            response = client.complete_json(SYSTEM, json.dumps(
                {'reference': case['reference'], 'claim': case['claim']}, ensure_ascii=False))
            label = response.get('label') if isinstance(response, dict) else None
            label = label if label in LABELS else 'Abstain'
        except Exception as exc:
            label = 'Abstain'
            error = {'type': type(exc).__name__}
            status = re.fullmatch(r'Model service returned HTTP (\d{3})', str(exc))
            if status:
                error['http_status'] = int(status[1])
        rows.append({'id': case['id'], 'expected': case['expected'], 'label': label,
                     'correct': None if label == 'Abstain' else label == case['expected'], 'error': error})
    labels = [r['label'] for r in rows]
    return {'complete': 'Abstain' not in labels,
            'correct': sum(r['correct'] is True for r in rows),
            'assessed': sum(r['correct'] is not None for r in rows), 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true', help='Send the supplied claims and references to the configured model')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required: input text is sent to the configured model provider')
    if args.output.exists():
        parser.error('output already exists')
    from backend import app  # Load local config without printing credentials.
    from backend.services.model_client import HttpModelClient
    cases = json.loads(args.input.read_text(encoding='utf-8'))['cases']
    client = HttpModelClient(task='complex', require_complete=True, timeout=45)
    if not client.api_key:
        client.api_key = getpass.getpass('Model API key (hidden, memory only): ').strip()
    if not client.api_key:
        parser.error('model API key is not configured')
    result = evaluate(client, cases)
    result['model'] = client.model
    result['method'] = 'RefChecker subsentence prompt adapted to JSON; manually pre-split claims; not the full upstream pipeline'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
