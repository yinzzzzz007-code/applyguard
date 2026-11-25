"""Bind a reviewed document to a named experience using its own provenance."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import PurePosixPath


def normalized(value):
    return re.sub(r'[^\w\u3400-\u9fff]+', '', unicodedata.normalize('NFKC', value).casefold()).replace('_', '')


def source_identity(filename, text):
    origin = {}
    lines = text.splitlines()
    if lines and lines[0].startswith(('# Agent候选证据','# GitHub 来源')):
        for index, line in enumerate(lines[1:], 1):
            if line.startswith('{'):
                try:
                    metadata = json.loads(line)
                    origin = {key: metadata[key] for key in ('repo', 'commit_sha', 'path', 'version') if isinstance(metadata.get(key), str)}
                    text = '\n'.join(lines[index+1:])
                except (ValueError, TypeError):
                    text = ''
                break
    return origin, text


def matches_item(title, filename, text, *, organization='', description='', kind='project'):
    origin,body=source_identity(filename,text)
    if not body.strip() or not re.search(r'[A-Za-z\u3400-\u9fff]',title):
        return False
    if kind == 'award':
        event = re.split(r'(?:特等|[一二三]等)奖|[（(]', title, maxsplit=1)[0].strip()
        if len(normalized(event)) >= 4 and normalized(event) in normalized(body):
            return True
    if project_match(title,filename,body,origin):return True
    if kind in {'project','experience','internship'} and not origin and not body.lstrip().startswith('#'):
        if len(description.strip()) >= 20 and description.strip() in body:
            return True
    if kind=='internship':
        if organization and normalized(organization) in normalized(body):return True
        # Some work records directly quote the whole named contribution, without a project heading.
        return not body.lstrip().startswith('#') and len(description.strip())>=20 and description.strip() in body
    return False


def project_match(title, filename, body, origin):
    stem = re.split(r'\s*(?:——|—|\||：|:)\s*', title, maxsplit=1)[0].strip()
    headings = [line.lstrip('# ').strip() for line in body.strip().splitlines()[:3] if line.startswith('# ')]
    if headings:
        identifiers = re.findall(r'^\s*(?:项目名称|项目名|project name)\s*[：:]\s*(.+)$',body,re.I|re.M)
        body = '\n'.join(headings + identifiers)
        filename = ''
    corpus = normalized(' '.join((filename, origin.get('repo',''), origin.get('path',''), body)))
    if len(normalized(stem)) >= 3 and normalized(stem) in corpus:
        return True
    generic = {'nvidia','challenge','model','reasoning','research','project','silver','kaggle','award','system','development','intern','internship','software','engineer','engineering','assistant','platform','learning','data','science','agent','team','github','information','technology'}
    # A specific project name (including a competition name) may precede a subtitle or medal.
    words = [w for w in re.findall(r'[A-Za-z][A-Za-z0-9-]{3,}', stem) if w.casefold() not in generic]
    if words and re.search(r'(?<![A-Za-z0-9])'+re.escape(words[0])+r'(?![A-Za-z0-9])', filename+' '+origin.get('repo','')+' '+body, re.I):
        return True
    chinese = re.findall(r'[\u3400-\u9fff]{4,}', stem)
    if any(normalized(w) in corpus for w in chinese if w not in {'项目经历','机器学习','数据分析','项目名称','实习经历'}):
        return True
    # OCR may attach a generic prefix or suffix to the actual project heading.
    # Only compare long, specific Chinese fragments with the source identity;
    # shared technologies in the document body are not proof of identity.
    generic_fragments = {'大语言模型训练与对齐', '大模型的训练与性能优化', '项目的设计与实现方案'}
    for word in chinese:
        for start in range(max(0, len(word) - 9)):
            fragment = word[start:start + 10]
            if len(fragment) == 10 and fragment not in generic_fragments and fragment in corpus:
                return True
    return False


def suggest_project_identity(title, filename, text):
    """A fuzzy filename candidate, never an automatic ownership decision."""
    origin, _ = source_identity(filename, text)
    title = re.sub(r'已完成|进行中|已结束', '', title.strip())
    wanted = normalized(title)
    if len(wanted) < 7:
        return False
    identity = origin.get('path') or filename
    parts = re.split(r'[/\\]', identity)
    for part in parts:
        actual = normalized(re.sub(r'^\d+[_\-. ]*', '', part))
        if len(actual) < 7 or actual in {'readmemd', 'readmetxt'}:
            continue
        blocks = [block for block in SequenceMatcher(None, wanted, actual, autojunk=False).get_matching_blocks() if block.size >= 3]
        if blocks:
            coverage = sum(block.size for block in blocks) / len(wanted)
            longest = max(block.size for block in blocks)
            if (longest >= 4 and coverage >= .8) or (longest >= 6 and coverage >= .6):
                return True
    return False
