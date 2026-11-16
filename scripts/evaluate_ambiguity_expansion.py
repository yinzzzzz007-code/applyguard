"""Run synthetic bilingual ambiguity stress cases against the wording guard."""
import argparse,hashlib,json,sys,time
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.services.wording_review import review_edit

domains=[('延迟','latency'),('误差率','error rate'),('测试耗时','test duration'),('内存占用','memory use'),('人工处理时间','manual handling time'),('查询耗时','query time'),('构建耗时','build time'),('服务成本','service cost'),('能耗','energy consumption'),('峰值流量','peak traffic')]
cases=[]
def add(cat,lang,origin,safe,wrong,i):
    for label,proposal in [('SAFE',safe),('WRONG',wrong)]:
        cases.append({'id':f'{cat}-{lang}-{i:02}-{label}','category':cat,'lang':lang,'label':label,'original':origin,'proposal':proposal})
for i,(zh,en) in enumerate(domains):
    n=11+i; m=n+7
    add('role','zh',f'林负责{zh}测试，周负责部署。',f'周负责部署，林负责{zh}测试。',f'周负责{zh}测试，林负责部署。',i)
    add('role','en',f'Lin tested {en}; Zhou handled deployment.',f'Zhou handled deployment; Lin tested {en}.',f'Zhou tested {en}; Lin handled deployment.',i)
    add('unit','zh',f'测试通过率下降了{n}个百分点。',f'测试通过率降低了{n}个百分点。',f'测试通过率相对降低了{n}%。',i)
    add('unit','en',f'The test pass rate decreased by {n} percentage points.',f'The test pass rate fell by {n} percentage points.',f'The test pass rate decreased by {n} percent relative to the original.',i)
    add('bounds','zh',f'响应时间从{m}毫秒降至{n}毫秒。',f'响应时间由{m}毫秒降为{n}毫秒。',f'响应时间从{n}毫秒变为{m}毫秒。',i)
    add('bounds','en',f'Response time changed from {m} ms to {n} ms.',f'Response time changed to {n} ms from {m} ms.',f'Response time changed from {n} ms to {m} ms.',i)
    add('scope','zh',f'在测试环境中，{zh}下降{n}%。',f'{zh}在测试环境中下降{n}%。',f'在生产环境中，{zh}下降{n}%。',i)
    add('scope','en',f'In the test environment, {en} fell by {n}%.',f'{en} fell by {n}% in the test environment.',f'In production, {en} fell by {n}%.',i)
    add('estimate','zh',f'林预计{zh}会降低约{n}%。',f'林估计{zh}预计下降约{n}%。',f'{zh}实际降低{n}%。',i)
    add('estimate','en',f'Lin estimated that {en} would fall by about {n}%.',f'Lin estimated an approximately {n}% decrease in {en}.',f'{en} fell by {n}%.',i)
    add('negation','zh',f'{zh}优化方案尚未上线。',f'{zh}优化方案还未上线。',f'{zh}优化方案已经上线。',i)
    add('negation','en',f'The {en} optimization has not been deployed.',f'The {en} optimization has not yet been deployed.',f'The {en} optimization has been deployed.',i)
    add('target','zh',f'对甲方案，{zh}约下降{n}%；对乙方案下降{m}%。',f'乙方案的{zh}下降{m}%；甲方案约下降{n}%。',f'对乙方案，{zh}约下降{n}%；对甲方案下降{m}%。',i)
    add('target','en',f'For plan A, {en} fell about {n}%; for plan B it fell {m}%.',f'For plan B {en} fell {m}%; for plan A it fell about {n}%.',f'For plan B, {en} fell about {n}%; for plan A it fell {m}%.',i)
assert len(cases)==280 and len({c['id'] for c in cases})==len(cases)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',required=True,type=Path,help='New report directory; existing results are never overwritten')
parser.add_argument('--baseline',type=Path,help='Compare with a previous report on identical cases')
args=parser.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=False)
(out/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf8')
def optimistic(action,before,text,issues): return {'decision':'equivalent','reason':'stress test'} if action=='judge' else {'text':text}
counts=defaultdict(Counter);results=[];start=time.monotonic()
for c in cases:
    _,trace=review_edit(optimistic,c['original'],c['proposal'])
    if trace.get('error'): raise RuntimeError(c['id']+': '+trace['error'])
    held=not trace['equivalent']; expected=c['label']=='WRONG'
    category=counts[c['category']];category[c['label']]+=1
    if held and not expected:category['false_hold']+=1
    if not held and expected:category['unsafe_pass']+=1
    results.append({**c,'held':held,'expected_held':expected,'invariants':trace.get('invariants',[])})
report={'scope':'New templated synthetic pairs, optimistic fake semantic judge; measure rule guard only, not end-to-end model quality. Labels are author provisional.', 'cases':len(cases),'unique_templates':14,'counts':counts,'results':results,'seconds':round(time.monotonic()-start,2),'source_sha256':hashlib.sha256((out/'cases.json').read_bytes()).hexdigest(), 'guard_sha256':hashlib.sha256((ROOT/'backend/services/fact_lock.py').read_bytes()).hexdigest()}
if args.baseline:
    baseline=json.loads(args.baseline.read_text(encoding='utf8'))
    old={row['id']:row for row in baseline['results']}
    if len(old)!=len(results) or any(c['id'] not in old or any(c[k]!=old[c['id']][k] for k in ('label','original','proposal')) for c in results):
        raise ValueError('Baseline cases or labels differ; comparison would be invalid')
    report['comparison']={'resolved':sum(r['held']==r['expected_held'] and old[r['id']]['held']!=r['expected_held'] for r in results),
                          'new_regressions':sum(r['held']!=r['expected_held'] and old[r['id']]['held']==r['expected_held'] for r in results)}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
findings=sum(v.get('false_hold',0)+v.get('unsafe_pass',0) for v in counts.values())
print(json.dumps({'cases':len(cases),'counts':counts,'findings':findings,'comparison':report.get('comparison'),'seconds':report['seconds'],'report':str((out/'report.json').resolve())},ensure_ascii=False),flush=True)
raise SystemExit(1 if findings else 0)
