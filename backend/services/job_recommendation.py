"""Local content recommendation: candidate hydration, scoring and diverse selection.

Pipeline inspiration: xai-org/x-algorithm and twitter/the-algorithm; no upstream
production model or social engagement weights are included. Scores are not probabilities.
"""
from __future__ import annotations
import hashlib,json,os,re,sys,threading
from collections import Counter,OrderedDict
from backend.services.job_fit import compare, job_sections, project_profile
from datetime import datetime,timezone
from pathlib import Path

_LOCK=threading.RLock()
_STATES=OrderedDict()
_VECTORS=OrderedDict()
_COMPLETED=OrderedDict()

def locations():
    root=Path(__file__).resolve().parents[2]/'data/local/job-semantic'
    return (Path(os.getenv('APPLYGUARD_JOB_EMBEDDING_DIR',str(root/'model'))),
            Path(os.getenv('APPLYGUARD_JOB_EMBEDDING_PACKAGES',str(root/'packages'))))

def profile_texts(resume):
    if not isinstance(resume,dict):return []
    texts=[]
    for row in resume.get('education',[]):
        texts.append(' '.join(str(row.get(k) or '') for k in ('major','degree')))
    extra=resume.get('extras') or {}
    texts.extend(str(extra.get(k) or '') for k in ('skills','summary'))
    intention=resume.get('intention') or {}
    texts.append(str(intention.get('expectRole') or ''))
    for group in ('projects','internships'):
        for row in resume.get(group,[]):
            title=' '.join(str(row.get(k) or '') for k in ('title','role','techStack'))
            text=str(row.get('description') or '')
            texts.append(title)
            texts.extend(title+' '+text[i:i+260] for i in range(0,len(text),260))
    return list(dict.fromkeys(t.strip() for t in texts if t.strip()))

def job_text(job):
    duties = [phrase for section, phrase in job_sections(job) if section == "description"]
    qualifications = [phrase for section, phrase in job_sections(job) if section != "description"]
    return " ".join([str(job.get("title", "")), *(s[:96] for s in duties[:6]), *(s[:64] for s in qualifications[:4])]).strip()

def dot(a,b):return sum(x*y for x,y in zip(a,b))

