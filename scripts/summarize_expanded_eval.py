"""Count all frozen cases, including missing/failed outputs. Never pool protocols."""
import json,math,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'data/local/expanded-eval';OUT=ROOT/'output/expanded-eval'

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def wilson(k,n):
    if not n:return None
    z=1.959964;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(c-r,4),round(c+r,4)]
def state(row):return {'SUPPORTED':'VERIFIED','CONTRADICTED':'BLOCKED','INSUFFICIENT':'NEEDS_REVIEW'}.get(row.get('relation'),row.get('state','NEEDS_REVIEW'))
def metrics(cases,results):
    pos=[c for c in cases if c['gold']=='SUPPORTED'];neg=[c for c in cases if c['gold']!='SUPPORTED']
    get=lambda c:state(results.get(c['id'],{}))
    counts={'n':len(cases),'positive':len(pos),'negative':len(neg),
        'leaked':sum(get(c)=='VERIFIED' for c in neg),'false_blocked':sum(get(c)=='BLOCKED' for c in pos),
        'review':sum(get(c)=='NEEDS_REVIEW' for c in cases),'supported_accepted':sum(get(c)=='VERIFIED' for c in pos),
        'missing_outputs':sum(c['id'] not in results for c in cases)}
    counts['rates']={'leak':counts['leaked']/len(neg) if neg else None,
        'false_block':counts['false_blocked']/len(pos) if pos else None,
        'review':counts['review']/len(cases) if cases else None,
        'supported_acceptance':counts['supported_accepted']/len(pos) if pos else None}
    counts['wilson95_descriptive_independence_assumed']={'leak':wilson(counts['leaked'],len(neg)),
        'false_block':wilson(counts['false_blocked'],len(pos)),'review':wilson(counts['review'],len(cases))}
    return counts

