# Gitvextor的原型：SAG 集成、事实核验与错改保护（姜凌天，2026-10-30）。
# Third-party methods and licenses: see THIRD_PARTY_NOTICES.md.
"""SAG polishing and atomic verification wired into actual workflow/risk controls."""
from __future__ import annotations
import copy
from collections import Counter
import hashlib
import json
import os
import re
from pathlib import Path

from backend.services.atomic_verifier import AtomicVerifier, ATOM_PROMPT, JUDGE_PROMPT
from backend.services.career_vault import CareerVault
from backend.services.wording_review import JUDGE, REPAIR, review_edit, may_apply_wording
from backend.services.local_evidence import vault_evidence_id
from backend.services.model_client import HttpModelClient, ModelFailure
from backend.services.resume_draft_vault import (
    claim_is_form_confirmed,
    experiences_from_resume_draft,
    is_form_confirmed_evidence,
    _safe_id,
)
from backend.services.sag_grounding import SAGRetriever, GroundingUnavailable, evidence_snapshot, fingerprint

_MODEL_UNAVAILABLE = 'MODEL_SERVICE_UNAVAILABLE'
_MODEL_UNAVAILABLE_MESSAGE = '模型服务暂时不可用，事实核验尚未完成。请稍后重试。'

_HIGH_RISK = re.compile(r'\d|[%％]|主导|负责|协助|参与|领导|成果|提升|降低|上线|部署|试点|离线|预计|未|不|'
    r'\b(?:lead|led|own|owned|assist|help|contribut|achiev|deliver|improv|reduc|deploy|pilot|offline|'
    r'planned|estimated|not|never|Python|SQL|Java|Go|Rust|Spark|Redis|Docker)\w*\b', re.I)
_ENGLISH_NAME = re.compile(r'\b[A-Z][a-z]{1,24}\b')


def high_risk_edit(original: str, proposal: str) -> bool:
    """Route changed factual language to a second judge; never grant approval itself."""
    from backend.services.edit_guard import change_audit
    changed = any(_HIGH_RISK.search(part) for change in change_audit(original, proposal)['changes']
                  for part in change.values())
    # Character diffs can split a word (wrote -> led); compare whole tokens too.
    old = Counter(m.group().casefold() for m in _HIGH_RISK.finditer(original))
    new = Counter(m.group().casefold() for m in _HIGH_RISK.finditer(proposal))
    names_changed = Counter(_ENGLISH_NAME.findall(original)) != Counter(_ENGLISH_NAME.findall(proposal))
    return changed or old != new or names_changed


