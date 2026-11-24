import hashlib
import re


def draft_phrases(text):
    matches = re.finditer(r'[^，。；;\n]+(?:[，。；;]|$)?', text)
    return {f'p{i}':{'start':m.start(), 'end':m.end(), 'quote':m.group()}
            for i,m in enumerate(matches,1) if m.group().strip()}


def bind_assertion(raw, draft, phrases):
    tag = re.match(r'^\[((?:p\d+)(?:\s*,\s*p\d+)*)\]\s*(.+)$', raw, re.S)
    text = tag[2].strip() if tag else raw.strip()
    ids = list(dict.fromkeys(re.split(r',\s*',tag[1]))) if tag else []
    version = hashlib.sha256(draft.encode()).hexdigest()
    result = {'text':text,'claim_text_sha256':version,'claim_spans':[], 'anchor_reason':''}
    if ids and all(k in phrases for k in ids):
        result['claim_spans'] = [dict(phrases[k], phrase_id=k) for k in ids]
    elif not ids and text and draft.count(text)==1:
        start = draft.index(text)
        result['claim_spans'] = [{'start':start, 'end':start+len(text), 'quote':text}]
    else:
        result['anchor_reason'] = ('invalid_phrase_id' if ids else 'empty_excerpt' if not text
                                   else 'ambiguous_excerpt' if draft.count(text)>1 else 'nonverbatim_without_phrase_id')
    if result['claim_spans']:
        result['claim_excerpt'] = result['claim_spans'][0]['quote']
    return result


def finalize_anchor(atom, draft, candidate):
    quote = candidate.strip()
    if not quote:
        atom['judge_anchor_status'] = 'empty_excerpt'
    elif quote not in draft:
        atom['judge_anchor_status'] = 'not_in_draft'
    elif draft.find(quote) != draft.rfind(quote):
        atom['judge_anchor_status'] = 'repeated_excerpt'
    else:
        atom['judge_anchor_status'] = 'unique'
        offset=draft.index(quote)
        if not atom['claim_spans'] or any(p['start'] <= offset and offset+len(quote) <= p['end'] for p in atom['claim_spans']):
            atom['claim_excerpt'] = quote
            if not atom['claim_spans']:
                atom['claim_spans']=[{'start':offset,'end':offset+len(quote),'quote':quote}]
                atom['anchor_reason']=''
    atom['judge_excerpt'] = quote
