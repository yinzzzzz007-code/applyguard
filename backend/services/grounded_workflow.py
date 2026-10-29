# Gitvextor的原型：SAG 集成、事实核验与错改保护（姜凌天，2026-10-30）。
# Third-party methods and licenses: see THIRD_PARTY_NOTICES.md.
"""SAG polishing and atomic verification wired into actual workflow/risk controls."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path

from backend.services.atomic_verifier import AtomicVerifier, ATOM_PROMPT, JUDGE_PROMPT
from backend.services.career_vault import CareerVault
from backend.services.local_evidence import vault_evidence_id
from backend.services.model_client import HttpModelClient, ModelFailure
from backend.services.resume_draft_vault import experiences_from_resume_draft, _safe_id
from backend.services.sag_grounding import SAGRetriever, GroundingUnavailable, evidence_snapshot, fingerprint


def grounding_mode(request: dict) -> str:
    configured = os.getenv('APPLYGUARD_GROUNDING_MODE', 'off')
    requested = request.get('grounding_mode', configured)
    if requested not in {'off', 'sag', 'sag_atomic'} or configured not in {'off', 'sag', 'sag_atomic'}:
        raise ValueError('grounding_mode必须为off、sag或sag_atomic')
    # Server policy can require atomic checks; a client cannot downgrade it.
    return 'sag_atomic' if configured == 'sag_atomic' else requested


def load_grounding_experiences(vault_path: Path, request: dict) -> list[dict]:
    """Check source provenance independently of whether an old draft is supported."""
    candidate = request['candidate_id']
    draft = request.get('resume_draft')
    if not isinstance(draft, dict):
        return CareerVault.from_json(vault_path).list_experiences(candidate)
    items = experiences_from_resume_draft(draft)
    if not items or any(item['candidate_id'] != candidate for item in items):
        raise ValueError('简历草稿为空或候选人不一致')
    from backend.services import evidence_workspace as workspace
    targets = {}
    for collection, kind in [('projects','project'), ('internships','internship'), ('awards','award')]:
        for row in draft.get(collection) or []:
            if isinstance(row, dict) and row.get('id'):
                targets[_safe_id('exp_',str(row['id']),'item')] = (kind,str(row['id']))
    links = workspace.list_links()['links']
    for item in items:
        target = targets.get(item['experience_id'])
        if not target:continue
        combined = {}
        for claim in item['claims']:
            accepted = []
            applicable = [link for link in links if link['link_state'] == 'ACTIVE' and
                (link['target_type'],link['target_id']) in {target,('experience',target[1]),('claim',claim['claim_id'])}]
            for link in applicable:
                # Neutral text triggers integrity/version/link checks, without treating
                # a lexical verdict on the old draft as the source's truth status.
                check = workspace.check_claim_support('材料完整性检查',link['evidence_id'],
                    target_type=link['target_type'],target_id=link['target_id'])
                record = check['evidence']
                file = record.get('file')
                if (check['status'] in {'STALE','CONFLICT'} or record['review_state'] != 'REVIEWED'
                        or not file or file['state'] != 'INDEXED'):
                    continue
                with workspace._db() as conn:
                    rows = conn.execute('SELECT * FROM source_span WHERE file_id=? ORDER BY page,line_start,rowid',
                        (file['file_id'],)).fetchall()
                # Include the complete parsed original, including correction context.
                text = '\n'.join(row['raw_text'] for row in rows)
                if not text.strip():continue
                positions, offset = [], 0
                for row in rows:
                    positions.append({'start':offset,'end':offset + len(row['raw_text']),
                        'span_id':row['span_id'],'page':row['page'],
                        'line_start':row['line_start'],'line_end':row['line_end']})
                    offset += len(row['raw_text']) + 1
                alias = vault_evidence_id(link['evidence_id'])
                combined[alias] = {'evidence_id':alias,'description':text,'verification_status':'VERIFIED',
                    'confidence':.9,'type':'DOCUMENT','source_type':'DOCUMENT','uri':None,
                    'source_reference':'local-evidence://' + link['evidence_id'],
                    '_positions':positions,'_file_id':file['file_id'],
                    '_file_version':file['version'],'_file_sha256':file['sha256'],
                    '_version':fingerprint([file['sha256'],file['version'],record.get('reviewed_at'),
                        record.get('normalized_fields'),link['linked_at'],link['file_sha256']])}
                accepted.append(alias)
            claim['evidence_ids'] = sorted(set(accepted))
        item['evidence_sources'] = list(combined.values())
    return items


def collect_sources(items: list[dict], candidate: str):
    sources, contexts, allowed = [], {}, {}
    for experience in items:
        if experience.get('candidate_id') != candidate:continue
        by_evidence = {}
        for source in experience.get('evidence_sources', []):
            eid = source['evidence_id']
            text = source.get('description', '')
            if (eid.startswith('ev_draft_') or source.get('verification_status') != 'VERIFIED'
                    or not isinstance(text,str) or not text.strip()):
                continue
            sid = 'src_' + fingerprint([candidate,experience['experience_id'],eid])[:32]
            row = {'source_id':sid,'evidence_id':eid,'candidate_id':candidate,
                'experience_id':experience['experience_id'],'title':experience['title'],'text':text,
                'sha256':hashlib.sha256(text.encode()).hexdigest(),'version':source.get('_version','vault'),
                'positions':source.get('_positions',[]),'file_id':source.get('_file_id'),
                'file_version':source.get('_file_version'),'file_sha256':source.get('_file_sha256')}
            by_evidence[eid] = row
            if not any(s['source_id'] == sid for s in sources):sources.append(row)
        for claim in experience.get('claims', []):
            cid = claim['claim_id']
            if cid in contexts:raise ValueError('陈述编号在候选人经历中不唯一')
            contexts[cid] = {'candidate_id':candidate,'experience_id':experience['experience_id'],
                'project':experience['title'],'organization':experience['organization']}
            required = claim.get('evidence_ids', [])
            # Required references must remain valid. Also search other reviewed originals
            # of this same experience: a later correction may not be cited by the old draft.
            allowed[cid] = ([row['source_id'] for row in by_evidence.values()]
                if required and all(eid in by_evidence for eid in required) else [])
    if len(sources) > 60 or sum(len(s['text']) for s in sources) > 120_000:
        raise GroundingUnavailable('本次原件过多，请按经历分批核验；未截断证据上下文。')
    return sources, contexts, allowed


class GroundingService:
    def __init__(self, *, retriever=None, model=None):
        self.retriever = retriever if retriever is not None else SAGRetriever()
        self.model = model if model is not None else HttpModelClient(
            max_tokens=int(os.getenv('APPLYGUARD_GROUNDING_MAX_TOKENS','6000')), require_complete=True)

    def retrieve(self, claims, sources, allowed, candidate):
        queries = [{'claim_id':c['claim_id'],'text':c['text'],'source_ids':allowed.get(c['claim_id'],[])} for c in claims]
        returned = self.retriever.retrieve_many(queries,sources,candidate)
        canonical = {s['source_id']:s for s in sources}
        result = {}
        for claim in claims:
            cid = claim['claim_id']
            hits = []
            for hit in returned.get(cid, []):
                sid = hit.get('source_id')
                source = canonical.get(sid)
                text = hit.get('text','')
                if (source and sid in allowed.get(cid,[]) and isinstance(text,str) and text.strip()
                        and text in source['text']):
                    hits.append({**source,'text':text,'text_offset':source['text'].find(text),
                        'chunk_id':str(hit.get('chunk_id','')),
                        'retrieval_channels':[v for v in hit.get('retrieval_channels',[])
                            if v in {'support','refutation','correction'}]})
            result[cid] = hits
        return result

    def run(self, claims, items, candidate, mode, *, jd='', polish=False):
        sources, contexts, allowed = collect_sources(items,candidate)
        snapshot = evidence_snapshot(sources)
        active = [c for c in claims if c['claim_id'] in contexts and allowed.get(c['claim_id'])]
        error = None
        hits, atomic = {}, {}
        original_text = {c['claim_id']:c['text'] for c in claims}
        originals = copy.deepcopy(claims)
        proposals, proposal_checks, preservation_checks = {}, {}, {}
        try:
            hits = self.retrieve(active,sources,allowed,candidate)
            if polish and active:
                polished = AtomicVerifier(self.model).polish(active,contexts,hits,jd)
                changed = {c['claim_id']:c for c in polished}
                proposals = copy.deepcopy(changed)
                claims = [changed.get(c['claim_id'],c) for c in claims]
                active = [changed[c['claim_id']] for c in active]
                hits = self.retrieve(active,sources,allowed,candidate)
            if mode == 'sag_atomic' and active:
                atomic = AtomicVerifier(self.model).verify(active,contexts,hits)
            if polish and proposals:
                from backend.services.edit_guard import preservation
                proposal_checks = copy.deepcopy(atomic)
                changed_originals = [c for c in originals if c['claim_id'] in proposals
                    and c['text'] != proposals[c['claim_id']]['text']]
                if mode == 'sag_atomic':
                    preservation_checks = preservation(self.model,changed_originals,list(proposals.values()),hits)
                rejected = {c['claim_id'] for c in changed_originals if mode != 'sag_atomic'
                    or atomic.get(c['claim_id'],{}).get('relation') != 'SUPPORTED'
                    or preservation_checks.get(c['claim_id'],{}).get('lost_supported_details')}
                fallback = [c for c in originals if c['claim_id'] in rejected]
                if fallback:
                    restored = {c['claim_id']:c for c in fallback}
                    claims = [restored.get(c['claim_id'],c) for c in claims]
                    fallback_hits = self.retrieve(fallback,sources,allowed,candidate)
                    hits.update(fallback_hits)
                    if mode == 'sag_atomic':
                        atomic.update(AtomicVerifier(self.model).verify(fallback,contexts,fallback_hits))
        except (GroundingUnavailable,ModelFailure,OSError,ValueError,TypeError,KeyError):
            # No fallback to a stale VERIFIED result, even for unchanged old text.
            error = 'SAG或模型核验未完成；当前文本不可按已核验内容导出。请检查配置后重试。'
            if polish:claims = originals;atomic = {}
        results, verifications = {}, []
        for claim in claims:
            cid = claim['claim_id']
            row = atomic.get(cid, {'atoms':[],'complete':False,'relation':'INSUFFICIENT',
                'claim_text_sha256':fingerprint(claim['text'])})
            if cid not in contexts or not allowed.get(cid):
                state, explanation = 'BLOCKED','当前陈述没有候选人所属经历的有效原件；草稿、JD及人工点击不能补足证据。'
            elif error:
                state, explanation = 'NEEDS_REVIEW',error
            elif mode == 'sag':
                state, explanation = 'NEEDS_REVIEW','SAG仅完成原文检索；采用或导出前请运行SAG＋原子事实核验。'
            else:
                state = {'SUPPORTED':'VERIFIED','CONTRADICTED':'BLOCKED','INSUFFICIENT':'NEEDS_REVIEW'}[row['relation']]
                explanation = {'VERIFIED':'所有已拆分事实及完整性检查通过，逐字引文来自当前经历原件；请人工核对后使用。',
                    'BLOCKED':'至少一项原子事实与当前原件矛盾，禁止导出。',
                    'NEEDS_REVIEW':'至少一项事实证据不足、引用无效或拆分不完整，尚不可导出。'}[state]
            claim['evidence_ids'] = sorted({s['evidence_id'] for s in sources if s['source_id'] in allowed.get(cid,[])})
            claim['status'] = 'BLOCKED' if state == 'BLOCKED' else 'DRAFT'
            unsupported = [a['text'] for a in row['atoms'] if a['relation'] != 'SUPPORTED']
            if state == 'BLOCKED' and not unsupported:unsupported = [claim['text']]
            verifications.append({'claim_id':cid,'state':state,'grounded':state == 'VERIFIED',
                'support_score':1.0 if state == 'VERIFIED' else 0.0,
                'unsupported_fragments':unsupported,'explanation':explanation})
            results[cid] = {**row,'state':state,'retrieved_sources':hits.get(cid,[]),
                'original_text':original_text[cid],'final_text':claim['text']}
            if cid in proposals:
                from backend.services.edit_guard import change_audit
                proposed = proposals[cid]['text']
                results[cid].update(proposed_text=proposed,proposal_check=proposal_checks.get(cid),
                    preservation=preservation_checks.get(cid),change_audit=change_audit(original_text[cid],proposed),
                    proposal_applied=not error and proposed==claim['text'],
                    proposal_rejected=proposed!=claim['text'],
                    proposal_notice='建议未通过核验或信息保留检查，已保留原文；原文状态单独核验。' if proposed!=claim['text'] else '')
        from backend.services.structured_verifier import SPLIT_PROMPT, CHECK_PROMPT
        from backend.services.edit_guard import PRESERVE_PROMPT
        return claims, verifications, {'mode':mode,'engine':'zleap-sag 0.15.0','snapshot':snapshot,
            'prompt_version':fingerprint([ATOM_PROMPT,JUDGE_PROMPT,SPLIT_PROMPT,CHECK_PROMPT,PRESERVE_PROMPT]),'results':results,'error':error,
            'export_requires_atomic':True}


def apply_grounding(vault_path, request, response, *, polish=False):
    mode = grounding_mode(request)
    if mode == 'off':return response
    items = load_grounding_experiences(vault_path,request)
    out = copy.deepcopy(response)
    claims, verified, report = GroundingService().run(out['resume_claims'],items,request['candidate_id'],mode,
        jd=request.get('jd_text',''),polish=polish)
    # Check for source replacement/revocation while network calls were in progress.
    current, _, _ = collect_sources(load_grounding_experiences(vault_path,request),request['candidate_id'])
    if evidence_snapshot(current) != report['snapshot']:
        report['error'] = '核验过程中材料或关联已变化，请重新核验。'
        for result in verified:
            result.update(state='NEEDS_REVIEW',grounded=False,support_score=0.0,explanation=report['error'])
            report['results'][result['claim_id']]['state'] = 'NEEDS_REVIEW'
    from backend.services.reverification import simulator_mapping
    from backend.services.risk_engine import RiskEngine
    from backend.services.schema_validation import validate_contract
    mapping = simulator_mapping(out.get('application_id') or request.get('application_id','app_demo_001'),claims)
    engine = RiskEngine()
    for control,field in zip(engine.field_controls(mapping,verified),mapping['fields']):
        field['action'] = control['action']
    if any(v['state'] == 'BLOCKED' for v in verified):mapping['consistency_state'] = 'BLOCKED'
    # Existing explicit evidence-conflict flags remain blocking.
    risk = engine.assess(mapping['application_id'],verified,mapping,out['evidence_match'])
    for result in verified:validate_contract('claim-verification',result)
    validate_contract('form-mapping',mapping)
    strict_ready = bool(verified) and all(v['state'] == 'VERIFIED' for v in verified) and not report['error']
    blocked = risk['action'] == 'BLOCKED'
    out.update(resume_claims=claims,claim_verification=verified,grounding=report,
        ats_form_mapping=mapping,field_controls=engine.field_controls(mapping,verified),risk_result=risk,
        requires_reverification=False,workflow_status='BLOCKED' if blocked else 'AWAITING_HUMAN_CONFIRMATION',
        human_confirmation={'required':True,'reason':'请核对逐事实引文；待复核状态不能通过人工点击直接导出。',
            'allowed_actions':['CONFIRM','EDIT','CANCEL'] if strict_ready and not blocked else ['EDIT','CANCEL']})
    out['component_modes'] = {**out.get('component_modes',{}),'claim_grounding':mode.upper()}
    out['evidence_sources'] = [{k:v for k,v in source.items() if not k.startswith('_')}
        for item in items for source in item.get('evidence_sources',[])]
    for step in out.get('step_trace',[]):
        if step['step'] == 'Human Confirmation':step['status'] = 'PENDING' if strict_ready and not blocked else 'BLOCKED'
        if step['step'] == 'Claim Validator':step['mode'] = mode.upper()
    return out


def polish_workflow(vault_path, request):
    from backend.services.reverification import reverify_workflow
    mode = grounding_mode(request)
    if mode == 'off':raise ValueError('润色请选择sag或sag_atomic模式')
    # Reconstruct IDs and refs server-side; the grounding pass replaces lexical verdicts.
    base = reverify_workflow(vault_path,{**request,'grounding_mode':'off'},_skip_grounding=True)
    return apply_grounding(vault_path,request,base,polish=True)


def export_grounded(vault_path, request):
    from backend.services.reverification import reverify_workflow
    if request.get('human_confirmed') is not True:
        raise ValueError('导出前请明确确认已核对最终正文与证据')
    result = reverify_workflow(vault_path,{**request,'grounding_mode':'sag_atomic'})
    verified = result['claim_verification']
    if (not verified or result['grounding'].get('error') or result['risk_result']['action'] == 'BLOCKED'
            or any(row['state'] != 'VERIFIED' for row in verified)):
        raise ValueError('最终文本尚未全部通过原子事实核验，不能导出；人工确认不能覆盖此状态')
    # The server returns its reconstructed final text, not a client-provided export body.
    text = '\n'.join(claim['text'] for claim in result['resume_claims'])
    return {'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),
        'evidence_snapshot':result['grounding']['snapshot'],'grounding_mode':'sag_atomic',
        'trace_id':result['trace_id'],'notice':'本地文本导出；没有向招聘平台投递。'}
