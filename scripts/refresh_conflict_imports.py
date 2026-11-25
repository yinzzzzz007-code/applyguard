"""Refresh selected OCR outputs after parser fixes, retaining other results."""
import base64, json, os, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
os.environ['APPLYGUARD_OCR_BACKEND']='rapidocr'
from backend.services.resume_parser import parse_resume_pdf

path=root/'output/desktop-check/conflict-corpus-final-private.json'
rows=json.loads(path.read_text(encoding='utf8'))
for number in map(int,sys.argv[1:]):
    row=next(r for r in rows if r['case']==number)
    pdf=Path(r'E:\pdf-collection')/row['pdf']
    result=parse_resume_pdf(base64.b64encode(pdf.read_bytes()).decode(),pdf.name,parse_mode='offline')
    row.update({k:result['form'][k] for k in ('projects','internships')})
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    print(number,[p['title'] for p in row['projects']],flush=True)