def main():
    data=read(LOCAL/'frozen-dataset.json');protocol=read(OUT/'protocol.json')
    career={};felm=[]
    for path in sorted((LOCAL/'results').glob('*.json')):
        r=read(path)
        if r['protocol']!=protocol['id']:raise ValueError('Result protocol mismatch')
        if path.name.startswith('career-'):career[r['id']]=r
        elif path.name.startswith('felm-'):felm.append(r)
    cm={};fm={};per_project={}
    for arm in ['baseline','whole','atomic']:
        merged={cid:row for r in career.values() for cid,row in r[arm].items()}
        cm[arm]=metrics(data['career'],merged)
        for record in data['career_records']:
            per_project.setdefault(record['id'],{})[arm]=metrics([c for c in data['career'] if c['record_id']==record['id']],career.get(record['id'],{}).get(arm,{}))
        if arm!='baseline':merged={cid:row for r in felm for cid,row in r[arm].items()}
        else:
            merged={}
            for r in felm:
                for cid,row in zip(r['ids'],r['baseline']):merged[cid]={'state':row['actual_state']}
        fm[arm]=metrics(data['felm'],merged)
    edits=[]
    for case in data['career']:
        r=career.get(case['record_id'],{});row=r.get('guarded',{}).get('results',{}).get(case['id'],{})
        pa=r.get('proposal_audit',{}).get(case['id'],{});fa=r.get('final_audit',{}).get(case['id'],{})
        edits.append({'id':case['id'],'gold_original':case['gold'],'original':case['text'],
            'proposed':row.get('proposed_text'),'final':row.get('final_text'),'rejected':row.get('proposal_rejected'),
            'final_state':row.get('state','NEEDS_REVIEW'),'proposal_audit':pa,'final_audit':fa,
            'preservation':row.get('preservation'),'source_record':case['record_id']})
    edit_metrics={}
    for arm,field in [('SAG_proposal','proposal_audit'),('guarded_final','final_audit')]:
        complete=[e for e in edits if e[field].get('supported') is not None]
        positives=[e for e in complete if e['gold_original']=='SUPPORTED']
        negatives=[e for e in complete if e['gold_original']!='SUPPORTED']
        edit_metrics[arm]={'n':len(edits),'audit_completed':len(complete),
            'unsupported_text':sum(e[field]['supported'] is False for e in complete),
            'correct_original_spoiled':sum(e[field]['supported'] is False for e in positives),
            'correct_original_total':len(positives),
            'supported_detail_loss':sum(bool(e[field].get('lost_supported_details')) for e in complete),
            'bad_original_now_supported':sum(e[field]['supported'] is True for e in negatives),
            'bad_original_total':len(negatives)}
    edit_metrics['guard']={'rejected_proposals':sum(e['rejected'] is True for e in edits),
        'final_verified':sum(e['final_state']=='VERIFIED' for e in edits),
        'audit_unsupported_but_final_verified':sum(e['final_state']=='VERIFIED' and e['final_audit'].get('supported') is False for e in edits),
        'final_review':sum(e['final_state']=='NEEDS_REVIEW' for e in edits),
        'final_blocked':sum(e['final_state']=='BLOCKED' for e in edits)}
    timing={k:[r['timing'][k] for r in career.values()] for k in ['retrieval_first','retrieval_cached','atomic','whole_sequential_batches','polish_and_guard']}
    timing={k:{'per_10_claim_record_seconds':v,'median':statistics.median(v) if v else None} for k,v in timing.items()}
    disagreements=[{'id':c['id'],'whole':state(career.get(c['record_id'],{}).get('whole',{}).get(c['id'],{})),
        'atomic':state(career.get(c['record_id'],{}).get('atomic',{}).get(c['id'],{}))} for c in data['career']
        if state(career.get(c['record_id'],{}).get('whole',{}).get(c['id'],{}))!=state(career.get(c['record_id'],{}).get('atomic',{}).get(c['id'],{}))]
    summary={'protocol':protocol['id'],'career':cm,'felm':fm,'per_project':per_project,'edits_model_audit':edit_metrics,
        'career_records_completed':len(career),'felm_cases_completed':sum(len(r['ids']) for r in felm),
        'timing':timing,'career_disagreements':disagreements,
        'coverage_missing_career':sum(not r['complete'] for project in career.values() for r in project['atomic'].values()),
        'annotation':'Author-labelled career; annotation-conditioned FELM; automatic edit audit uses a different, weaker model, not human gold.',
        'uncertainty':'Career cases cluster within only six projects. Wilson intervals assume independence and are descriptive, not justified population intervals.'}
    completed_cases=[c for c in data['career'] if c['record_id'] in career]
    summary['career_completed_only']={arm:metrics(completed_cases,{cid:row for r in career.values() for cid,row in r[arm].items()})
        for arm in ['baseline','whole','atomic']}
    summary['felm_completed_only']={}
    for arm in ['whole','atomic']:
        successful=[r for r in felm if not r.get(arm+'_error')]
        ids={cid for r in successful for cid in r['ids']}
        summary['felm_completed_only'][arm]=metrics([c for c in data['felm'] if c['id'] in ids],
            {cid:row for r in successful for cid,row in r[arm].items()})
    summary['availability']={'career_missing_records':[r['id'] for r in data['career_records'] if r['id'] not in career],
        'felm_atomic_failed_cases':sum(len(r['ids']) for r in felm if r.get('atomic_error')),
        'felm_whole_failed_cases':sum(len(r['ids']) for r in felm if r.get('whole_error')),
        'felm_unattempted':len(data['felm'])-sum(len(r['ids']) for r in felm),
        'reason':'Provider returned HTTP 403 insufficient balance; run stopped. Missing or failed cases are NOT quality-evaluated.'}
    write(OUT/'summary.json',summary);write(OUT/'career-edit-audit.json',edits)
    write(OUT/'career-raw.json',list(career.values()))
    # Public data wording and generated quotations stay in data/local; distributable table is IDs only.
    write(OUT/'felm-decisions.json',[{'id':c['id'],'gold':c['gold'],'domain':c['domain'],
        **{arm:state(next((r[arm][c['id']] for r in felm if c['id'] in r[arm]),{})) for arm in ['whole','atomic']}} for c in data['felm']])
    print(json.dumps({k:summary[k] for k in ['career_completed_only','felm_completed_only','availability']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
