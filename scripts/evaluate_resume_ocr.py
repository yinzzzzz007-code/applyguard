"""Run the actual local OCR import and save aggregate observations, never resume text."""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import app  # Loads the same local OCR settings as the application.
from backend.services.resume_parser import extract_resume_from_text, parse_resume_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path, nargs='+', help='PDFs, or local .txt/.json OCR output when --replay-ocr is set')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-education', help='Comma-separated manually counted education rows, in PDF order')
    parser.add_argument('--expected-internships', help='Comma-separated manually counted work rows, in input order')
    parser.add_argument('--expected-projects', help='Comma-separated manually counted project rows, in input order')
    parser.add_argument('--replay-ocr', action='store_true', help='Read local OCR text/spans; do not run OCR again')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists')
    expectations = {}
    for field in ('education', 'internships', 'projects'):
        raw = getattr(args, 'expected_' + field)
        if raw is None:
            continue
        try:
            values = [int(value) for value in raw.split(',')]
        except ValueError:
            parser.error(f'expected {field} counts must be comma-separated nonnegative integers')
        if len(values) != len(args.pdf) or any(value < 0 for value in values):
            parser.error(f'provide one nonnegative expected {field} count for every input')
        expectations[field] = values
    rows = []
    for index, path in enumerate(args.pdf, 1):
        start = time.monotonic()
        try:
            if args.replay_ocr:
                if path.suffix.lower() == '.json':
                    spans = json.loads(path.read_text(encoding='utf-8'))
                    text = '\n'.join(span['text'] for span in spans)
                elif path.suffix.lower() == '.txt':
                    text = path.read_text(encoding='utf-8')
                else:
                    raise ValueError('OCR replay input must be .txt or .json')
                result = {'form': extract_resume_from_text(text)}
            else:
                payload = base64.b64encode(path.read_bytes()).decode('ascii')
                result = parse_resume_pdf(payload, 'local.pdf', parse_mode='offline_ocr')
            rows.append({'sample': index, 'status': 'replayed' if args.replay_ocr else 'imported', 'seconds': round(time.monotonic() - start, 2),
                         'section_counts': {k: len(result['form'][k]) for k in ('education', 'internships', 'projects', 'awards')}})
            for field, values in expectations.items():
                rows[-1]['expected_' + field] = values[index - 1]
                rows[-1][field + '_count_matches'] = rows[-1]['section_counts'][field] == values[index - 1]
        except Exception as exc:
            rows.append({'sample': index, 'status': 'failed', 'seconds': round(time.monotonic() - start, 2),
                         'error_type': type(exc).__name__})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump({'samples': rows, 'notice': 'Counts are not correctness; independently compare each field with its source.'}, handle, ensure_ascii=False, indent=2)
    if any(row['status'] == 'failed' for row in rows):
        return 1
    return 2 if any(any(row.get(field + '_count_matches') is False for field in expectations) for row in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
