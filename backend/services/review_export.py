"""User-owned draft export. A confirmation never becomes factual verification."""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone


def export_user_draft(vault_path, request):
    from backend.services.reverification import reverify_workflow
    if request.get('human_confirmed') is not True or request.get('acknowledge_unverified') is not True:
        raise ValueError('请确认最终正文，并知晓材料不足或冲突会保留记录')
    # Rebuild ownership, identifiers, text and local evidence integrity on the server.
    # No model call is needed to export user-authored text, even if the model is unavailable.
    result = reverify_workflow(vault_path, request, _skip_grounding=True)
    claims = result['resume_claims']
    if not claims:
        raise ValueError('草稿为空，无法导出')
    text = '\n'.join(claim['text'] for claim in claims)
    digest = hashlib.sha256(text.encode()).hexdigest()
    if request.get('confirmed_text_sha256') != digest:
        raise ValueError('确认的文字与导出正文不一致，请重新确认')
    checks = {v['claim_id']: v for v in result['claim_verification']}
    records = []
    for claim in claims:
        check = checks[claim['claim_id']]
        records.append({'claim_id':claim['claim_id'], 'text':claim['text'],
            'user_confirmed':True, 'material_support':'NOT_ATOMICALLY_VERIFIED',
            'local_rule_state':check['state'], 'local_rule_explanation':check['explanation'],
            'evidence_ids':claim['evidence_ids']})
    return {'text':text, 'sha256':digest, 'export_policy':'user_confirmed', 'user_confirmed':True,
        'material_support':'NOT_ATOMICALLY_VERIFIED', 'trace_id':result['trace_id'],
        'review_record':{'created_at':datetime.now(timezone.utc).isoformat(),
            'candidate_id':request['candidate_id'], 'application_id':request.get('application_id'),
            'text_sha256':digest, 'claims':records, 'verification_method':'fresh_local_rules_only',
            'notice':'本次只刷新本地材料规则检查；不将人工确认或旧模型结果当成当前原子事实核验通过。'},
        'notice':'已按用户确认导出最终草稿；材料不足和冲突不因此变成通过。没有向招聘平台投递。'}
