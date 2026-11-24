"""Bind a reviewed document to a named experience using its own provenance."""
import json
import re
import unicodedata
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
    return any(normalized(w) in corpus for w in chinese if w not in {'项目经历','机器学习','数据分析','项目名称','实习经历'})
