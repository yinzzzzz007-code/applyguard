"""Adapt explicitly linked local originals to the frozen Career Vault contract."""
from __future__ import annotations

import copy
import re
from typing import Any
from backend.services import evidence_workspace as workspace


def vault_evidence_id(local_id: str) -> str:
    return 'ev_local_' + local_id.removeprefix('evloc_')


def attach_local_evidence(experiences: list[dict[str, Any]], draft: dict[str, Any]) -> list[dict[str, Any]]:
    items = copy.deepcopy(experiences)
    # Scope joins to the stable IDs of entries actually supplied by this candidate.
    targets = {}
    from backend.services.resume_draft_vault import _safe_id
    for collection, kind in (('projects', 'project'), ('internships', 'internship'), ('awards', 'award')):
        for row in draft.get(collection) or []:
            if isinstance(row, dict) and row.get('id'):
                targets[_safe_id('exp_', str(row['id']), 'item')] = (kind, str(row['id']))
    links = workspace.list_links()['links']
    for item in items:
        target = targets.get(item['experience_id'])
        if target is None:
            continue
        for claim in item['claims']:
            applicable = [link for link in links if
                          (link['target_type'], link['target_id']) in
                          {target, ('experience', target[1]), ('claim', claim['claim_id'])}]
            sources = []
            for link in applicable:
                local_id = link['evidence_id']
                check = workspace.check_claim_support(claim['text'], local_id,
                                                      target_type=link['target_type'], target_id=link['target_id'])
                # A rejected/stale link must never contribute support.
                if link['link_state'] != 'ACTIVE' or not check['supported']:
                    continue
                record = check['evidence']
                alias = vault_evidence_id(local_id)
                if any(source['evidence_id'] == alias for source in sources):
                    continue
                sources.append({'evidence_id': alias, 'type': 'DOCUMENT', 'source_type': 'DOCUMENT',
                                'description': '\n'.join(span['raw_text'] for span in record['spans']),
                                'source_reference': 'local-evidence://' + local_id, 'uri': None,
                                'confidence': .9, 'verification_status': 'VERIFIED'})
            if sources:
                item['evidence_sources'] = sources
                claim['evidence_ids'] = [source['evidence_id'] for source in sources]
                claim['verification_state'] = 'VERIFIED'
                claim['confidence'] = .9
                item['verification_state'] = 'VERIFIED'
                # Extract only literal skills stated by the now-supported sentence.
                from backend.services.jd_parser import _TERMS, _TERM_ALIASES
                local_aliases = {'HTTP API': ('接口服务',), 'automated testing': ('自动化测试', '单元测试'),
                                 'Git': ('版本协作', '版本控制'), 'data pipelines': ('数据管道',)}
                item['skills'] = [term for term in _TERMS if any(
                    re.search(r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])', claim['text'], re.I)
                    for alias in (*_TERM_ALIASES.get(term, (term,)), *local_aliases.get(term, ())))]
    return items
