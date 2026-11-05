"""Summarize valid paired outputs; failed calls are availability, never model accuracy."""
import json,sys,statistics
from pathlib import Path
from datetime import datetime,timezone,timedelta
root=Path(sys.argv[1]);local=root/'data/local/expanded-eval';out=root/'output/expanded-eval'
data=json.loads((local/'frozen-dataset.json').read_text(encoding='utf8'));protocol=json.loads((out/'protocol.json').read_text(encoding='utf8'))
rows=[json.loads(p.read_text(encoding='utf8')) for p in sorted((local/'results').glob('*.json'))]
assert all(r['protocol']==protocol['id'] for r in rows)
career=[r for r in rows if 'cases' in r and not r.get('atomic_error') and not r.get('whole_errors')]
felm=[r for r in rows if 'ids' in r and not r.get('atomic_error') and not r.get('whole_error')]
def measure(cases,values):
    pos=[c for c in cases if c['gold']=='SUPPORTED'];neg=[c for c in cases if c['gold']!='SUPPORTED']
    state=lambda c:values.get(c['id'],{}).get('relation','INSUFFICIENT')
    missed=[c['id'] for c in neg if state(c)=='SUPPORTED'];blocked=[c['id'] for c in pos if state(c)=='CONTRADICTED']
    review=[c['id'] for c in cases if state(c)=='INSUFFICIENT']
    positive_review=[c['id'] for c in pos if state(c)=='INSUFFICIENT']
    return {'n':len(cases),'positives':len(pos),'negatives':len(neg),'missed':len(missed),'false_blocked':len(blocked),'review':len(review),
       'miss_rate':len(missed)/len(neg) if neg else None,'false_block_rate':len(blocked)/len(pos) if pos else None,'review_rate':len(review)/len(cases) if cases else None,
       'positive_review':len(positive_review),'positive_not_auto_passed_rate':(len(blocked)+len(positive_review))/len(pos) if pos else None,
       'missed_ids':missed,'false_blocked_ids':blocked}
summary={'date':datetime.now(timezone(timedelta(hours=8))).isoformat(),'protocol':protocol['id'],'dataset_sha256':protocol['dataset_sha256'],
    'career_paired':{},'felm_paired':{},'valid_career_records':len(career),'valid_felm_cases':sum(len(r['ids']) for r in felm),
    'planned':{'career':60,'felm':200},'limitations':['Author-labelled synthetic career cases clustered within 6 projects','FELM evidence is annotation-conditioned, not official benchmark scoring','Frozen algorithm predates new Agent/original-inventory changes','No independent human gold for generated edits']}
for name,records,cases in [('career',career,data['career']),('felm',felm,data['felm'])]:
    ids={c['id'] for r in records for c in r['cases']} if name=='career' else {cid for r in records for cid in r['ids']}
    cases=[c for c in cases if c['id'] in ids]
    for arm in ['whole','atomic']:
        summary[name+'_paired'][arm]=measure(cases,{k:v for r in records for k,v in r[arm].items()})
summary['career_batch_timing']={key:{'seconds':[r['timing'][key] for r in career], 'median_seconds':statistics.median([r['timing'][key] for r in career]) if career else None} for key in ['retrieval_first','retrieval_cached','atomic','whole_sequential_batches','polish_and_guard']}
summary['complete']=len(career)==6 and summary['valid_felm_cases']==200
summary['availability']={'attempted_career_cases':60,'attempted_felm_cases':sum(len(r['ids']) for r in rows if 'ids' in r),
    'failed_felm_cases':[cid for r in rows if 'ids' in r and (r.get('atomic_error') or r.get('whole_error')) for cid in r['ids']]}
(out/'paired-summary-20261030.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
