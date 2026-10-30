# Gitvextor的原型：用户授权的材料检索与证据回传。
"""In-memory, expiring capability grants. No agent tool can expand scope or approve evidence."""
from __future__ import annotations
import base64, hashlib, json, os, re, secrets, threading, time
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler

LOCK = threading.RLock()
GRANTS: dict[str, dict] = {}
EXTENSIONS = {'.md', '.txt', '.py', '.ts', '.tsx', '.js', '.java', '.sql', '.pdf', '.docx'}
SKIP = {'node_modules', 'venv', '__pycache__', 'dist', 'build'}
MAX_BYTES = 1_000_000

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('GitHub redirect refused')

def gh(path, private=False):
    headers = {'Accept':'application/vnd.github+json','User-Agent':'ApplyGuard-agent-prototype'}
    if private:
        token = os.getenv('APPLYGUARD_GITHUB_TOKEN', '')
        if not token: raise ValueError('私有仓库尚未配置独立 GitHub 授权')
        headers['Authorization'] = 'Bearer '+token
    with build_opener(NoRedirect).open(Request('https://api.github.com/'+path, headers=headers), timeout=20) as r:
        raw = r.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('GitHub response too large')
        return json.loads(raw)

def clean_path(name):
    p = Path(name.replace('\\','/'))
    if p.is_absolute() or p.anchor or name.startswith(('/', '\\')) or any(x in {'..',''} or x.startswith('.') or x in SKIP for x in p.parts):
        raise ValueError('路径超出授权范围')
    if ':' in name or p.suffix.lower() not in EXTENSIONS: raise ValueError('不支持此文件类型')
    return p

def create(body):
    mode = body.get('mode')
    if mode not in {'local','github','auto'}: raise ValueError('请选择搜索范围')
    if body.get('disclosure') not in {'cloud_allowed','isolated_local'}:
        raise ValueError('读取前必须确定材料外发授权')
    if body.get('purpose') not in {'contribution','background'}: raise ValueError('请选择查找目的')
    task = str(body.get('task','')).strip()
    if not 4<=len(task)<=2000: raise ValueError('请输入 4–2000 字的任务')
    roots = []
    for value in body.get('roots',[])[:5]:
        p=Path(value).resolve(strict=True)
        if not p.is_dir() or p == Path(p.anchor): raise ValueError('请选择具体文件夹，不允许整盘授权')
        roots.append(str(p))
    repos=[]
    for spec in body.get('repos',[])[:5]:
        # Exact repository and immutable revision; account-wide expansion is not implicit.
        repo,sep,sha=spec.partition('@')
        if not sep or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) or not re.fullmatch(r'[0-9a-fA-F]{40}',sha):
            raise ValueError('GitHub 范围请填写 owner/repo@完整40位提交SHA')
        repos.append({'repo':repo,'sha':sha.lower(),'private':body.get('private') is True})
    if (mode=='local' and not roots) or (mode=='github' and not repos) or (mode=='auto' and not (roots or repos)):
        raise ValueError('至少指定一个允许访问的来源')
    if (mode=='local' and repos) or (mode=='github' and roots): raise ValueError('来源与所选模式不符')
    with LOCK:
        for key in list(GRANTS):
            if GRANTS[key]['expires']<time.time(): del GRANTS[key]
        if len(GRANTS)>=32: raise ValueError('请先撤销旧连接')
        token=secrets.token_urlsafe(32); ui=secrets.token_urlsafe(32)
        g={'id':secrets.token_hex(12),'token':token,'ui_token':ui,'expires':time.time()+1800,
           'task':task,'mode':mode,'purpose':body['purpose'],'disclosure':body['disclosure'],
           'roots':roots,'repos':repos,'connected':False,'cards':{},'revoked':False}
        GRANTS[g['id']]=g
    return {'id':g['id'],'token':token,'ui_token':ui,'expires':g['expires']}

def grant(identifier, token, ui=False):
    g=GRANTS.get(identifier)
    expected=g.get('ui_token' if ui else 'token','') if g else ''
    if not expected or not secrets.compare_digest(expected,str(token)) or g['revoked'] or g['expires']<time.time():
        raise ValueError('连接已失效或未授权，请重新配对')
    return g