def feedback_table(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS job_recommendation_feedback(job_id TEXT PRIMARY KEY,interest INTEGER NOT NULL,updated_at TEXT NOT NULL)')

def feedback(conn):
    feedback_table(conn)
    return {row['job_id']:row['interest'] for row in conn.execute('SELECT job_id,interest FROM job_recommendation_feedback')}

def save_feedback(conn,job_id,value):
    if type(value) is not int or value not in {-1,0,1}:raise ValueError('兴趣反馈只接受 -1、0、1')
    feedback_table(conn)
    conn.execute('INSERT INTO job_recommendation_feedback VALUES(?,?,?) ON CONFLICT(job_id) DO UPDATE SET interest=excluded.interest,updated_at=excluded.updated_at',
                 (job_id,value,datetime.now(timezone.utc).isoformat()))
    return {'interest':value}

def vectorize(texts):
    directory,packages=locations()
    if str(packages) not in sys.path and packages.is_dir():sys.path.append(str(packages))
    from backend.services.local_sag_embedding import LocalMiniLM,LocalEmbeddingConfig
    model=LocalMiniLM(LocalEmbeddingConfig(model='paraphrase-multilingual-MiniLM-L12-v2',schema_dimensions=384,model_directory=directory))
    model_key = str(directory.resolve())
    with _LOCK:
        resolved = {t: _VECTORS[(model_key,t)] for t in texts if (model_key,t) in _VECTORS}
    # Dynamic ONNX quantization uses the batch range. A fixed one-text batch keeps
    # the score independent of the cold-cache order and of other applicants.
    for item in dict.fromkeys(t for t in texts if t not in resolved):
        vector = model._embed([item])[0]
        resolved[item] = vector
        with _LOCK:
            _VECTORS[(model_key,item)] = vector
            while len(_VECTORS)>4096:
                _VECTORS.popitem(last=False)
    return [resolved[t] for t in texts]

def semantic_scores(texts,jobs):
    vectors=vectorize(texts+[job_text(job) for job in jobs])
    profile=vectors[:len(texts)]
    positive=[vectors[len(texts)+i] for i,job in enumerate(jobs) if job.get('interest')==1]
    negative=[vectors[len(texts)+i] for i,job in enumerate(jobs) if job.get('interest')==-1]
    scores={}
    for index,job in enumerate(jobs):
        vector=vectors[len(texts)+index]
        related=sorted((dot(vector,p) for p in profile),reverse=True)
        relevance=sum(related[:3])/min(3,len(related))
        affinity=sum(max(0,dot(vector,p)) for p in positive)/len(positive) if positive else 0
        aversion=max((max(0,dot(vector,p)) for p in negative),default=0)
        scores[job['id']]={'semantic':round(max(0,min(1,relevance))*100,2),'affinity':affinity,'aversion':aversion}
    return scores

def rerank(jobs):
    remaining=list(jobs);ordered=[];companies=Counter();titles=Counter()
    while remaining:
        def value(job):
            company=job.get('company','').casefold();title=re.sub(r'\s+','',job.get('title','')).casefold()
            penalty = min(3.5, .6 * companies[company] + 2.8 * titles[(company,title)])
            return (job['recommendation_score'] - penalty, job['recommendation_score'], job['id'])
        chosen=max(remaining,key=value);remaining.remove(chosen)
        chosen['recommendation_rank']=len(ordered)
        company=chosen.get('company','').casefold();title=re.sub(r'\s+','',chosen.get('title','')).casefold()
        companies[company]+=1;titles[(company,title)]+=1;ordered.append(chosen)
    return ordered

def decorate(jobs,resume,signals,scores=None):
    intention=(resume or {}).get('intention') or {}
    cities=[s.removesuffix('市') for s in re.split(r'[/、,，\s]+',str(intention.get('expectCity') or '')) if len(s)>1]
    profile = project_profile(resume)
    for job in jobs:
        technical=max(0,job.get('match_score') or 0)
        value=(scores or {}).get(job['id'])
        fit, reasons, domain_penalty = compare(job.get("title",""), job_sections(job), profile)
        reasons = list(reasons)
        base = technical if fit is None else .82 * fit + .18 * technical
        if value:
            base = .85 * base + .15 * value["semantic"]
        base -= domain_penalty
        if value:reasons.append(f"与专业、技能和项目描述的本地语义相关度 {value['semantic']:.0f}/100")
        if cities:
            matched=any(city in str(job.get('location','')) for city in cities)
            base+=4 if matched else -4;reasons.append('符合意向城市' if matched else '地点与意向城市不同')
        if value and value['affinity']:base+=10*value['affinity'];reasons.append('结合你标记感兴趣的岗位方向')
        if value and value['aversion']:base-=12*value['aversion']
        interest=signals.get(job['id'],0);job['interest']=interest
        if interest:base+=15 if interest==1 else -40;reasons.append('你标记了感兴趣' if interest==1 else '你选择了减少此类推荐')
        if job.get('details_available') is False:base-=12;reasons.append('岗位完整要求尚未读取')
        if job.get('stage')=='archived' or job.get('status') in {'closed','reference'}:base-=60;reasons.append('已归档或非在招岗位')
        job['recommendation_score']=round(max(0,min(100,base)),2)
        job['recommendation_reasons']=reasons or ['暂按技术记录排序；完善经历和偏好后可提高相关性']
    rerank(jobs)

def rank_jobs(jobs,resume,signals):
    texts=profile_texts(resume)
    directory,_=locations()
    if not texts:
        decorate(jobs,resume,signals)
        return {'state':'unavailable','notice':'请先保存经历库，推荐会使用专业、技能和项目描述。'}
    if not all((directory/file).is_file() for file in ('tokenizer.json','model_quantized.onnx')):
        decorate(jobs,resume,signals)
        return {'state':'unavailable','notice':'本地语义模型未安装，暂按技术记录和已填偏好排序。'}
    profile_key = hashlib.sha256(json.dumps([str(directory), texts, (resume or {}).get('intention'), sorted(signals.items())], sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    key = hashlib.sha256(json.dumps([profile_key, sorted((j['id'], j.get('content_hash'), job_text(j)) for j in jobs)], ensure_ascii=False).encode()).hexdigest()
    with _LOCK:
        state=_STATES.get(key)
        if state is None:
            state={'state':'loading','scores':None};_STATES[key]=state
            while len(_STATES)>4:_STATES.popitem(last=False)
            inputs=[{**job,'interest':signals.get(job['id'],0)} for job in jobs]
            def worker():
                try:
                    scores=semantic_scores(texts,inputs)
                    with _LOCK:state.update(state='ready',scores=scores)
                except Exception:
                    with _LOCK:state.update(state='failed',scores=None)
            threading.Thread(target=worker,daemon=True,name='job-semantic-ranking').start()
        snapshot=dict(state)
        previous = _COMPLETED.get(profile_key, {})
    decorate(jobs,resume,signals,snapshot['scores'])
    if snapshot["state"] == "ready":
        with _LOCK:
            _COMPLETED[profile_key] = {j["id"]: {k: j[k] for k in ("recommendation_rank", "recommendation_score", "recommendation_reasons")} for j in jobs}
            while len(_COMPLETED) > 4:
                _COMPLETED.popitem(last=False)
    elif previous:
        for job in jobs:
            if job["id"] in previous:
                job.update(previous[job["id"]])
            else:
                job["recommendation_rank"] += len(previous)
    notices={'loading':('沿用上次完成的排名，新岗位暂列其后。' if previous else '初步排序：已按核心职责与经历匹配，正在本机补充语义评分。'),'ready':'按材料语义、已填偏好与兴趣反馈排序，并适度打散同公司和重复岗位；推荐分不代表录用概率。','failed':'本地语义计算未完成，暂按技术记录和偏好排序；请检查模型运行依赖。'}
    return {'state':snapshot['state'],'notice':notices[snapshot['state']],'engine':'multilingual-MiniLM/local','profile_fingerprint':key[:12]}
