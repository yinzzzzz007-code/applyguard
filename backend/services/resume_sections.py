"""Conservative local parsing of bilingual, sectioned academic/campus CVs.

Headings are whole lines; dates and roles are copied only when explicitly present.
These are imported drafts, not verified evidence or inferred qualifications.
"""
from __future__ import annotations
import re

_HEADINGS = {
    'education': (r'教育(?:背景|经历)', r'education(?:al background)?'),
    'projects': (r'(?:重点|主要|精选)?(?:科研|研究)(?:经历|项目)|当前研究|在研项目|(?:工程|个人|重点|精选)?项目(?:经历|经验)?',
                 r'(?:selected |current |ongoing )?research(?: experience| projects)?|(?:engineering |selected |personal )?projects?(?: experience)?'),
    'internships': (r'实习(?:经历|经验)?|工作(?:经历|经验)?|职业经历', r'(?:work|professional|internship) experience|internships?|employment'),
    'awards': (r'(?:获奖|荣誉|奖项|竞赛|比赛|学科竞赛)(?:情况|经历|成果|获奖)?|荣誉奖项', r'(?:awards?|honou?rs?|competitions?)(?:\s*(?:&|and)\s*(?:awards?|honou?rs?))?'),
    'mixed': (r'其他经历与荣誉', r'other experience\s*(?:&|and)\s*honou?rs?'),
    'skills': (r'专业技能|技术技能|技能特长|技能', r'(?:technical |professional )?skills'),
    'interests': (r'研究兴趣|科研兴趣|研究方向', r'research interests?'),
    'summary': (r'个人简介|自我评价|个人总结', r'profile|summary|about me'),
}
_ROLE = re.compile(r'独立第一作者|独立一作|共同第一作者|共同一作|第一作者|项目负责人|技术负责人|主要贡献者|核心成员|团队成员')
_AWARD = re.compile(r'一等奖|二等奖|三等奖|金奖|银奖|铜奖|银牌|金牌|铜牌|奖学金|优胜|冠军|亚军|季军|\b(?:silver|gold|bronze|honorable\s+mention|honourable\s+mention|scholarship)\b', re.I)
_SCHOOL = re.compile(r'[\u4e00-\u9fff]{2,20}(?:大学|学院)')
_RANGE = re.compile(r'(?<![\d./-])(20\d{2})(?:[./年-](\d{1,2})(?!\d)月?)?\s*(?:[–—~至]|\s-\s|-(?=20))\s*(20\d{2}|至今|现在|present)(?:[./年-](\d{1,2})(?!\d)月?)?(?!\d|[./年-]\d)',re.I)

def heading_kind(line):
    line=line.strip().strip(':：').strip()
    for kind,(cn,en) in _HEADINGS.items():
        if re.fullmatch(rf'(?:{cn})(?:\s+(?:{en}))?|(?:{en})',line,re.I):return kind
    return None

def sections(text):
    blocks=[];kind=None;lines=[]
    for raw in text.splitlines():
        line=raw.strip()
        if not line:continue
        found=heading_kind(line)
        if found:
            if kind:blocks.append((kind,lines))
            kind=found;lines=[]
        elif kind:lines.append(line)
    if kind:blocks.append((kind,lines))
    return blocks

def header_name(text):
    for line in [s.strip() for s in text.splitlines() if s.strip()][:3]:
        if heading_kind(line):break
        if re.search(r'简历|姓名|学院|大学|专业|背景|个人资料|基本信息|个人信息',line):continue
        found=re.fullmatch(r'([\u4e00-\u9fff]{2,4})(?:\s+[A-Za-z][A-Za-z .\x27-]{1,55})?',line)
        if found:return found[1]
    return ''

def dates(text):
    found=_RANGE.search(text)
    if not found:return '',''
    if any(month and not 1<=int(month)<=12 for month in (found[2],found[4])):return '',''
    if found[3].isdigit():
        if int(found[3])<int(found[1]):return '',''
        if found[3]==found[1] and found[2] and found[4] and int(found[4])<int(found[2]):return '',''
    start=found[1]+(f'-{int(found[2]):02d}' if found[2] else '')
    end=found[3]+(f'-{int(found[4]):02d}' if found[4] else '')
    return start,end

def education(lines):
    groups=[];current=[]
    for line in lines:
        if _SCHOOL.match(line) and current:groups.append(current);current=[]
        current.append(line)
    if current:groups.append(current)
    rows=[]
    for group in groups:
        text='\n'.join(group);school=_SCHOOL.search(group[0])
        if not school:continue
        degree=re.search(r'博士|硕士|本科|专科|高中',text)
        major=re.search(r'(?:所学专业|专业)(?!排名|方向|课程)\s*[:：]\s*([^\n，,；;]{2,40})',text)
        if not major:major=re.search(r'^\s*([\u4e00-\u9fff与及 /A-Za-z-]{2,40}?)(?:本科|硕士|博士|专科)',text,re.M)
        rank=re.search(r'(?:专业排名|排名|Rank)\s*[:：]?\s*(\d+\s*/\s*\d+(?:\s*[（(]\s*Top\s*[\d.]+%\s*[）)])?)',text,re.I)
        start,end=dates(text)
        rows.append({'school':school[0],'degree':degree[0] if degree else '',
            'major':major[1].strip(' ·') if major else '', 'rank':rank[1] if rank else '',
            'fullTime':'','start':start,'end':end})
    return rows

