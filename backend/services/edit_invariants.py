# Gitvextor的原型：限定语保留及可证明的数字等价，2026-10-30。
"""Narrow edit checks; no regex match establishes factual truth or authorship."""
import re
from decimal import Decimal

# A family requires the same meaning, not merely a shared negative word.
QUALIFIERS = {
    'not_implemented': r'尚未实施|未(?:正式)?实施|尚未落地|未付诸实施|尚未执行|未执行该方案|尚未(?:开始|启动)|not\s+(?:yet\s+)?implemented|unimplemented|(?:has|have|had)\s+not\s+(?:yet\s+)?(?:started|begun)',
    'estimated': r'预计|预估|估算|预测|测算|估计|estimat(?:e[ds]?|ing|ion)|projected|projecting|forecast(?:ed)?|expected',
    'offline': r'离线|offline',
    'prototype': r'原型|概念验证|proof.of.concept|prototype|\bPoC\b',
    'not_deployed': r'未(?:正式)?(?:上线|部署)|尚未(?:上线|部署)|未进入生产|未投产|未发布到生产|not\s+(?:yet\s+)?(?:deployed|released)|(?:did\s+not|never)\s+deploy|no\s+production\s+deployment',
    'not_trained': r'未(?:参与|负责|进行)(?:模型)?训练|未训练|(?:did\s+not|never)\s+train|not\s+(?:involved\s+in\s+)?(?:model\s+)?training|without\s+(?:(?:participating|being\s+involved)\s+in\s+)?(?:model\s+)?training',
    'assisting': r'协助|辅助|assisted|supported\s+(?:the\s+)?team|helped',
    'not_leader': r'非(?:项目)?负责人|并非(?:项目)?负责人|未(?:主导|领导)|不是(?:项目)?负责人|not\s+(?:the\s+)?(?:project\s+)?lead(?:er)?|did\s+not\s+lead',
    'pilot': r'试点|试运行|pilot',
    'anonymous': r'匿名|脱敏|anonymi[sz]ed|de.identif',
    'limited_role': r'(?:只|仅)(?:负责|实现|参与)|(?:only|solely|exclusively)\s+(?:implemented|responsible)|implement(?:ed|s|ing)\s+(?:only|solely|exclusively)|responsibilit(?:y|ies)\s+(?:was|were|is)\s+limited\s+to',
}

def qualifier_inventory(text):
    return {name:match.group() for name,pattern in QUALIFIERS.items()
            if (match:=re.search(pattern,text,re.I))}

def lost_qualifiers(supported_original,proposal):
    before=qualifier_inventory(supported_original);after=qualifier_inventory(proposal)
    return [{'category':name,'detail':detail} for name,detail in before.items() if name not in after]

def equivalent_qualifier_detail(detail,original,proposal):
    clean=detail.strip(' .。;；')
    return any(re.fullmatch(pattern,clean,re.I) and re.search(pattern,original,re.I) and re.search(pattern,proposal,re.I)
               for pattern in QUALIFIERS.values())

def causal_escalation(original,proposal,sources=()):
    """A measurement does not establish causing the measured improvement.

    Narrowly require review for new causal phrasing on observational work. An exact
    in-scope source statement can justify it; keyword overlap alone cannot.
    """
    observation=r'评测|测得|测量|\bevaluat(?:ed|ing|ion)\b|\bmeasur(?:ed|ing|ement)\b'
    causal=(r'\bcontribut(?:ed|ing)\s+to\b|\bachiev(?:ed|ing|es)\b|\b(?:drove|driving)\b'
            r'|\bdeliver(?:ed|ing|s)?\s+(?:a\s+)?(?:\d+(?:\.\d+)?\s*%\s+)?'
            r'(?:[A-Za-z-]+\s+){0,3}(?:reduction|improvement|increase|gain)\b'
            r'|推动|使得|带来')
    if (re.search(observation,original,re.I) and re.search(causal,proposal,re.I)
        and not re.search(causal,original,re.I) and not any(proposal.strip() in s.get('text','') for s in sources)):
        return ['建议将测量/评测改为促成成果，新增因果或个人贡献归属，须补证据。']
    return []

