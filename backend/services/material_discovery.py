"""Use the installed SAG engine to propose original documents before association."""
import json
import logging
import time
from uuid import uuid4
from backend.services import evidence_workspace as workspace
from backend.services.resume_draft_vault import experiences_from_resume_draft, _safe_id
from backend.services.sag_grounding import SAGRetriever, fingerprint
from backend.services.evidence_scope import matches_item, suggest_project_identity
from backend.services.local_store import local_dir


def discover(request, retriever=None):
    started=time.monotonic()
    if request.get('local_only') is not False:
        raise ValueError('请先确认将材料和经历发送给配置的模型服务。')
    form=request.get('resume_draft')
    candidate=request.get('candidate_id')
    if not isinstance(form,dict) or not candidate:
        raise ValueError('请先导入经历库。')
    items=experiences_from_resume_draft(form)
    if any(item['candidate_id']!=candidate for item in items):
        raise ValueError('经历库不属于当前候选人。')
    requested={row.get('claim_id'):str(row.get('text') or '')[:420] for row in request.get('claims',[]) if isinstance(row,dict)}
    targets={_safe_id('exp_',str(row['id']),'item'):(kind,str(row['id']))
             for name,kind in [('projects','project'),('internships','internship'),('awards','award')]
             for row in form.get(name,[]) if row.get('id')}
    sources=[]
    for space in workspace.list_workspaces():
        for file in workspace.list_files(space['workspace_id']):
            if not file.get('evidence_id') or file['state'] in {'FAILED','STALE'}:continue
            record=workspace.get_evidence(file['evidence_id'])
            spans=sorted(record['spans'],key=lambda s:(s.get('page') or 0,s.get('line_start') or 0))
            text='\n'.join(s['raw_text'] for s in spans).strip()
            if not text:continue
            sources.append({'source_id':'src_'+fingerprint([file['evidence_id'],file['sha256']])[:32],
                'evidence_id':file['evidence_id'],'candidate_id':candidate,'experience_id':'exp_material_discovery',
                'title':file['relative_path'],'text':text,'sha256':file['sha256'],'version':file['version']})
    if len(sources)>60 or sum(len(s['text']) for s in sources)>120000:
        raise ValueError('材料超过本次检索范围，请先按项目整理到较小的材料库。')
    queries=[]; lookup={}
    for item in items:
        target=targets.get(item['experience_id'])
        if not target:continue
        for claim in item['claims']:
            if claim['claim_id'] not in requested:continue
            queries.append({'claim_id':claim['claim_id'],'text':item['title']+'\n'+(requested[claim['claim_id']] or item['summary']),
                            'source_ids':[s['source_id'] for s in sources]})
            lookup[claim['claim_id']]=(item,target)
    engine=retriever or SAGRetriever()
    hits=engine.retrieve_many(queries,sources,candidate)
    canonical={s['source_id']:s for s in sources}
    owners={s['source_id']:{item['experience_id'] for item in items if item['experience_id'] in targets and
        (matches_item(item['title'],s['title'],s['text'],kind=targets[item['experience_id']][0],organization=item.get('organization',''))
         or suggest_project_identity(item['title'],s['title'],s['text']))} for s in sources}
    rows=[]; ambiguous=[]; excluded=0
    for cid,found in hits.items():
        if cid not in lookup:continue
        item,target=lookup[cid];seen=set();uncertain=set()
        for hit in found:
            source=canonical.get(hit.get('source_id'))
            if not source or source['evidence_id'] in seen:continue
            if hit.get('text')!=source['text']:continue
            if item['experience_id'] not in owners[source['source_id']]:
                excluded+=1
                if not owners[source['source_id']] and len(uncertain)<2 and not any(word in source['title'] for word in ('总览','材料说明','项目清单')):
                    uncertain.add(source['evidence_id'])
                    ambiguous.append({'target_type':target[0],'target_id':target[1],'label':item['title'],
                        'status':'NEEDS_CONFIRM','score':0,'evidence_id':source['evidence_id'],
                        'relative_path':source['title'],'file_sha256':source['sha256'],
                        'notes':['仅为语义线索：尚未确认属于同一项目，请勿仅因技术词相似就关联。'],
                        'action':'先核对是否属于同一项目','quote':source['text'][:2400]})
                continue
            seen.add(source['evidence_id'])
            rows.append({'target_type':target[0],'target_id':target[1],'label':item['title'],
                'status':'NEEDS_CONFIRM','score':0,'evidence_id':source['evidence_id'],
                'relative_path':source['title'],'file_sha256':source['sha256'],
                'notes':['SAG 语义检索候选，尚未确认项目归属或事实支持。'],
                'action':'核对原文和项目归属后选择关联','quote':source['text'][:2400]})
            if len(seen)>=3:break
    result={'run_id':uuid4().hex,'results':rows,'unresolved_candidates':ambiguous,'source_count':len(sources),'query_count':len(queries),'engine':'zleap.sag',
            'stats':{**engine.stats,'excluded_project_mismatch':excluded},'notice':'检索结果仅为候选，确认关联后才用于原子核验。'}
    try:
        folder=local_dir()/'material-discovery-runs';folder.mkdir(parents=True,exist_ok=True)
        audit={**result,'elapsed_ms':round((time.monotonic()-started)*1000),'snapshot':fingerprint(sources)}
        for name in ('results','unresolved_candidates'):
            audit[name]=[{k:v for k,v in row.items() if k!='quote'} for row in result[name]]
        (folder/(result['run_id']+'.json')).write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    except OSError:
        logging.warning('Could not save material discovery summary')
    return result