def _title_line(line):
    if len(line)>180 or re.match(r'研究[:：]|贡献[:：]|职责[:：]|负责[:：]|项目负责人[。.]',line):return False
    if re.search(r'[。；;，]|(?:^|\s)(?:through|and|with|using)\s',line):return False
    if re.search(r'\s[—–]+\s|\s-\s',line):return True
    # Capitalized English titles; continuation prose with punctuation stays in the body.
    return bool(re.match(r'^[A-Z][A-Za-z0-9-]*(?:\s+[A-Z0-9][A-Za-z0-9/&-]*){1,}',line)
        and not re.search(r'[:：。、]',line))

def project_entries(lines,kind):
    groups=[];current=[]
    for line in lines:
        if current and len(current)==1 and current[0].endswith('-'):
            current[0]+=line;continue
        if _title_line(line) and current:groups.append(current);current=[]
        current.append(line)
    if current:groups.append(current)
    rows=[]
    for group in groups:
        header=group[0];role=_ROLE.search(header);start,end=dates(header)
        # Remove only trailing status metadata from the displayed title, retaining it in description.
        title=re.split(r'\s+(?=[A-Z][A-Z0-9/-]{1,20}\s+20\d{2}\s+(?i:Submitted|Accepted)\b|Kaggle\s+(?:Silver|Gold|Bronze)\b|(?:独立一作|共同第一作者|项目负责人|主要贡献者|核心成员)\b)',header)[0]
        rows.append({'organization':header[:100] if kind=='internships' else '',
            'title':title,'role':role[0] if role else '', 'start':start,'end':end,
            'description':'\n'.join(group)})
    return rows

def award_entry(text):
    match=re.search(r'(?<!\d)(20\d{2})[./年-](\d{1,2})(?!\d)月?',text)
    if match and not 1<=int(match[2])<=12:match=None
    return {'name':text,'issuer':'','date':f'{match[1]}-{int(match[2]):02d}' if match else '', 'description':text}

def enrich_sections(result,text):
    if not result['basic']['name']:result['basic']['name']=header_name(text)
    blocks=sections(text)
    if not blocks:return result
    project_rows=[];intern_rows=[];awards=[];edu=[];skills=[];summary=[]
    for line in text.splitlines():
        if heading_kind(line):break
        if re.search(r'\bGPA\b|\bCET[-–]?\d\b|\bIELTS\b|\bTOEFL\b|\bRank\b|绩点|四六级|雅思|托福',line,re.I):
            summary.append(line.strip())
    for kind,lines in blocks:
        if kind=='education':edu.extend(education(lines))
        elif kind in {'projects','internships'}:
            rows=project_entries(lines,kind)
            (project_rows if kind=='projects' else intern_rows).extend(rows)
            for row in rows:
                header=row['description'].split('\n')[0]
                if _AWARD.search(header):awards.append(award_entry(header))
        elif kind in {'awards','mixed'}:
            joined=' '.join(lines)
            pieces=re.split(r'\s+[·•]\s+|[；;]',joined) if kind=='mixed' else lines
            for piece in pieces:
                piece=piece.strip(' ·•-')
                if not piece:continue
                if _AWARD.search(piece) or (kind=='awards' and re.search(r'竞赛|比赛|大赛|挑战杯|数学建模',piece)):
                    awards.append(award_entry(piece))
                elif kind=='mixed' and (_ROLE.search(piece) or re.search(r'项目|大创',piece)):
                    project_rows.extend(project_entries([piece],'projects'))
        elif kind=='skills':skills.append(' '.join(lines))
        elif kind in {'interests','summary'}:summary.append(' '.join(lines))
    kinds={kind for kind,_ in blocks}
    if 'education' in kinds:result['education']=edu
    if kinds & {'projects','mixed'}:result['projects']=project_rows
    if 'internships' in kinds:result['internships']=intern_rows
    if kinds & {'awards','mixed','projects'}:
        unique={re.sub(r'\s+','',a['name']).casefold():a for a in awards}
        result['awards']=list(unique.values())
        result['extras']['awards']='；'.join(a['name'] for a in result['awards'])
    if skills:result['extras']['skills']='\n'.join(skills)
    if summary:result['extras']['summary']='\n'.join(summary)
    return result
