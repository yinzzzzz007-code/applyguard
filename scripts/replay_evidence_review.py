"""Reproduce a selected CV review in an empty local workspace; never auto-authorizes external accounts."""
import argparse, base64, getpass, hashlib, json, os, sys, threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from start_recording_workspace import configure, ROOT
from demo_budget import install


def evaluate(steps):
    checks = {}
    def successes(name):
        row = steps.get(name,{})
        return list(row.get('states',{}).values()) if not row.get('error') else []
    checks['new_wrong_link_refused'] = steps.get('new_mislink',{}).get('refused') is True
    checks['job_matched'] = steps.get('match',{}).get('requirements',0)>0
    for i in range(1,4):
        states = successes(f'verify_{i}')
        checks[f'wrong_project_and_missing_source_{i}'] = len(states)==3 and states[0]['excluded']>=1 and all(
            r['state']=='NEEDS_REVIEW' and r['sources']==0 for r in states[:2])
        checks[f'certificate_conflict_{i}'] = len(states)==3 and states[2]['sources']>0 and states[2]['state']=='BLOCKED' and states[2]['atoms']==states[2]['located']>0
        row=steps.get(f'repeated_{i}',{})
        anchors=row.get('anchors',[])
        checks[f'repeated_locations_{i}'] = any(len(a['offsets'])>=2 for a in anchors) and all(a['offsets'] and a['verbatim'] for a in anchors)
    ids=[steps.get(f'verify_{i}',{}).get('run_id') for i in range(1,4)]
    checks['independent_runs']=None not in ids and len(set(ids))==3
    rows=successes('polish')
    checks['rewrite_without_overriding_conflict']=len(rows)==3 and all(r['rewritten'] for r in rows[:2]) and not rows[2]['rewritten']
    checks['strict_mixed_refused']=steps.get('strict_conflict',{}).get('status')==422
    checks['strict_corrected_text']=steps.get('strict_supported_award',{}).get('matches') is True
    for stage in ('personal_export','skip_with_user_edit'):
        checks[stage]=steps.get(stage,{}).get('matches_final_text') is True
    checks['interview']=steps.get('predict',{}).get('questions',0)>0 and bool(steps.get('practice',{}).get('scores')) and steps.get('practice',{}).get('followup') is True and steps.get('retry',{}).get('returned_original') is True
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','cache','cv','certificate','transcription','foreign-readme'):
        parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    root=args.workspace.resolve()
    root.mkdir(parents=True,exist_ok=False)
    configure(root,args.cache.resolve(),0)
    os.environ['APPLYGUARD_AI_API_KEY']=getpass.getpass('ChatAnywhere key (hidden): ').strip()
    used=install(root)
    before=used()
    if before>=15:raise SystemExit('Cumulative limit reached')
    from backend import app
    from backend.services import evidence_workspace as ew
    from backend.services.resume_draft_vault import experiences_from_resume_draft
    server=app.create_server('127.0.0.1',0)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    report={'initial_ca':str(before),'steps':{}}
    def record(name,details):
        report['steps'][name]=details
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(name,flush=True)
    def post(path,payload):
        req=Request(f'http://127.0.0.1:{server.server_port}/api/v1/'+path,json.dumps(payload,ensure_ascii=False).encode(),{'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=650) as res:return json.load(res)
        except HTTPError as exc:return {'http_error':exc.code,**json.load(exc)}
    def pack(data):return base64.b64encode(data).decode()
    def summarize(out):
        ground=out.get('grounding',{})
        return {'run_id':ground.get('run_id'),'error':out.get('error') or ground.get('error'),
                'states':{key:{'state':v['state'],'scope':v.get('material_status'),'sources':len(v['retrieved_sources']),
                     'excluded':len(v['excluded_links']),'rewritten':bool(v.get('proposed_text') and v['proposed_text']!=v['original_text']),
                     'atoms':len(v['atoms']),'located':sum(bool(a.get('claim_spans')) for a in v['atoms'])}
                     for key,v in ground.get('results',{}).items()}}
    try:
        parsed=post('resume/parse',{'filename':args.cv.name,'pdf_base64':pack(args.cv.read_bytes()),'parse_mode':'offline'})
        form=parsed['form'];form['candidateId']='cand_recording_replay'
        for collection in ('education','projects','internships','awards'):
            for i,row in enumerate(form.get(collection,[])):row['id']=f'{collection}_{i}'
        record('import',{'chars':parsed['char_count'],'projects':len(form['projects']),'extractor':parsed.get('extractor')})
        blank=ew.create_workspace('复测专用')
        files=[{'relative_path':args.certificate.name,'content_base64':pack(args.certificate.read_bytes())},
               {'relative_path':'finbot-public-readme.md','content_base64':pack(args.foreign_readme.read_bytes())}]
        trans=json.loads(args.transcription.read_text('utf-8'))
        if trans['sha256']!=hashlib.sha256(args.certificate.read_bytes()).hexdigest():raise ValueError('证书与已对照的文字版本不符。')
        files[0]['ocr_sidecar_base64']=pack(json.dumps({'lines':trans['lines']}).encode())
        rows=ew.import_files(blank['workspace_id'],files)['files']
        items=experiences_from_resume_draft(form)
        selected=[]
        for term in ('ActionPersona','SocialMimic','Nemotron'):
            item=next(i for i in items if term.lower() in i['title'].lower())
            c=item['claims'][0];selected.append({'claim_id':c['claim_id'],'text':c['text']})
            if term=='SocialMimic':continue
            row=next(r for r in rows if r['relative_path']==(args.certificate.name if term=='Nemotron' else 'finbot-public-readme.md'))
            eid=row['evidence_id'];ew.review_evidence(eid,{'normalized_fields':{},'review_state':'REVIEWED'})
            ew.create_link({'evidence_id':eid,'target_type':'project','target_id':item['experience_id'].removeprefix('exp_')})
        saved=post('resume/draft',form)
        if saved.get('error'):raise ValueError(saved['error'])
        try:
            ew.create_link({'evidence_id':next(r['evidence_id'] for r in rows if r['relative_path']=='finbot-public-readme.md'),
                            'target_type':'project','target_id':next(p['id'] for p in form['projects'] if 'ActionPersona' in p['title'])})
        except ValueError as exc:record('new_mislink',{'refused':True,'message':str(exc)})
        else:record('new_mislink',{'refused':False})
        jd='大模型研发实习生：评估模型可靠性，分析实验数据，使用 Python、PyTorch 和 LoRA 开展训练与对照实验。'
        request={'candidate_id':form['candidateId'],'application_id':'app_recording_replay','resume_draft':form,'jd_text':jd,
                 'claims':selected,'grounding_mode':'sag_atomic','local_only':False}
        record('target',{'description':jd,'claims':len(selected)})
        matched=post('workflow/mock',{**request,'parse_mode':'offline','local_only':True})
        record('match',{'error':matched.get('error'),'requirements':len(matched.get('parsed_jd',{}).get('requirements',[]))})
        for i in range(3):
            out=post('workflow/reverify',request);record(f'verify_{i+1}',summarize(out))
        repeated = '在 NVIDIA Nemotron Model Reasoning Challenge 中获得银牌。获得银牌。团队排名 197/4,185。'
        for attempt in range(1,4):
            check=post('workflow/reverify',{**request,'claims':[{'claim_id':selected[-1]['claim_id'],'text':repeated}]})
            result=check.get('grounding',{}).get('results',{}).get(selected[-1]['claim_id'],{})
            atoms=result.get('atoms',[])
            record(f'repeated_{attempt}',{**summarize(check),'anchors':[
                {'offsets':[[p['start'],p['end']] for p in a.get('claim_spans',[])],
                 'verbatim':all(repeated[p['start']:p['end']]==p['quote'] for p in a.get('claim_spans',[])),
                 'reason':a.get('anchor_reason','')} for a in atoms]})
        polish=post('resume/polish',request);record('polish',summarize(polish))
        strict=post('resume/export',{**request,'human_confirmed':True,'export_policy':'verified'})
        record('strict_conflict',{'status':strict.get('http_error',200),'error':strict.get('error')})
        def export_personal(stage,claims):
            text='\n'.join(c['text'] for c in claims)
            result=post('resume/export',{**request,'claims':claims,'human_confirmed':True,'acknowledge_unverified':True,
                'confirmed_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'export_policy':'user_confirmed'})
            record(stage,{'matches_final_text':result.get('text')==text,'error':result.get('error')})
        export_personal('personal_export',selected)
        corrected=[{**c,'text':c['text'].replace('196/4,182','197/4,185')} for c in selected]
        export_personal('skip_with_user_edit',corrected)
        award={'claim_id':selected[-1]['claim_id'],'text':'在 NVIDIA Nemotron Model Reasoning Challenge 中获得银牌，团队排名 197/4,185。'}
        strict=post('resume/export',{**request,'claims':[award],'human_confirmed':True,'export_policy':'verified'})
        record('strict_supported_award',{'status':strict.get('http_error',200),'matches':strict.get('text')==award['text'],'error':strict.get('error')})
        resume={'projects':[{'title':c['text'].split('·')[0][:65],'description':c['text']} for c in corrected]}
        guide=post('interview/generate',{'jd_text':jd,'resume':resume})
        record('predict',{'questions':len(guide.get('questions',[])),'error':guide.get('error')})
        if 'practice' in guide:
            practice=guide['practice'];turn=post('interview/practice',{**practice,'action':'answer','answer':'我会先说明对照组、数据来源和评价指标。当前这段经历没有提供具体提升幅度，我会补看实验记录。'})
            record('practice',{'scores':turn.get('scores'),'followup':bool(turn.get('question')),'error':turn.get('error')})
            if 'revision' in turn:
                retry=post('interview/practice',{**practice,'revision':turn['revision'],'action':'retry'})
                record('retry',{'returned_original':retry.get('question')==practice['question']})
    finally:
        server.shutdown();server.server_close()
        record('meter',{'final_ca':str(used())})
        checks=evaluate(report['steps'])
        record('acceptance',checks)
    if not all(checks.values()):raise SystemExit('FAIL: '+', '.join(k for k,v in checks.items() if not v))
if __name__=='__main__':main()
