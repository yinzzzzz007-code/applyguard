"""Download cited benchmark sources; freeze sampling before any model calls."""
from pathlib import Path
import bz2
import hashlib
import io
import json
import random
import sys
import urllib.request
import zipfile
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'data/local/expanded-eval'
OUT=ROOT/'output/expanded-eval'
SEED=20261030
URLS={
 'felm.zip':'https://huggingface.co/datasets/sjtu-lit/felm/resolve/main/data.zip',
 'felm-official.jsonl':'https://huggingface.co/datasets/hkust-nlp/felm/resolve/main/all.jsonl',
 'crag.jsonl.bz2':'https://raw.githubusercontent.com/facebookresearch/CRAG/ad1518887dd4d9ebcd7de95388c7a62751e7705c/example_data/dev_data.jsonl.bz2',
 'upstream.json':'https://api.github.com/repos/yinzzzzz007-code/applyguard/commits/main',
}

def digest(data):return hashlib.sha256(data).hexdigest()

def download():
    LOCAL.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    manifest={}
    for name,url in URLS.items():
        path=LOCAL/name
        if not path.exists():
            req=urllib.request.Request(url,headers={'User-Agent':'ApplyGuard-local-research'})
            with urllib.request.urlopen(req,timeout=90) as response:data=response.read(20_000_001)
            if len(data)>20_000_000:raise ValueError('Source exceeded bounded download')
            path.write_bytes(data)
        data=path.read_bytes()
        manifest[name]={'url':url,'sha256':digest(data),'bytes':len(data)}
    (OUT/'source-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

def inspect():
    manifest=download()
    with zipfile.ZipFile(LOCAL/'felm.zip') as z:
        data={d:[json.loads(s) for s in z.read('data/test/'+d+'.jsonl').decode().splitlines() if s]
            for d in ['wk','science','math','reasoning','writing_rec']}
    stats={}
    for domain,rows in data.items():
        stats[domain]={'records':len(rows),'example_keys':list(rows[0]),'negative_records':sum(False in r.get('labels',[]) for r in rows)}
    official=[json.loads(s) for s in (LOCAL/'felm-official.jsonl').read_text(encoding='utf-8').split('\n') if s]
    crag=[json.loads(s) for s in bz2.decompress((LOCAL/'crag.jsonl.bz2').read_bytes()).decode().splitlines() if s]
    upstream=json.loads((LOCAL/'upstream.json').read_text(encoding='utf-8'))
    print(json.dumps({'download':manifest,'felm':stats,'official':{'rows':len(official),'keys':list(official[0])},
        'crag':{'rows':len(crag),'keys':list(crag[0])},
        'upstream':{'sha':upstream['sha'],'date':upstream['commit']['committer']['date']}},ensure_ascii=False,indent=2))

def freeze():
    sys.path.insert(0,str(ROOT))
    from scripts.evaluate_external_benchmark_pilot import _read_felm, _sample_felm
    from eval.career_holdout import RECORDS
    from backend.services.atomic_verifier import ATOM_PROMPT, JUDGE_PROMPT, POLISH_PROMPT
    download()
    raw,domains,excluded=_read_felm(LOCAL/'felm.zip')
    prior={(r['domain'],r['record_id']) for r in _sample_felm(domains)}
    rng=random.Random(SEED);selected=[];exclusions=Counter()
    for domain,rows in domains.items():
        used=set()
        for label in [False,True]:
            pool=[]
            for row in rows:
                if row['label'] != label:continue
                if (domain,row['record_id']) in prior:exclusions['prior_record']+=1;continue
                if not 5 <= len(row['segment']) <= 420:exclusions['claim_length']+=1;continue
                if not label and len(row['comment'])>6000:exclusions['annotation_length']+=1;continue
                pool.append(row)
            rng.shuffle(pool);taken=[]
            for row in pool:
                if row['record_id'] in used:continue
                used.add(row['record_id']);taken.append(row)
                if len(taken)==20:break
            if len(taken)!=20:raise ValueError(f'{domain}/{label} only {len(taken)} eligible distinct records')
            for row in taken:
                selected.append({**row,'id':f"felm_{domain}_{row['record_id']}_{row['segment_index']}",
                    'evidence':('Source assertion: '+row['segment'] if label else 'Annotation correction: '+row['comment']),
                    'gold':'SUPPORTED' if label else 'NOT_SUPPORTED'})
    career=[]
    for record in RECORDS:
        for label,rows in [('SUPPORTED',record['good']),('NOT_SUPPORTED',record['bad'])]:
            for n,row in enumerate(rows):
                category,text=row[:2]
                career.append({'id':f"career_{record['id']}_{'p' if label=='SUPPORTED' else 'n'}{n}",
                    'record_id':record['id'],'category':category,'text':text,'gold':label,
                    'relation':row[2] if len(row)>2 else 'SUPPORTED'})
    data={'sampling_seed':SEED,'felm':selected,'career':career,'career_records':RECORDS,
        'source_zip_sha256':digest(raw),'excluded_misaligned_records':excluded,'exclusions':dict(exclusions),
        'annotation':'FELM original labels with annotation-conditioned sources; career cases author-labelled, not independent annotation',
        'protocol':'FELM: fixed evidence stress test, not retrieval or official FELM score. Career: real SAG retrieval with identical cached hits for whole-claim and atomic checks. Polish paired original and edited checks; automatic auditor is not human gold.'}
    path=LOCAL/'frozen-dataset.json'
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old!=data:raise ValueError('Frozen dataset differs; create a new version instead of overwriting')
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    manifest={'seed':SEED,'dataset_sha256':digest(path.read_bytes()),'felm':len(selected),'career':len(career),
        'felm_ids':[{'id':r['id'],'domain':r['domain'],'gold':r['gold']} for r in selected],
        'career_ids':[{'id':r['id'],'record_id':r['record_id'],'gold':r['gold']} for r in career],
        'excluded_misaligned_records':excluded,'exclusions':dict(exclusions),'prior_felm_records_excluded':sorted(prior),
        'v1_prompts_sha256':digest((ATOM_PROMPT+JUDGE_PROMPT+POLISH_PROMPT).encode())}
    (OUT/'frozen-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in manifest.items() if not k.endswith('_ids') and not k.startswith('prior_')},ensure_ascii=False))

if __name__=='__main__':freeze() if '--freeze' in sys.argv else inspect()