def extract(path, raw):
    suffix=Path(path).suffix.lower()
    if suffix=='.pdf':
        import io
        from pypdf import PdfReader
        pdf=PdfReader(io.BytesIO(raw))
        if len(pdf.pages)>40: raise ValueError('PDF超过40页')
        return [(i+1,1,(p.extract_text() or '')) for i,p in enumerate(pdf.pages)]
    if suffix=='.docx':
        import io,zipfile
        from xml.etree import ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            info=z.getinfo('word/document.xml')
            if info.file_size>4_000_000: raise ValueError('DOCX解压内容过大')
            node=ET.fromstring(z.read(info))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        return [(None,i+1,''.join(p.itertext())) for i,p in enumerate(node.findall('.//w:p',ns))]
    return [(None,i+1,t) for i,t in enumerate(raw.decode('utf-8').splitlines())]

def local_files(g):
    visited=0
    for root in g['roots']:
        base=Path(root)
        for directory,dirs,files in os.walk(base,followlinks=False):
            visited+=1
            if visited>500:return
            dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in SKIP and not Path(directory,d).is_symlink() and not Path(directory,d).is_junction())
            for name in sorted(files):
                visited+=1
                if visited>500: return
                p=Path(directory,name)
                try:
                    rel=str(p.relative_to(base));clean_path(rel)
                    resolved=p.resolve(strict=True)
                    if not resolved.is_relative_to(base) or p.is_symlink() or p.stat().st_size>MAX_BYTES: continue
                    with p.open('rb') as f: raw=f.read(MAX_BYTES+1)
                    if len(raw)>MAX_BYTES: continue
                    yield {'kind':'local','root':root,'path':rel,'version':hashlib.sha256(raw).hexdigest()},raw
                except (ValueError,OSError): continue

def github_files(g):
    for spec in g['repos']:
        tree=gh(f"repos/{spec['repo']}/git/trees/{spec['sha']}?recursive=1",spec['private'])
        if tree.get('truncated'): raise ValueError('仓库目录过大，请缩小范围后重试')
        count=0
        for row in tree.get('tree',[]):
            if row.get('type')!='blob' or row.get('mode')=='120000' or row.get('size',MAX_BYTES+1)>MAX_BYTES: continue
            try: clean_path(row['path'])
            except ValueError: continue
            count+=1
            if count>60: return
            blob=gh(f"repos/{spec['repo']}/git/blobs/{row['sha']}",spec['private'])
            raw=base64.b64decode(blob['content'])
            if len(raw)>MAX_BYTES: continue
            yield {'kind':'github','repo':spec['repo'],'path':row['path'],'commit_sha':spec['sha'],
                   'version':hashlib.sha256(raw).hexdigest()},raw

def search(g, query):
    if not isinstance(query,str) or not 1<=len(query)<=300: raise ValueError('查询长度须为1–300')
    # Lexical retrieval baseline. Harness may issue multiple queries; no semantic accuracy claim.
    terms=re.findall(r'[a-zA-Z0-9_]+|[\u4e00-\u9fff]{2,}',query.lower())
    terms += [t[i:i+2] for t in terms[:] if re.search(r'[\u4e00-\u9fff]',t) for i in range(len(t)-1)]
    hits=[]; errors=[]
    for stream in (local_files(g),github_files(g)):
        try:
            for source,raw in stream:
                grant(g['id'],g['token'])  # revocation checked before every file disclosure
                if re.search(rb'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----',raw):
                    errors.append({'path':source['path'],'error':'POSSIBLE_SECRET_SKIPPED'});continue
                try: spans=extract(source['path'],raw)
                except Exception: errors.append({'path':source['path'],'error':'EXTRACTION_FAILED'});continue
                for page,line,text in spans:
                    if not text.strip(): continue
                    score=sum(t in text.lower() for t in set(terms))
                    if not score: continue
                    quote=text[:4000]
                    cid=hashlib.sha256(json.dumps([source,page,line,quote],sort_keys=True).encode()).hexdigest()[:24]
                    hits.append({'id':cid,'source':source,'page':page,'line':line,'quote':quote,'score':score,
                                 'state':'CANDIDATE','purpose':g['purpose'],'interpretation':'',
                                 'missing':['本人归属与陈述支持度尚未核验'],'numeric_confirmation_required':bool(re.search(r'\d',quote))})
        except ValueError: raise
        except Exception: errors.append({'error':'SOURCE_UNAVAILABLE'})
    with LOCK:
        grant(g['id'],g['token'])
        hits=sorted(hits,key=lambda c:(-c['score'],c['id']))[:20]
        for c in hits:
            if c['id'] not in g['cards']:g['cards'][c['id']]=c
        return {'cards':[g['cards'][c['id']] for c in hits],'errors':errors,'bounded':True,
                'limits':{'local_entries':500,'github_files':60,'results':20}}