_METRIC=r'准确率|精确率|召回率|通过率|转化率|成功率|accuracy|precision|recall|pass rate|conversion rate|success rate'
_NUMBER=r'\d+(?:\.\d+)?'
_PATH=re.compile(r'(?P<metric>'+_METRIC+r')\s*(?:从|由|变化为|(?:rose|increased|improved|fell|decreased|improvement|increase|reduction)\s+from|from)?\s*'
    r'(?P<before>'+_NUMBER+r')\s*[%％]\s*(?:提升至|提高至|下降至|降至|变为|增至|升至|提升到|提高到|下降到|至|到|→|->|to)\s*'
    r'(?P<after>'+_NUMBER+r')\s*[%％]',re.I)
_POINT=re.compile(r'(?P<value>'+_NUMBER+r')\s*(?:个?百分点|percentage\s+points?|pp\b)',re.I)

def _one_path(text):
    paths=list(_PATH.finditer(text))
    if len(paths)!=1:return None
    match=paths[0]
    # Negated, estimated or multiple alternative paths are not arithmetic proof.
    prefix=text[max(0,match.start()-12):match.start()]
    if re.search(r'不是|并非|未达到|未从|not|instead',prefix,re.I):return None
    before,after=Decimal(match['before']),Decimal(match['after'])
    if not (0<=before<=100 and 0<=after<=100):return None
    return match['metric'].casefold(),before,after

def equivalent_point_detail(detail,original,proposal):
    """Only discharge a PURE redundant delta, never another missing qualifier.

    Both texts must explicitly retain the same single named metric transition.
    Decimal arithmetic, direction and units must match. Unknown forms abstain.
    """
    first,second=_one_path(original),_one_path(proposal)
    if not first or first!=second:return False
    points=list(_POINT.finditer(detail))
    if len(points)!=1:return False
    point=points[0];delta=first[2]-first[1]
    if re.search(r'[-−]\s*$',detail[:point.start()]):return False
    if abs(delta)!=Decimal(point['value']):return False
    rest=(detail[:point.start()]+detail[point.end():]).strip()
    sentence=re.fullmatch(r'(?:The\s+)?('+_METRIC+r')\s+(increase|improvement|decrease|reduction)\s+of\s+([A-Za-z][A-Za-z0-9_-]*)\s+(?:was|is)\s*[.。]?',rest,re.I)
    if sentence:
        metric,verb,entity=sentence.groups()
        if metric.casefold()!=first[0] or not all(re.search(r'\b'+re.escape(entity)+r'\b',text) for text in (original,proposal)):return False
        rest=verb
    # Deliberately tiny vocabulary: additional scope/person/time must not be excused.
    rest=re.sub(_METRIC,'',rest,flags=re.I)
    if delta>0:
        rest=re.sub(r'提高|提升|增加|上升|增幅|increase(?:d)?|improve(?:d|ment)?|rose|gain', '',rest,flags=re.I)
    elif delta<0:
        rest=re.sub(r'降低|下降|减少|降幅|decrease(?:d)?|reduc(?:ed|tion)|fell|drop', '',rest,flags=re.I)
    else:
        rest=re.sub(r'变化|change(?:d)?','',rest,flags=re.I)
    rest=re.sub(r'即|了|的|by|of|[\s，,。.;；:：()（）\-]','',rest,flags=re.I)
    return not rest and bool(_POINT.search(original))

def preservation_hints(original,proposal):
    return [{'detail':m.group(),'explanation':'Same named metric endpoints retained; exact percentage-point delta is redundant.'}
            for m in _POINT.finditer(original) if equivalent_point_detail(m.group(),original,proposal)]