def grounding_mode(request: dict) -> str:
    configured = os.getenv('APPLYGUARD_GROUNDING_MODE', 'sag_atomic')
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
                (not link.get('candidate_id') or link['candidate_id']==candidate) and
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
                from backend.services.evidence_scope import matches_item, source_identity
                filename = file['relative_path']
                origin, original_body = source_identity(filename, text)
                if not link.get('association_confirmed') and not matches_item(item['title'],filename,text,kind=target[0],organization=item.get('organization',''),
                                    description=str(next((r.get('description','') for k in ('projects','internships','awards') for r in draft.get(k,[]) if r.get('id')==target[1]),''))):
                    item.setdefault('_excluded_links', {})[link['evidence_id']] = {
                        'evidence_id':link['evidence_id'], 'filename':filename, 'version':file['version'],
                        'sha256':file['sha256'], 'project':item['title'], 'origin':origin,
                        'reason':'材料原文和来源未标明本经历，已从核验范围排除。'}
                    continue
                positions, offset = [], 0
                for row in rows:
                    positions.append({'start':offset,'end':offset + len(row['raw_text']),
                        'span_id':row['span_id'],'page':row['page'],
                        'line_start':row['line_start'],'line_end':row['line_end']})
                    offset += len(row['raw_text']) + 1
                body_offset = len(text) - len(original_body)
                if body_offset:
                    positions = [{**p,'start':max(0,p['start']-body_offset),'end':p['end']-body_offset}
                                 for p in positions if p['end']>body_offset]
                text = original_body
                alias = vault_evidence_id(link['evidence_id'])
                prior_scope=combined.get(alias,{}).get('_claim_scope')
                scope=([] if prior_scope==[] or link['target_type']!='claim' else sorted(set((prior_scope or [])+[claim['claim_id']])))
                combined[alias] = {'evidence_id':alias,'description':text,'verification_status':'VERIFIED',
                    'confidence':.9,'type':'DOCUMENT','source_type':'DOCUMENT','uri':None,
                    'source_reference':'local-evidence://' + link['evidence_id'],
                    '_filename':filename, '_origin':origin, '_claim_scope':scope,
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
        # Personal/education profile text never enters SAG indexes or model contexts.
        if experience.get('claims') and all(
                claim_is_form_confirmed(c['claim_id'], [experience]) for c in experience['claims']):
            continue
        by_evidence = {}
        for source in experience.get('evidence_sources', []):
            eid = source['evidence_id']
            text = source.get('description', '')
            if eid.startswith('ev_draft_') or is_form_confirmed_evidence(source):
                continue
            if source.get('verification_status') != 'VERIFIED' or not isinstance(text, str) or not text.strip():
                continue
            sid = 'src_' + fingerprint([candidate,experience['experience_id'],eid])[:32]
            row = {'source_id':sid,'evidence_id':eid,'candidate_id':candidate,
                'experience_id':experience['experience_id'],'title':source.get('_filename') or source.get('title') or source.get('source_reference') or eid,'origin':source.get('_origin',{}),'text':text,
                'sha256':hashlib.sha256(text.encode()).hexdigest(),'version':source.get('_version','vault'),
                'claim_scope':source.get('_claim_scope',[]),'positions':source.get('_positions',[]),'file_id':source.get('_file_id'),
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
            allowed[cid] = ([row['source_id'] for row in by_evidence.values() if not row.get('claim_scope') or cid in row['claim_scope']]
                if required and all(eid in by_evidence for eid in required) else [])
    if len(sources) > 60 or sum(len(s['text']) for s in sources) > 120_000:
        raise GroundingUnavailable('本次原件过多，请按经历分批核验；未截断证据上下文。')
    return sources, contexts, allowed


class GroundingService:
    def __init__(self, *, retriever=None, model=None):
        self.retriever = retriever if retriever is not None else SAGRetriever()
        self._model = model

    @property
    def model(self):
        if self._model is None:
            self._model = HttpModelClient(
                max_tokens=int(os.getenv('APPLYGUARD_GROUNDING_MAX_TOKENS','6000')), require_complete=True, task='complex')
        return self._model

    @model.setter
    def model(self, value):
        self._model = value

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

    def run(self, claims, items, candidate, mode, *, jd='', polish=False, local_only=False, fresh_atomic=False):
        sources, contexts, allowed = collect_sources(items,candidate)
        personal = {c['claim_id']:c for item in items if item.get('candidate_id') == candidate
                    for c in item.get('claims', []) if claim_is_form_confirmed(c['claim_id'], [item])}
        snapshot = evidence_snapshot(sources)
        active = [c for c in claims if c['claim_id'] in contexts and allowed.get(c['claim_id'])]
        source_free = {}
        error = None
        error_code = None
        hits, atomic = {}, {}
        excluded = {c['claim_id']:list(i.get('_excluded_links',{}).values()) for i in items for c in i.get('claims',[])}
        original_text = {c['claim_id']:c['text'] for c in claims}
        originals = copy.deepcopy(claims)
        proposals, proposal_checks, preservation_checks = {}, {}, {}
        original_checks = {}
        polish_source = None
        polish_violations = {}
        original_hits = {}
        risk_escalation = {}
        refchecker_reviews = {}
        wording = {}
        applied_wording = set()
        empty_check = {'relation':'INSUFFICIENT', 'complete':False, 'atoms':[]}
        reused_checks = set()
        stage = '材料检索'
        polishable = [c for c in claims if c['claim_id'] not in personal]
        for claim in polishable:
            contexts.setdefault(claim['claim_id'], {'candidate_id':candidate,'experience_id':'',
                'project':'用户手写内容','organization':''})
        try:
            if local_only and active:
                error = '当前为全离线模式。材料已关联。若需模型核验，请回到岗位说明选择 AI 模式、确认后重新分析。'
            hits = self.retrieve(active,sources,allowed,candidate) if active and not local_only else {}
            original_hits = copy.deepcopy(hits)
            if polish and polishable and not local_only:
                stage = '原文原子核验'
                if mode == 'sag_atomic' and active:
                    original_checks = AtomicVerifier(self.model).verify(active,contexts,hits)
                for claim in polishable:
                    original_checks.setdefault(claim['claim_id'], {**empty_check,
                        'claim_text_sha256':hashlib.sha256(claim['text'].encode()).hexdigest()})
                stage = '润色生成'
                polisher = AtomicVerifier(self.model)
                polished = polisher.polish(polishable,contexts,hits,jd,original_checks=original_checks)
                polish_source = polisher.polish_source
                polish_violations = polisher.polish_violations
                changed = {c['claim_id']:c for c in polished}
                proposals = copy.deepcopy(changed)
                stage = '改写核验'
                if mode == 'sag_atomic':
                    from backend.services.asu_resume import proposal_violations
                    from backend.services.fact_lock import locked_edit_findings
                    for cid, proposal in changed.items():
                        if proposal['text'] == original_text[cid]:
                            continue
                        text, wording[cid] = review_edit(getattr(self.model, 'wording_step', None),
                                                         original_text[cid], proposal['text'])
                        if text != proposal['text']:
                            from backend.services.asu_resume import polish_quality
                            repair_quality = polish_quality(original_text[cid], text)
                            if repair_quality:
                                wording[cid]['equivalent'] = False
                                wording[cid]['repair_quality_issues'] = repair_quality
                            else:
                                proposal['text'] = text
                                polish_violations[cid] = (proposal_violations(original_text[cid], text, hits.get(cid, []))
                                    + locked_edit_findings(original_text[cid], text, original_checks[cid]))
                proposals = copy.deepcopy(changed)
                claims = [changed.get(c['claim_id'],c) for c in claims]
                active = [changed[c['claim_id']] for c in active]
                changed_active = [c for c in active if c['text'] != original_text[c['claim_id']]]
                if changed_active:hits.update(self.retrieve(changed_active,sources,allowed,candidate))
            if mode == 'sag_atomic' and active and not local_only:
                # Reuse only checks computed in THIS call against its immutable
                # source snapshot. apply_grounding rechecks revocation afterward.
                unchanged = [c for c in active if polish and c['text']==original_text[c['claim_id']]]
                reused_checks.update(c['claim_id'] for c in unchanged)
                atomic = {c['claim_id']:copy.deepcopy(original_checks[c['claim_id']]) for c in unchanged}
                pending = [c for c in active if c['claim_id'] not in atomic]
                if pending:
                    stage = '改写核验' if polish else '原子事实核验'
                    atomic.update(AtomicVerifier(self.model).verify(pending,contexts,hits))
            if fresh_atomic and mode == 'sag_atomic' and not polish and not local_only:
                pending_sources = [c for c in polishable if not allowed.get(c['claim_id'])]
                if pending_sources:
                    from backend.services.structured_verifier import split_without_sources
                    stage = '无材料陈述的事实拆分'
                    source_free = split_without_sources(self.model, pending_sources)
            if polish and proposals:
                from backend.services.edit_guard import preservation
                proposal_checks = copy.deepcopy(atomic)
                changed_originals = [c for c in originals if c['claim_id'] in proposals
                    and c['text'] != proposals[c['claim_id']]['text']]
                escalated_rejections = set()
                strong_name = os.getenv('APPLYGUARD_STRONG_AI_MODEL', '').strip()
                if mode == 'sag_atomic' and strong_name:
                    high_risk = [proposals[c['claim_id']] for c in changed_originals
                                 if c['claim_id'] in atomic and high_risk_edit(c['text'], proposals[c['claim_id']]['text'])]
                    if high_risk:
                        try:
                            strong = HttpModelClient(model=strong_name,
                                max_tokens=int(os.getenv('APPLYGUARD_GROUNDING_MAX_TOKENS','6000')),
                                require_complete=True)
                            second = AtomicVerifier(strong).verify(high_risk, contexts, hits)
                            for claim in high_risk:
                                cid = claim['claim_id']
                                relation = second[cid]['relation']
                                risk_escalation[cid] = {'model':strong_name, 'relation':relation,
                                    'agrees_with_primary':relation == atomic[cid]['relation']}
                                if relation != 'SUPPORTED':escalated_rejections.add(cid)
                        except (GroundingUnavailable, ModelFailure, OSError, ValueError, TypeError, KeyError):
                            escalated_rejections.update(c['claim_id'] for c in high_risk)
                            for claim in high_risk:
                                risk_escalation[claim['claim_id']] = {'model':strong_name,
                                    'relation':'INSUFFICIENT', 'error':'强模型复核未完成；建议未采用。'}
                if mode == 'sag_atomic':
                    # Incomplete/absent originals have no complete inventory of supported facts.
                    # Keep their source status separate; do not contaminate other sentences.
                    comparable = [c for c in changed_originals if original_checks[c['claim_id']].get('complete')]
                    preservation_checks = preservation(self.model,comparable,list(proposals.values()),hits,original_checks)
                for original in changed_originals:
                    cid = original['claim_id']
                    final_check = atomic.get(cid, empty_check)
                    refchecker_blocked = False
                    if mode == 'sag_atomic' and os.getenv('APPLYGUARD_REFCHECKER_AUDIT', '').strip().lower() in {'1', 'true', 'yes'}:
                        from backend.services.refchecker_review import review_refchecker
                        refchecker_reviews[cid] = review_refchecker(self.model, proposals[cid]['text'], final_check)
                        refchecker_blocked = refchecker_reviews[cid]['relation'] != 'Entailment'
                    if mode == 'sag_atomic' and may_apply_wording(
                        wording.get(cid, {}), original_checks[cid], final_check,
                        polish_violations.get(cid), cid in escalated_rejections or refchecker_blocked,
                        original_text[cid], proposals[cid]['text'], preservation_checks.get(cid, {})
                    ):
                        applied_wording.add(cid)
                        # A stylistic change cannot promote an unsupported original.
                        if original_checks[cid]['relation'] != 'SUPPORTED' and final_check['relation'] == 'SUPPORTED':
                            atomic[cid] = {**final_check, 'relation':'INSUFFICIENT',
                                           'support_notice':'原句依据不足；此处仅确认表达等价。'}
                rejected = {c['claim_id'] for c in changed_originals} - applied_wording
                fallback = [c for c in originals if c['claim_id'] in rejected]
                if fallback:
                    restored = {c['claim_id']:c for c in fallback}
                    claims = [restored.get(c['claim_id'],c) for c in claims]
                    fallback_hits = {c['claim_id']:original_hits.get(c['claim_id'], []) for c in fallback}
                    hits.update(fallback_hits)
                    if mode == 'sag_atomic':
                        atomic.update({c['claim_id']:copy.deepcopy(original_checks[c['claim_id']]) for c in fallback})
                        reused_checks.update(restored)
        except (GroundingUnavailable,ModelFailure,OSError,ValueError,TypeError,KeyError) as exc:
            from backend.services.verification_audit import save_failure
            save_failure(stage, exc)
            # No fallback to a stale VERIFIED result, even for unchanged old text.
            if isinstance(exc, ModelFailure) and exc.http_status == 503:
                error_code = _MODEL_UNAVAILABLE
                error = _MODEL_UNAVAILABLE_MESSAGE
            elif isinstance(exc, ModelFailure):
                error_code = exc.code or {401:'MODEL_AUTH', 403:'MODEL_AUTH', 429:'MODEL_RATE_LIMIT'}.get(exc.http_status, 'MODEL_RESPONSE')
                error = {
                    'MODEL_KEY_MISSING': '后端缺少模型密钥。配置密钥并重启服务后，再次启动核验。',
                    'MODEL_AUTH': '模型服务拒绝了当前密钥。请检查后端密钥和模型访问权限后重试。',
                    'MODEL_RATE_LIMIT': '模型服务暂时限流，请稍后再次启动核验。',
                    'MODEL_BUDGET_LIMIT': '本次演示的模型预算已用尽。请先检查用量与预算，再启动核验。',
                    'MODEL_BUDGET_UNAVAILABLE': '暂时无法确认模型用量，本次调用已暂停。请稍后重试。',
                    'MODEL_TIMEOUT': '等待模型回复超时。正文已保留，请再次启动核验。',
                    'MODEL_CONNECTION': '后端未能连接模型服务。请检查网络后再次启动核验。',
                }.get(error_code, '模型未返回可用的核验结果。正文已保留，请再次启动核验。')
            elif isinstance(exc, GroundingUnavailable):
                error_code = 'SAG_RETRIEVAL' if stage == '材料检索' else 'VERIFICATION_INCOMPLETE'
                error = str(exc)
            else:
                error = 'SAG或模型核验未完成；当前文本不可按已核验内容导出。请检查配置后重试。'
            if polish:
                claims = originals;atomic = {}
                if stage in {'材料检索', '原文原子核验'} and not proposals and polishable and not local_only:
                    try:
                        for claim in polishable:
                            original_checks.setdefault(claim['claim_id'], {**empty_check,
                                'claim_text_sha256':hashlib.sha256(claim['text'].encode()).hexdigest()})
                        polisher = AtomicVerifier(self.model)
                        fallback = polisher.polish(polishable,contexts,hits,jd,original_checks=original_checks)
                        polish_source = polisher.polish_source
                        polish_violations = polisher.polish_violations
                        proposals = {c['claim_id']:c for c in fallback}
                    except (GroundingUnavailable,ModelFailure,OSError,ValueError,TypeError,KeyError):
                        proposals = {}
                cause = error
                if proposals:
                    error = f'{stage}未完成（{cause}）；建议仅供人工对照，尚未核验。'
                else:
                    error = f'{stage}未完成（{cause}）；本次没有生成润色建议，原文已保留。'
        results, verifications = {}, []
        for claim in claims:
            cid = claim['claim_id']
            row = atomic.get(cid, {'atoms':[],'complete':False,'relation':'INSUFFICIENT',
                'claim_text_sha256':fingerprint(claim['text'])})
            is_personal = cid in personal
            if is_personal:
                unchanged = claim['text'] == personal[cid]['text']
                state = 'VERIFIED' if unchanged else 'BLOCKED'
                explanation = ('个人资料按表单填写使用，不进行SAG核验或AI润色。' if unchanged
                               else '请在个人资料表单修改后重新载入，不能借用个人资料编号填写经历陈述。')
                row = {**row, 'complete': False, 'atoms': [], 'relation': 'INSUFFICIENT'}
            elif cid not in contexts or not allowed.get(cid):
                from backend.services.draft_anchors import draft_phrases
                row={**row, 'claim_text_sha256':hashlib.sha256(claim['text'].encode()).hexdigest(), 'atoms':[
                    {'atom_id':k,'text':p['quote'],'claim_excerpt':p['quote'],'claim_spans':[p], 'relation':'INSUFFICIENT',
                     'reason':'暂无相关材料，保留此处原文供补证。','citations':[], 'method':'draft_fragment'}
                    for k,p in draft_phrases(claim['text']).items()]}
                if cid in source_free:
                    row = source_free[cid]
                state, explanation = 'NEEDS_REVIEW', error or '暂无相关材料。请补充能识别本经历的原件，或继续使用个人稿。'
            elif error:
                state, explanation = 'NEEDS_REVIEW',error
            elif mode == 'sag':
                state, explanation = 'NEEDS_REVIEW','SAG仅完成原文检索；采用或导出前请运行SAG＋原子事实核验。'
            else:
                state = {'SUPPORTED':'VERIFIED','CONTRADICTED':'BLOCKED','INSUFFICIENT':'NEEDS_REVIEW'}[row['relation']]
                explanation = {'VERIFIED':'所有已拆分事实及完整性检查通过，逐字引文来自当前经历原件；请人工核对后使用。',
                    'BLOCKED':'至少一项事实与原件矛盾。请查看引文，可编辑后按用户确认稿导出。',
                    'NEEDS_REVIEW':'证据不足、引用无效或拆分不完整。可按用户确认稿导出，材料状态单独记录。'}[state]
            claim['evidence_ids'] = (personal[cid]['evidence_ids'] if is_personal else
                sorted({s['evidence_id'] for s in sources if s['source_id'] in allowed.get(cid,[])}))
            claim['status'] = 'BLOCKED' if state == 'BLOCKED' else 'DRAFT'
            unsupported = [a['text'] for a in row['atoms'] if a['relation'] != 'SUPPORTED']
            if state == 'BLOCKED' and not unsupported:unsupported = [claim['text']]
            verifications.append({'claim_id':cid,'state':state,'grounded':state == 'VERIFIED' and not is_personal,
                'support_score':1.0 if state == 'VERIFIED' and not is_personal else 0.0,
                'unsupported_fragments':unsupported,'explanation':explanation})
            results[cid] = {**row,'state':state,'verification_scope':'personal' if is_personal else 'experience',
                'scope_notice':explanation if is_personal else '', 'retrieved_sources':hits.get(cid,[]),
                'excluded_links':excluded.get(cid,[]),
                'material_status':'profile' if is_personal else 'no_related_material' if not allowed.get(cid) else 'service_error' if error else 'checked',
                'original_text':original_text[cid],'final_text':claim['text'],
                'reused_current_run_original_check':cid in reused_checks}
            if cid in proposals:
                from backend.services.edit_guard import change_audit
                proposed = proposals[cid]['text']
                results[cid].update(proposed_text=proposed,proposal_check=proposal_checks.get(cid),
                    original_check=original_checks.get(cid),
                    wording_auto_restored=(not error and proposed != claim['text'] and
                        claim['text'] == original_text[cid] and
                        wording.get(cid, {}).get('repair_outcome') == 'restored_original'),
                    wording_review=wording.get(cid), wording_auto_applied=cid in applied_wording and not error,
                    proposal_constraint_violations=polish_violations.get(cid,[]),
                    risk_escalation=risk_escalation.get(cid),
                    refchecker_review=refchecker_reviews.get(cid),
                    preservation=preservation_checks.get(cid),change_audit=change_audit(original_text[cid],proposed),
                    proposal_applied=not error and proposed==claim['text'],
                    proposal_rejected=proposed!=claim['text'],
                    proposal_notice=('原文与材料存在冲突，请先核对来源；此条暂不润色。' if cid in (polish_source or {}).get('conflict_claim_ids',[])
                        else '模型建议改变了年份，已保留原文，请先核对材料。' if cid in (polish_source or {}).get('year_drift_claim_ids',[])
                        else ('；'.join(polish_violations[cid]) if polish_violations.get(cid)
                            else '逐项复核未确认支持，已保留原文；请人工核对。' if refchecker_reviews.get(cid, {}).get('relation') in {'Neutral', 'Contradiction', 'Abstain'}
                            else '建议未确认事实等价，已保留原文；原文状态单独核验。') if proposed!=claim['text'] else ''))
        from backend.services.structured_verifier import SPLIT_PROMPT, CHECK_PROMPT
        from backend.services.atomic_verifier import POLISH_PROMPT
        from backend.services.edit_guard import PRESERVE_PROMPT
        return claims, verifications, {'mode':mode,'engine':'zleap-sag 0.15.0','snapshot':snapshot,
            'prompt_version':fingerprint(['numeric-coverage-grouped-ascii-v2','model-source-payload-v1',ATOM_PROMPT,JUDGE_PROMPT,JUDGE,REPAIR,SPLIT_PROMPT,CHECK_PROMPT,PRESERVE_PROMPT,POLISH_PROMPT,polish_source]),
            'polish_source':polish_source,'results':results,'error':error,'error_code':error_code,
            'failure_stage':stage if error else None,
            'export_requires_atomic':True, 'model_routing':{
                'requested_model':getattr(self._model,'model',None),
                'response_models':sorted(getattr(self._model,'response_models',[])),
                'max_output_tokens':getattr(self._model,'max_tokens',None)}}


def apply_grounding(vault_path, request, response, *, polish=False):
    mode = grounding_mode(request)
    if mode == 'off':return response
    items = load_grounding_experiences(vault_path,request)
    from time import monotonic
    started = monotonic()
    fresh = request.get('fresh_atomic') is True and mode == 'sag_atomic' and not polish and request.get('local_only') is not True
    out = copy.deepcopy(response)
    claims, verified, report = GroundingService().run(out['resume_claims'],items,request['candidate_id'],mode,
        jd=request.get('jd_text',''),polish=polish,local_only=request.get('local_only') is True and not polish, fresh_atomic=fresh)
    # Check for source replacement/revocation while network calls were in progress.
    current, _, _ = collect_sources(load_grounding_experiences(vault_path,request),request['candidate_id'])
    if evidence_snapshot(current) != report['snapshot']:
        report['error'] = '核验过程中材料或关联已变化，请重新核验。'
        report['error_code'] = None
        for result in verified:
            if report['results'][result['claim_id']].get('verification_scope') == 'personal':continue
            result.update(state='NEEDS_REVIEW',grounded=False,support_score=0.0,explanation=report['error'])
            cid = result['claim_id']
            row = report['results'][cid]
            if polish and row.get('wording_auto_applied'):
                claim = next(c for c in claims if c['claim_id'] == cid)
                claim['text'] = row['original_text']
                row.update(final_text=claim['text'], proposal_rejected=True, proposal_applied=False)
            row.update(state='NEEDS_REVIEW', relation='INSUFFICIENT', wording_auto_applied=False,
                       wording_auto_restored=False)

    from backend.services.verification_audit import save_run
    report.update(fresh_atomic=fresh, elapsed_ms=round((monotonic() - started) * 1000))
    save_run(report, request['candidate_id'], polish=polish)
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
        human_confirmation={'required':True,'reason':'请核对引文。已核验稿要求材料支持；用户确认稿可在编辑并确认最终文字后单独导出。',
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
    policy = request.get('export_policy', 'verified')
    if policy == 'user_confirmed':
        from backend.services.review_export import export_user_draft
        return export_user_draft(vault_path, request)
    if policy != 'verified':
        raise ValueError('未知导出策略')
    if request.get('fresh_atomic') is not True:
        from backend.services.verification_audit import current_conflict
        base = reverify_workflow(vault_path, request, _skip_grounding=True)
        sources, _, _ = collect_sources(load_grounding_experiences(vault_path,request),request['candidate_id'])
        if current_conflict(request['candidate_id'],base['resume_claims'],evidence_snapshot(sources)):
            raise ValueError('当前正文仍有与当前材料一致的已记录冲突，不能严格导出。请修改后重新核验，或选择用户确认稿。')
    result = reverify_workflow(vault_path,{**request,'grounding_mode':'sag_atomic'})
    verified = result['claim_verification']
    if result['grounding'].get('error_code') == _MODEL_UNAVAILABLE:
        raise GroundingUnavailable(_MODEL_UNAVAILABLE_MESSAGE)
    if result['grounding'].get('error'):
        raise GroundingUnavailable(result['grounding']['error'])
    if (not verified or result['risk_result']['action'] == 'BLOCKED'
            or any(row['state'] != 'VERIFIED' for row in verified)):
        raise ValueError('仅已核验稿要求全部事实通过原子核验。请复核材料，或选择用户确认稿导出。')
    # The server returns its reconstructed final text, not a client-provided export body.
    text = '\n'.join(claim['text'] for claim in result['resume_claims'])
    return {'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),
        'evidence_snapshot':result['grounding']['snapshot'],'grounding_mode':'sag_atomic',
        'trace_id':result['trace_id'],'notice':'本地文本导出；没有向招聘平台投递。'}