def agent_call(body, token):
    g=grant(body.get('id'),token)
    action=body.get('action');args=body.get('arguments') or {}
    if action=='task':
        g['connected']=True
        return {k:g[k] for k in ('id','task','mode','purpose','disclosure','expires')}
    if action=='search':return search(g,args.get('query'))
    if action=='submit':
        c=g['cards'].get(args.get('card_id'))
        if not c or args.get('quote')!=c['quote'] or args.get('version')!=c['source']['version']:
            raise ValueError('引用内容或版本不匹配，拒绝回传')
        if c['state']=='IMPORTED': raise ValueError('已导入证据不可由Agent改写')
        c.update(interpretation=str(args.get('interpretation',''))[:2000],experience=str(args.get('experience',''))[:200],
                 missing=[str(x)[:200] for x in args.get('missing',[])[:12]],state='NEEDS_REVIEW')
        return c
    raise ValueError('不允许的Agent操作')

def ui_call(body):
    if body.get('action')=='create':return create(body)
    if body.get('action')=='revoke':
        # A valid UI capability may revoke even after expiry; repeated revoke is
        # harmless. Agent capabilities can never revoke or mint UI authorization.
        with LOCK:
            g=GRANTS.get(body.get('id'))
            if g and not secrets.compare_digest(g['ui_token'],str(body.get('ui_token',''))):
                raise ValueError('未授权的界面操作')
            if g:g['revoked']=True
            return {'revoked':True}
    g=grant(body.get('id'),body.get('ui_token'),ui=True)
    if body.get('action')=='status':return {'connected':g['connected'],'cards':list(g['cards'].values()),'expires':g['expires']}
    if body.get('action')=='accept':
        c=g['cards'].get(body.get('card_id'))
        if not c or c['state']!='NEEDS_REVIEW': raise ValueError('请先等待Agent回传候选解释')
        if c['purpose']=='background': raise ValueError('技术背景不能作为个人经历导入')
        if body.get('confirm_source') is not True: raise ValueError('请核对原文与本人归属')
        if c['numeric_confirmation_required'] and body.get('confirm_numbers') is not True: raise ValueError('量化内容必须单独确认')
        if c['source']['kind']=='local':
            p=(Path(c['source']['root'])/clean_path(c['source']['path'])).resolve(strict=True)
            if not p.is_relative_to(Path(c['source']['root'])) or hashlib.sha256(p.read_bytes()).hexdigest()!=c['source']['version']:
                raise ValueError('原文已变化，请重新查找')
        from backend.services.evidence_workspace import import_files
        provenance={**c['source'],'page':c['page'],'line_or_paragraph':c['line'],'experience':c.get('experience',''),
                    'review_scope':'用户仅确认来源；陈述支持度仍待核验'}
        content='# Agent候选证据（待陈述核验）\n\n'+json.dumps(provenance,ensure_ascii=False)+'\n\n'+c['quote']
        result=import_files(str(body.get('workspace_id','')),[{'relative_path':'agent-'+c['id']+'.md',
            'content_base64':base64.b64encode(content.encode()).decode()}])
        if any(row.get('state')=='FAILED' or row.get('parse_error') for row in result.get('results',[])):
            raise ValueError('证据导入失败，请检查工作区')
        c['state']='IMPORTED'
        return {'import':result,'state':'NEEDS_REVIEW','note':'人工确认来源不等于陈述已核验'}
    raise ValueError('未知界面操作')
