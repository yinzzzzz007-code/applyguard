"""Assistant-reviewed labels for the actual 2026-10-30 partial run.

These explicit decisions were made after reading all 57 outputs and source facts.
They are not independent human annotation. Preserve automated grades unchanged.
"""
import argparse,copy,hashlib,json,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.services.edit_guard import preservation
from backend.services.asu_resume import proposal_violations
from scripts.evaluate_asu_ablation import fixture,ARMS

WRONG={
 ('zh_team_2',a):'删除“只实现Vue”的个人职责限定及SQL接口归属林岚的信息。' for a in ARMS
}
WRONG.update({('zh_assist_1',a):'删除“只负责缺失值检查”的职责范围限定；部分版本还删除未负责架构。' for a in ARMS})
WRONG.update({
 ('zh_alias_2','asu_v1'):'将Redis负责人林岚泛化成他人，丢失原文明确的分工信息。',
 ('zh_pending_1','asu_fixed'):'删除林岚为项目负责人的明确归属。',
 ('zh_assist_2','asu_fixed'):'保留未做架构，但删除只负责缺失值检查的范围限定。',
 ('en_team_3','pre_asu'):'删除only，扩大了原文对个人实现范围的表述。',
 ('en_team_3','asu_v1'):'删除only及Lee负责API的归属，且增加对团队获奖的贡献表述。',
 ('en_points_2','pre_asu'):'把评测/观察准确率提升改成contributing to，新增促成提升的因果归属。',
 ('en_points_3','pre_asu'):'把评测/观察准确率提升改成contributing to，新增促成提升的因果归属。',
})

