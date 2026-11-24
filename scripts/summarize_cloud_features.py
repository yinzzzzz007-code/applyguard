"""Summarize actual cloud runs; HTTP 200 alone is never a model success."""
from __future__ import annotations
import argparse,getpass,json
from decimal import Decimal
from pathlib import Path
from urllib.request import Request,urlopen


def outcome(name,row):
    if name=='ai_resume_parse':ok=row.get('http')==200 and row.get('extractor')=='模型抽取'
    elif name=='ai_jd_and_semantic_match':ok=row.get('modes',{}).get('jd_parser')=='MODEL' and row.get('modes',{}).get('evidence_matcher')=='AI_SEMANTIC'
    elif name=='atomic_reverification':ok=row.get('http')==200 and not row.get('error')
    elif name=='ai_resume_polish':ok=row.get('passed') is True and row.get('http')==200 and not row.get('error') and (row.get('proposals',0)>0 or (row.get('expected_proposals')==0 and row.get('conflicts_skipped',0)>0))
    elif name=='interview':ok=row.get('http')==200 and row.get('questions',0)>0
    elif name=='optional_job_ai_explanation':ok=row.get('has_ai_explanation') is True
    elif name=='optional_refchecker_audit':ok=row.get('relation') in {'Entailment','Neutral','Contradiction'} and bool(row.get('atomic_labels'))
    else:ok=row.get('passed') is True
    return 'COMPLETED' if ok else 'INCOMPLETE'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports',nargs='+',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--balance-check',action='store_true',help='Read cumulative usage with hidden key input; no model call')
    args=parser.parse_args()
    attempts={};latest={};used=[]
    for path in args.reports:
        report=json.loads(path.read_text(encoding='utf-8'))
        for value in ('key_used_ca_before','key_used_ca_after'):
            if value in report:used.append(Decimal(report[value]))
        for name,row in report.get('stages',{}).items():
            # Keep only stage metadata, not resume text, evidence or model proposals.
            result={'report':str(path),'outcome':outcome(name,row),**row}
            attempts.setdefault(name,[]).append(result);latest[name]=result
    if args.balance_check:
        key=getpass.getpass('ChatAnywhere key (hidden; balance lookup only): ').strip()
        request=Request('https://api.chatanywhere.tech/v1/query/balance',b'{}',{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with urlopen(request,timeout=20) as response:billing=json.load(response)
        used.append(Decimal(str(billing.get('data',billing)['apiKeyUsed'])))
    total=max(used,default=Decimal('0'))
    expected={'ai_resume_parse','ai_jd_and_semantic_match','atomic_reverification','ai_resume_polish','strict_export_selected_award','interview','optional_job_ai_explanation','optional_refchecker_audit','harness_tool_flow'}
    missing=sorted(expected-set(latest))
    result={'model':'gemini-3.1-flash-lite-preview','latest_by_feature':latest,'attempts':attempts,
        'key_cumulative_used_ca':str(total),'within_10_ca':total<Decimal('10'),
        'missing_features':missing,'all_latest_completed':not missing and all(row['outcome']=='COMPLETED' for row in latest.values()),
        'notice':'Cumulative key usage is a conservative cap; overlapping run deltas must not be added. Completed verification may correctly block unsupported claims. RefChecker is a bounded optional audit; retrieval strategy ablations are outside this feature test.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'outcomes':{name:row['outcome'] for name,row in latest.items()},'key_cumulative_used_ca':str(total),'within_10_ca':result['within_10_ca'],'all_latest_completed':result['all_latest_completed']},ensure_ascii=False))
    return 0 if result['all_latest_completed'] and result['within_10_ca'] else 1

if __name__=='__main__':raise SystemExit(main())
