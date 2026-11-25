"""Test PDF import over the running desktop API without storing resume text."""
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

folder = Path(sys.argv[1])
output = Path(sys.argv[2])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
results = []
selected = set(sys.argv[3:])
for path in sorted(folder.glob('[0-9][0-9]_*.pdf')):
    if selected and path.name not in selected:
        continue
    request = urllib.request.Request('http://127.0.0.1:8766/api/v1/resume/parse',
        data=json.dumps({'filename': path.name, 'pdf_base64': base64.b64encode(path.read_bytes()).decode(),
                         'parse_mode': 'offline'}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    started = time.monotonic()
    try:
        with opener.open(request, timeout=180) as response:
            data = json.load(response)
            form = data.get('form', {})
            row = {'file': path.name, 'http': response.status, 'extractor': data.get('extractor'),
                   'characters': data.get('char_count'), 'education': len(form.get('education', [])),
                   'internships': len(form.get('internships', [])), 'projects': len(form.get('projects', []))}
    except urllib.error.HTTPError as error:
        data = json.load(error)
        row = {'file': path.name, 'http': error.code, 'error': data.get('error', {}).get('message', '')}
    except Exception as error:
        row = {'file': path.name, 'error': type(error).__name__}
    row['seconds'] = round(time.monotonic() - started, 1)
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
raise SystemExit(0 if results and all(row.get('http') == 200 for row in results) else 1)
