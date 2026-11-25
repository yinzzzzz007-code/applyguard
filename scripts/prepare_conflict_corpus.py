"""Extract project candidates locally for the 13 user-provided simulated cases."""
import base64
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ.setdefault('APPLYGUARD_OCR_BACKEND', 'rapidocr')
from backend.services.resume_parser import parse_resume_pdf

folder = Path(sys.argv[1])
output = Path(sys.argv[2])
results = []
for index in list(range(1, 9)) + list(range(10, 15)):
    pdf = folder / 'merged-8-9.pdf' if index == 8 else next(folder.glob(f'{index:02}_*.pdf'))
    try:
        parsed = parse_resume_pdf(base64.b64encode(pdf.read_bytes()).decode(), pdf.name, parse_mode='offline')
        form = parsed['form']
        row = {'case': index, 'pdf': pdf.name, 'extractor': parsed['extractor'],
               'projects': form['projects'], 'internships': form['internships']}
        print(index, 'projects=', [p.get('title') for p in form['projects']],
              'internships=', [p.get('title') or p.get('organization') for p in form['internships']], flush=True)
    except Exception as exc:
        row = {'case': index, 'pdf': pdf.name, 'error': str(exc)}
        print(index, 'FAILED', type(exc).__name__, flush=True)
    results.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
