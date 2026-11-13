"""Aggregate independently annotated facts with the upstream DocLens scorer."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from third_party.doclens.aggregate_scores import get_claim_scores, get_citation_scores


def _rows(data: dict, key: str) -> list[dict]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f'{key} must be a list')
    for row in value:
        if not isinstance(row, dict) or 'supported' not in row or type(row['supported']) not in (int, type(None)) or row['supported'] not in (0, 1, None):
            raise ValueError(f'{key}: supported must be 0, 1, or null')
    return value


def evaluate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError('input must be an object')
    result = {}
    for key in ('claim_precision', 'claim_recall'):
        rows = _rows(data, key)
        known = [row for row in rows if row['supported'] is not None]
        source = {'all': {'examples': [{'entailment_prediction': row['supported']} for row in known]}}
        result[key] = {'score': get_claim_scores(source)['total'] if known else None,
                       'assessed': len(known), 'unknown': len(rows) - len(known)}
    rows = _rows(data, 'citations')
    known = [row for row in rows if row['supported'] is not None]
    citations = []
    for row in known:
        cited, evidence = row.get('citations'), row.get('provenance')
        if not isinstance(cited, list) or not isinstance(evidence, list) or any(not isinstance(x, str) for x in cited + evidence):
            raise ValueError('citations and provenance must be lists of strings')
        citations.append({'entailment_prediction': row['supported'], 'citations': cited, 'provenance': evidence})
    scored = get_citation_scores({'all': {'examples': citations}}) if known else None
    result['citations'] = {
        'precision': scored['citation_precision']['total'] if scored and any(r['citations'] for r in citations) else None,
        'recall': scored['citation_recall']['total'] if scored else None,
        'assessed': len(known), 'unknown': len(rows) - len(known),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='Independent human annotations in JSON')
    parser.add_argument('--output', required=True, type=Path, help='New result JSON file')
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8'))
    result = evaluate(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
