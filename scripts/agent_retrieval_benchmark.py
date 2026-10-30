"""Deterministic connector benchmark, authored synthetic gold, no model calls."""
import json,sys,tempfile,time,statistics
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.services import agent_bridge as a
stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
out=ROOT/'output/test-reports'/(stamp+'_agent-retrieval-60');out.mkdir(parents=True)
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    for folder in ['repo','report','notes']:(root/folder).mkdir()
    cases=[]
    for i in range(60):
        project=f'Project{i:03d}';owner=f'Person{i:03d}'
        documents={f'repo/{project}.md':f'{project}: {owner} contributed SQL queries. Another person was the lead.',
                   f'report/{project}.md':f'{project}: Offline accuracy was 84 of 100. No production result is documented.',
                   f'notes/{project}.txt':f'{project}: earlier claim of 40% improvement was withdrawn; only 84% accuracy is recorded.'}
        for path,text in documents.items():(root/path).write_text(text,encoding='utf8')
        cases.append({'query':project,'expected':sorted(documents)})
    (out/'protocol.json').write_text(json.dumps({'created':stamp,'n':60,'files':180,'gold':cases,'annotation':'author-generated synthetic, not independent human annotation','metric':'document recall@20 with exact project identifier; connector lexical baseline, not LLM retrieval quality'},indent=2),encoding='utf8')
    c=a.create({'mode':'local','roots':[directory],'task':'Find synthetic project evidence','purpose':'contribution','disclosure':'isolated_local'})
    g=a.grant(c['id'],c['token']);rows=[]
    for case in cases:
        start=time.monotonic();found=a.search(g,case['query']);elapsed=time.monotonic()-start
        paths={r['source']['path'].replace('\\','/') for r in found['cards']};expected=set(case['expected'])
        rows.append({'query':case['query'],'recalled':len(paths&expected),'expected':3,'wrong_project':len(paths-expected),'seconds':elapsed,'errors':found['errors']})
    a.ui_call({**c,'action':'revoke'})
    times=sorted(r['seconds'] for r in rows)
    report={'date':datetime.now(timezone(timedelta(hours=8))).isoformat(),'cases':60,'documents':180,'recalled':sum(r['recalled'] for r in rows),'expected':180,
            'wrong_project_hits':sum(r['wrong_project'] for r in rows),'median_seconds':statistics.median(times),'p95_seconds':times[56],
            'rows':rows,'limitation':'Exact project names; no synonym/multihop/large-tree benchmark; wrong-project retrieval is not personal-attribution error.'}
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k!='rows'}));print('REPORT',out)
