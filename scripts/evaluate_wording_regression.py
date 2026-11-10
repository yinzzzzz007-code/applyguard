"""Offline paired regression for the wording guard; input data never leave the machine."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.wording_review import review_edit

def numeric_pairs():
    """Metamorphic test matrix. Each scenario has a faithful and a corrupted rewrite."""
    # Numbers intentionally recur in other clauses: a bag-of-numbers check cannot suffice.
    for i, (a, b, c) in enumerate([(200,140,80),(32,16,8),(90,61,52),(80,84,73),
                                    (25,18,12),(18,22,30),(71,63,41),(47.5,35.5,20.5)]):
        for lang in ('en', 'zh'):
            for unit in ('%', 'ms'):
                v, w, z = [str(x) + (' ms' if unit == 'ms' and lang == 'en'
                                      else '毫秒' if unit == 'ms' else '%') for x in (a,b,c)]
                if lang == 'en':
                    first, second = ('Precision', 'Recall') if unit == '%' else ('Latency', 'Duration')
                    prefix = f'{first} changed from {v} to {w}'
                    tail = f'{second} changed from {w} to {z}'
                    groups = [
                        ('endpoints', prefix+'.', f'{first} changed to {w} from {v}.',
                         f'{first} changed to {v} from {w}.'),
                        ('two_metrics', prefix+'; '+tail+'.', tail+'; '+prefix+'.',
                         f'{second} changed from {v} to {w}; {first} changed from {w} to {z}.'),
                        ('approximation', f'{first} was approximately {v}; {second} was {z}.',
                         f'{second} was {z}; {first} was about {v}.',
                         f'{second} was about {z}; {first} was {v}.'),
                    ]
                else:
                    first, second = ('精确率', '召回率') if unit == '%' else ('延迟','耗时')
                    prefix, tail = f'{first}从{v}变为{w}', f'{second}从{w}变为{z}'
                    groups = [
                        ('endpoints', prefix+'。', f'{first}由{v}调整至{w}。', f'{first}由{w}调整至{v}。'),
                        ('two_metrics', prefix+'；'+tail+'。', tail+'；'+prefix+'。',
                         f'{second}从{v}变为{w}；{first}从{w}变为{z}。'),
                        ('approximation', f'{first}约为{v}，{second}为{z}。',
                         f'{second}为{z}，{first}约为{v}。', f'{second}约为{z}，{first}为{v}。'),
                    ]
                for family, original, safe, wrong in groups:
                    for label, text in [('SAFE', safe), ('WRONG', wrong)]:
                        yield (f'{lang}-{unit}-{family}-{i}-{label}',original,text,label)

    # Equivalent units, decimal fractions, Chinese full-width percent and distinct pp.
    for a in ('1','2','3.5','12','20','33','47','65.5'):
        for lang, original, safe, wrong in [
            ('en', f'Precision improved by {a} percentage points.', f'Precision improved by {a} pp.',
             f'Precision improved by {a}%.'),
            ('zh', f'准确率提高{a}％。', f'准确率提升{a}%。', f'准确率提升{a}个百分点。'),
        ]:
            yield (f'{lang}-unit-{a}-SAFE',original,safe,'SAFE')
            yield (f'{lang}-unit-{a}-WRONG',original,wrong,'WRONG')

def suites():
    for path in (ROOT/'eval/asu_ablation/fact-lock-challenge-2026-10-31.json',
                 ROOT/'eval/asu_ablation/fact-lock-confirmation-2026-10-31.json',
                 ROOT/'eval/review-holdout-20261105.json'):
        for row in json.loads(path.read_bytes())['cases']:
            label = row['expected'] if 'expected' in row else ('SAFE' if row['equivalent'] else 'WRONG')
            yield row.get('split','review-holdout'),(row['id'],row['original'],row['proposal'],label)
    path = ROOT/'docs/testing/runs/2026-10-30/main/20261030_172733_803092_asu-reviewed-replay/report.json'
    for row in json.loads(path.read_bytes())['records']:
        if row['label'] in {'SAFE','WRONG'} and row['changed'] and row['replayed_v3_accept'] is not None:
            yield 'frozen-asu',(row['id']+'/'+row['arm'],row['original'],row['proposal'],row['label'])
    for pair in numeric_pairs():
        yield 'numeric-matrix',pair

def optimistic_judge(action,before,text,issues):
    # Stress the deterministic checks even if the semantic judge accepts every edit.
    return {'decision':'equivalent','reason':'test'} if action == 'judge' else {'text':text}

def measure(pairs):
    rows = []
    for suite, (key,original,proposal,label) in pairs:
        _,trace = review_edit(optimistic_judge,original,proposal)
        if trace.get('error'):
            raise RuntimeError((key,trace['error']))
        rows.append(dict(suite=suite,id=key,label=label,
                         input_sha256=hashlib.sha256((original+'\n'+proposal).encode()).hexdigest(),
                         held=not trace['equivalent']))
    return rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--prose', nargs='?', type=Path, const=ROOT/'eval/wording-prose-20261105.json',
                        help='Separately score the default or a specified frozen prose file')
    args = parser.parse_args()
    pairs = suites()
    if args.prose:
        cases = json.loads(args.prose.read_bytes())['cases']
        pairs = (('prose',(r['id'],r['original'],r['proposal'],r['expected'])) for r in cases)
    rows = measure(pairs)
    keys = ('suite','id','input_sha256','label')
    if len({(r['suite'],r['id']) for r in rows}) != len(rows):
        raise ValueError('Duplicate case IDs')
    guard_paths = ['backend/services/'+name+'.py' for name in ('fact_lock','edit_invariants','wording_review','asu_resume')]
    digest = lambda p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    out = {'date':datetime.now(timezone.utc).isoformat(),'guard_files':{p:digest(p) for p in guard_paths},
           'counts':{},'rows':rows}
    if args.baseline:
        baseline = json.loads(args.baseline.read_bytes())
        out['baseline_guard_files'] = baseline.get('baseline_guard_files',baseline['guard_files'])
        if [[r[k] for k in keys] for r in rows] != [[r[k] for k in keys] for r in baseline['rows']]:
            raise ValueError('Inputs or labels changed since baseline')
        for row,old in zip(rows,baseline['rows']):
            row['previously_held'] = old.get('previously_held',old['held'])
    for suite in sorted({r['suite'] for r in rows}):
        counts = Counter()
        for r in rows:
            if r['suite']==suite:
                counts[r['label']] += 1
                for field in ('previously_held','held'):
                    if field in r:
                        counts[field+'_'+r['label']] += int(r[field])
        out['counts'][suite] = counts
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n',encoding='utf8')
    print(json.dumps(out['counts'], sort_keys=True))
    if args.baseline:
        regressions = [r for r in rows if r['held'] != r['previously_held'] and
                       r['held'] != (r['label'] == 'WRONG')]
        if regressions:
            raise SystemExit(f'{len(regressions)} new regressions. See {args.output}')

if __name__ == '__main__':
    main()
