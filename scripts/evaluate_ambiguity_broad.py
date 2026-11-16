"""Reproducible templated bilingual stress test; not a model accuracy benchmark."""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.wording_review import review_edit


def cases():
    people = [('林','周','Lin','Zhou'), ('陈','吴','Chen','Wu'), ('李','王','Lee','Wang'),
              ('杨','赵','Yang','Zhao'), ('黄','秦','Huang','Qin'), ('沈','白','Shen','Bai'),
              ('宋','高','Song','Gao'), ('唐','徐','Tang','Xu'), ('何','钱','He','Qian'), ('许','孙','Xu','Sun')]
    subjects = [('缓存','cache'),('服务','service'),('接口','API'),('索引','index'),('任务','task'),
                ('流程','workflow'),('搜索','search'),('队列','queue'),('报表','report'),('模型','model')]
    for i, (a, b, x, y) in enumerate(people):
        for j, (zh, en) in enumerate(subjects):
            n, m = j + 11, j + 31
            groups = [
                ('role_zh', f'{a}负责{zh}测试，{b}负责部署。', f'{b}负责部署，{a}负责{zh}测试。', f'{b}负责{zh}测试，{a}负责部署。'),
                ('role_en', f'{x} tested the {en}; {y} handled deployment.', f'{y} handled deployment; {x} tested the {en}.', f'{y} tested the {en}; {x} handled deployment.'),
                ('scope_zh', f'在测试环境中，{zh}延迟降低{n}%。', f'{zh}延迟在测试环境中降低{n}%。', f'在生产环境中，{zh}延迟降低{n}%。'),
                ('scope_en', f'In the test environment, {en} latency fell {n}%.', f'{en} latency fell {n}% in the test environment.', f'In production, {en} latency fell {n}%.'),
                ('stage_en', f'In staging, {en} latency fell {n}%.', f'{en} latency fell {n}% in staging.', f'In production, {en} latency fell {n}%.'),
                ('neg_zh', f'{zh}方案尚未上线。', f'{zh}方案还未上线。', f'{zh}方案已经上线。'),
                ('neg_en', f'The {en} has not been deployed.', f'The {en} has not yet been deployed.', f'The {en} has been deployed.'),
                ('neg_release_en', f'The {en} has not been released.', f'The {en} has not yet been released.', f'The {en} has been released.'),
                ('target_zh', f'对甲方案，{zh}延迟约降低{n}%；对乙方案降低{m}%。', f'乙方案的{zh}延迟降低{m}%；甲方案约降低{n}%。', f'乙方案的{zh}延迟约降低{n}%；甲方案降低{m}%。'),
                ('target_en', f'For plan A, {en} latency fell about {n}%; for plan B it fell {m}%.', f'For plan B {en} latency fell {m}%; for plan A it fell about {n}%.', f'For plan B {en} latency fell about {n}%; for plan A it fell {m}%.'),
                ('metric_zh', f'准确率提升约{n}%，召回率提升{m}%。', f'召回率提升{m}%，准确率提升约{n}%。', f'召回率提升约{n}%，准确率提升{m}%。'),
                ('metric_en', f'Accuracy was about {n}%; recall was {m}%.', f'Recall was {m}%; accuracy was about {n}%.', f'Recall was about {n}%; accuracy was {m}%.'),
                ('unit_zh', f'{zh}通过率提高{n}个百分点。', f'{zh}通过率提升{n}个百分点。', f'{zh}通过率相对提高{n}%。'),
                ('unit_en', f'The {en} pass rate increased by {n} percentage points.', f'The {en} pass rate rose by {n} percentage points.', f'The {en} pass rate increased by {n} percent relative to baseline.'),
            ]
            for category, original, safe, wrong in groups:
                for label, proposal in [('SAFE', safe), ('WRONG', wrong)]:
                    yield {'id': f'{category}-{i:02}-{j:02}-{label}', 'category': category, 'original': original,
                           'proposal': proposal, 'label': label}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New report directory')
    args = parser.parse_args()
    rows = list(cases())
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate cases')
    args.output.mkdir(parents=True, exist_ok=False)
    def optimistic(action, before, text, issues):
        return {'decision': 'equivalent', 'reason': 'synthetic stress'} if action == 'judge' else {'text': text}
    counts = defaultdict(Counter)
    for row in rows:
        _, trace = review_edit(optimistic, row['original'], row['proposal'])
        if trace.get('error'):
            raise RuntimeError(row['id'] + ': ' + trace['error'])
        row['held'] = not trace['equivalent']
        row['invariants'] = trace.get('invariants', [])
        counts[row['category']][row['label']] += 1
        if row['held'] and row['label'] == 'SAFE': counts[row['category']]['false_hold'] += 1
        if not row['held'] and row['label'] == 'WRONG': counts[row['category']]['unsafe_pass'] += 1
    report = {'scope': 'Author-labelled templated fictional examples; optimistic fake judge; not model accuracy.',
              'cases': len(rows), 'template_families': 14, 'counts': counts, 'results': rows,
              'guard_sha256': hashlib.sha256((ROOT/'backend/services/fact_lock.py').read_bytes()).hexdigest()}
    (args.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    findings = sum(v.get('false_hold', 0) + v.get('unsafe_pass', 0) for v in counts.values())
    print(json.dumps({'cases': len(rows), 'counts': counts, 'findings': findings,
                      'report': str((args.output/'report.json').resolve())}, ensure_ascii=False))
    return int(findings > 0)


if __name__ == '__main__':
    raise SystemExit(main())