class RecordedPreservation:
    def __init__(self,rows):self.rows=rows
    def complete_structured(self,prompt,data,schema):
        return {cid:{'lost_supported_details':self.rows[cid]['lost_supported_details'],
                     'reason':self.rows[cid]['reason']} for cid in json.loads(data)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('run');args=parser.parse_args();run=Path(args.run)
    data={r['id']:r for r in json.loads((run/'dataset.json').read_text(encoding='utf8'))}
    reviewed=json.loads((ROOT/'eval/asu_ablation/adjudication-2026-10-30.json').read_text(encoding='utf8'))
    labels={(r['id'],r['arm']):r for r in reviewed['records']}
    now=datetime.now(timezone(timedelta(hours=8)));out=ROOT/'output/test-reports'/(now.strftime('%Y%m%d_%H%M%S_%f')+'_asu-reviewed-replay')
    out.mkdir(parents=True);records=[]
    for batch in sorted(run.glob('batch-*')):
        grades={(r['id'],r['arm']):r for r in json.loads((batch/'rows.json').read_text(encoding='utf8'))} if (batch/'rows.json').exists() else {}
        original_checks=json.loads((batch/'original-checks.json').read_text(encoding='utf8')) if (batch/'original-checks.json').exists() else {}
        for file in sorted(batch.glob('*-writing.json')):
            arm=file.stem.removesuffix('-writing');proposals=json.loads(file.read_text(encoding='utf8'))['proposals']
            claims,contexts,hits=fixture([data[c['claim_id'].removeprefix('claim_')] for c in proposals])
            changed=[c for c,p in zip(claims,proposals) if c['text']!=p['text']]
            model_file=batch/(arm+'-preserve-v1.json')
            legacy=json.loads(model_file.read_text(encoding='utf8')) if model_file.exists() else {}
            replay=preservation(RecordedPreservation(legacy),changed,proposals,hits,original_checks) if changed and all(c['claim_id'] in legacy for c in changed) else {}
            for claim,p in zip(claims,proposals):
                cid=claim['claim_id'];identifier=cid.removeprefix('claim_');key=(identifier,arm)
                if key not in labels or hashlib.sha256(p['text'].encode()).hexdigest()!=labels[key]['text_sha256']:
                    raise ValueError('New/changed output needs explicit adjudication; never default it to SAFE')
                label=labels[key]['label'];reason=labels[key]['review_reason']
                prior=grades.get(key);changed_text=claim['text']!=p['text'];has_replay=bool(prior) and (not changed_text or cid in replay)
                violations=proposal_violations(claim['text'],p['text'],hits[cid])
                accepted=(prior['proposal_relation']=='SUPPORTED' and not violations and not replay.get(cid,{}).get('lost_supported_details')) if has_replay else None
                records.append({'id':identifier,'arm':arm,'original':claim['text'],'proposal':p['text'],
                    'text_sha256':hashlib.sha256(p['text'].encode()).hexdigest(),'label':label,'review_reason':reason,
                    'changed':changed_text,'automated_audit':prior['audit'] if prior else None,
                    'old_accept':prior['old_guard_accept'] if prior else None,'replayed_v3_accept':accepted,
                    'replayed_losses':replay.get(cid),'replayed_violations':violations})
    paired=set.intersection(*[{r['id'] for r in records if r['arm']==a} for a in ARMS])
    primary=paired-{r['id'] for r in records if r['label']=='AMBIGUOUS'}
    complete_guards=set.intersection(*[{r['id'] for r in records if r['arm']==a and r['replayed_v3_accept'] is not None} for a in ARMS]) & primary
    writing={};guards={}
    for arm in ARMS:
        raw=[r for r in records if r['arm']==arm and r['id'] in primary]
        writing[arm]={'paired_n':len(raw),'changed':sum(r['changed'] for r in raw),'wrong':sum(r['label']=='WRONG' for r in raw),
            'including_ambiguous_n':len(paired),'wrong_upper_bound':sum(r['label']=='WRONG' for r in raw)+len(paired-primary)}
        group=[r for r in records if r['arm']==arm and r['id'] in complete_guards]
        wrong=[r for r in group if r['label']=='WRONG'];safe=[r for r in group if r['label']=='SAFE' and r['changed']]
        guards[arm]={'paired_n':len(group),'wrong_n':len(wrong),'safe_changed_n':len(safe),
            'old_retained_wrong':sum(r['old_accept'] for r in wrong),'replayed_retained_wrong':sum(r['replayed_v3_accept'] for r in wrong),
            'old_false_blocks':sum(not r['old_accept'] for r in safe),'replayed_false_blocks':sum(not r['replayed_v3_accept'] for r in safe)}
    report={'date':now.isoformat(),'status':'PARTIAL_REVIEWED_OFFLINE_REPLAY','input_run':str(run),
        'generated_outputs':len(records),'generation_pair_count':len(paired),'primary_pair_count':len(primary),
        'fully_checked_pair_count':len(complete_guards),'writing':writing,'guards':guards,'records':records,
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [ROOT/'backend/services/edit_invariants.py',ROOT/'backend/services/edit_guard.py',ROOT/'backend/services/asu_resume.py',Path(__file__)]},
        'limitations':['Assistant reviewed, not independent human gold; strict scope preservation rubric.',
            'One ambiguous template excluded from primary analysis for ALL arms.',
            'Guard replay uses the SAME cached v1 preservation-model responses and cached atomic verdicts; no paid calls.',
            'No score for new citation alignment or changed prompts: those need fresh end-to-end model runs.',
            'Trials encountered HTTP 403 insufficient balance; 60 paired cases have NOT completed.',
            'Seen failures informed fixes; replay is a regression diagnostic, not an unseen holdout.']}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['# ASu真实建议复核与离线重放','',f'- 日期：{report["date"]}（北京时间）',
        f'- 实际生成 {len(records)} 条建议；三组完整生成配对 {len(paired)} 条；排除一条歧义样本后主分析 {len(primary)} 条。',
        '- 复核者：Codex；不是独立人工标注。原自动评分保留，未覆盖。','',
        '| 写作策略 | 可比较样本 | 实际改写 | 错改（含关键信息丢失） |', '|---|---:|---:|---:|']
    for arm,m in writing.items():lines.append(f'| {arm} | {m["paired_n"]} | {m["changed"]} | {m["wrong"]} |')
    lines+=['','| 保护重放（完整配对） | 错改数 | 旧保护留下错改 | 新规则重放留下错改 | 安全改写数 | 旧误拦 | 新规则误拦 |','|---|---:|---:|---:|---:|---:|---:|']
    for arm,m in guards.items():lines.append(f'| {arm}（n={m["paired_n"]}） | {m["wrong_n"]} | {m["old_retained_wrong"]} | {m["replayed_retained_wrong"]} | {m["safe_changed_n"]} | {m["old_false_blocks"]} | {m["replayed_false_blocks"]} |')
    lines+=['','- 不能据此认定ASu降低错改率；配对样本很少，且评分器存在标点误判及遗漏限定语漏判。',
        '- 60条扩大对照已冻结，余额不足中断；完成后须另报未经开发调参的新样本结果。','']+['- '+v for v in report['limitations']]
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'records','source_sha256'}},ensure_ascii=True));print('REPORT '+str(out))

if __name__=='__main__':main()
