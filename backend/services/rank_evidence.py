"""Explicit competition placements anchored on each side of a claim."""
import re
from backend.services.evidence_scope import project_match

RANK = re.compile(r'(?<![\d/])(\d{1,3}(?:,\d{3})*|\d+)\s*(?:/|(?:st|nd|rd|th)\s+of\s+)\s*(\d{1,3}(?:,\d{3})*|\d+)(?![\d/])')
RANK_CONTEXT = re.compile(r'placed|rank|排名|名次|金牌|银牌|铜牌|gold|silver|bronze|challenge|kaggle|竞赛',re.I)


def placements(text):
    for clause in re.finditer(r'[^。；;\n]+',text):
        if not RANK_CONTEXT.search(clause.group()):
            continue
        for match in RANK.finditer(clause.group()):
            nearby = clause.group()[max(0, match.start()-64):match.start()]
            if '/' in match.group() and not re.search(r'(?:排名|名次|rank(?:ed|ing)?|place(?:d)?|银牌|金牌|铜牌|silver|gold|bronze)\s*(?:medal(?:ist)?)?[\s:：·(（，,为第#-]*$',nearby,re.I):
                continue
            nums=tuple(int(n.replace(',','')) for n in match.groups())
            if 0 < nums[0] <= nums[1]:
                yield clause.start()+match.start(), match.group(), nums, clause.group()


def rank_conflict(claim, project, sources):
    draft=list(placements(claim))
    if len({p[2] for p in draft})!=1:
        return None
    start,excerpt,numbers,_=draft[0]
    originals=[(source,quote,rank) for source in sources for _,_,rank,quote in placements(source['text'])
               if project_match(project,'',quote,{}) or (source.get('title','').lower().endswith(('.png','.pdf','.jpg')) and project_match(project,source['title'],'',{}))]
    values={rank for _,_,rank in originals}
    if len(values)!=1 or numbers in values:
        return None
    source,quote,_=originals[0]
    return start,excerpt,source,quote
