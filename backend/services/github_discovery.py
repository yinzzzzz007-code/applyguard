"""Public GitHub metadata discovery; reading material requires a separate grant."""
import re
from datetime import datetime, timedelta, timezone
import os,subprocess,threading,time,copy
from collections import OrderedDict
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from pathlib import Path

LOGIN = r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?'
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')

class PublicUnavailable(ValueError):
    pass


class PublicRateLimit(PublicUnavailable):
    def __init__(self, bucket, until, primary):
        self.bucket, self.until, self.primary = bucket, until, primary
        label = {'core':'常规接口', 'search':'搜索接口', 'all':'接口'}[bucket]
        when = datetime.fromtimestamp(until, timezone(timedelta(hours=8))).strftime('%m-%d %H:%M:%S')
        reason = f'匿名公开查询的{label}额度已用完' if primary else 'GitHub 暂时限制了请求频率'
        super().__init__(f'{reason}。请在北京时间 {when} 后重试。')


_PUBLIC_COOLDOWNS = OrderedDict()


def public_request(fetch, path):
    bucket = 'search' if path.startswith('search/') else 'core'
    now = time.time()
    with _CACHE_LOCK:
        for key in ((fetch, 'all'), (fetch, bucket)):
            entry = _PUBLIC_COOLDOWNS.get(key)
            if entry:
                until, primary = entry
                if until > now:
                    raise PublicRateLimit(key[1], until, primary)
                _PUBLIC_COOLDOWNS.pop(key)
    try:
        return fetch(path, False)
    except HTTPError as exc:
        if exc.code in {403, 429}:
            headers = {k.lower(): str(v) for k, v in (exc.headers or {}).items()}
            body = exc.read(4096).lower()
            retry = headers.get('retry-after', '')
            primary = headers.get('x-ratelimit-remaining') == '0' and not retry and b'secondary' not in body
            if not (primary or exc.code == 429 or retry or b'rate limit' in body):
                raise ValueError('GitHub 拒绝了这次公开查询（HTTP 403）。请核对公开资源的访问权限。') from None
            now = time.time()
            reset = headers.get('x-ratelimit-reset', '')
            wait_until = int(reset) if primary and reset.isdecimal() and 0 < int(reset) < 32_503_680_000 else 0
            until = max(now + (int(retry) if retry.isdecimal() and len(retry) < 7 else 0), wait_until)
            if until <= now: until = now + 60
            scope = bucket if primary else 'all'
            with _CACHE_LOCK:
                _PUBLIC_COOLDOWNS[(fetch,scope)] = (until, primary)
                while len(_PUBLIC_COOLDOWNS)>64: _PUBLIC_COOLDOWNS.popitem(last=False)
            raise PublicRateLimit(scope, until, primary) from None
        if exc.code == 404:
            raise ValueError('未找到公开账号或仓库，请核对用户名。') from None
        if exc.code == 409:
            raise ValueError('该仓库尚无提交，请选择其他仓库。') from None
        if exc.code >= 500:
            raise PublicUnavailable(f'GitHub 服务暂时不可用（HTTP {exc.code}），请稍后重试。') from None
        raise ValueError(f'GitHub 查询失败（HTTP {exc.code}）。') from None
    except (URLError, TimeoutError, OSError):
        raise PublicUnavailable('无法连接 GitHub，请检查网络后重试。') from None

def repository(row):
    name = row.get('full_name', '')
    if row.get('private') is not False or not REPO.fullmatch(name):
        return None
    return {'repo': name, 'url': 'https://github.com/' + name,
            'description': str(row.get('description') or '')[:500],
            'branch': str(row.get('default_branch') or ''),
            'updated_at': row.get('pushed_at'), 'archived': bool(row.get('archived'))}

def _discover(body, fetch):
    query = str(body.get('query', '')).strip()
    kind = body.get('kind', 'auto')
    page = body.get('page', 1)
    if type(page) is not int or not 1 <= page <= 34:
        raise ValueError('查询页码须为 1–34。')
    if not 1 <= len(query) <= 120 or re.search(r'github_pat_|gh[pousr]_|sk-[\w-]{20,}', query):
        raise ValueError('请输入用户名、公开邮箱或关键词；不要填写密钥。')
    if kind not in {'auto', 'username', 'email', 'keyword'}:
        raise ValueError('请选择公开查询方式。')
    normalized = re.sub(r'^(?:https://github\.com/|@)', '', query).rstrip('/')
    normalized = re.sub(r'(?:的)?(?:公开|public)?仓库$', '', normalized, flags=re.I).strip()
    if kind == 'auto':
        kind = 'email' if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', query) else 'username' if re.fullmatch(LOGIN, normalized) else 'keyword'
    if kind == 'email':
        if not re.fullmatch(r'[^\s@"<>]+@[^\s@"<>]+\.[^\s@"<>]+', query):
            raise ValueError('请输入完整的公开邮箱地址。')
        data = public_request(fetch, 'search/users?' + urlencode({'q': query + ' in:email', 'per_page': 30, 'page': page}))
        accounts = [{'login': row['login'], 'url': 'https://github.com/' + row['login']}
                    for row in data.get('items', []) if re.fullmatch(LOGIN, row.get('login', ''))]
        return {'accounts': accounts, 'items': [], 'page': page,
                'has_more': page*30 < min(data.get('total_count', 0), 1000),
                'notice': '邮箱仅能匹配 GitHub 可搜索的公开资料。请先核对候选账号，再查看其公开仓库；未找到不代表账号不存在。'}
    listing = 'default'
    if kind == 'username':
        if not re.fullmatch(LOGIN, normalized):
            raise ValueError('请输入有效的 GitHub 用户名。')
        by_owner_search = page > 1 and body.get('listing') == 'owner_search'
        if not by_owner_search:
            try:
                rows = public_request(fetch, 'users/' + normalized + '/repos?' + urlencode({'type':'owner','sort':'pushed','per_page':30,'page':page}))
                more = len(rows) == 30
            except PublicRateLimit as exc:
                if not exc.primary or exc.bucket != 'core' or page != 1: raise
                by_owner_search = True
        notice = f'{normalized} 的公开仓库，请选择本次需要的仓库。'
        if by_owner_search:
            data = public_request(fetch,'search/repositories?' + urlencode({
                'q': f'user:{normalized} is:public fork:true', 'sort':'updated','per_page':30,'page':page}))
            rows = [row for row in data.get('items',[]) if str(row.get('full_name','')).partition('/')[0].casefold() == normalized.casefold()]
            more = page*30 < min(data.get('total_count',0),1000)
            listing = 'owner_search'
            notice += ' 当前使用 GitHub 公开搜索索引，结果按更新时间排列。'
    elif REPO.fullmatch(normalized):
        rows = [public_request(fetch, 'repos/' + normalized)]
        more, notice = False, '已找到公开仓库，请核对后选择。'
    else:
        if any(c in query for c in ':"\\'):
            raise ValueError('关键词请填写项目名称或技术词，不需要 GitHub 查询语法。')
        data = public_request(fetch, 'search/repositories?' + urlencode({'q': query + ' is:public', 'sort': 'updated', 'per_page': 30, 'page': page}))
        rows = data.get('items', [])
        more = page*30 < min(data.get('total_count', 0), 1000)
        notice = '按关键词匹配公开仓库；匹配结果不代表本人贡献。'
        if data.get('incomplete_results'):
            notice += ' GitHub 返回了部分结果，可缩小关键词重试。'
    return {'accounts': [], 'items': [item for row in rows if (item := repository(row))],
            'page': page, 'has_more': more and page < 34, 'notice': notice, 'listing': listing}

def pin(body, fetch):
    name = str(body.get('repo', '')).strip()
    if not REPO.fullmatch(name):
        raise ValueError('请选择有效的 owner/repo 仓库。')
    try:
        row = public_request(fetch, 'repos/' + name)
        item = repository(row)
        if not item or item['repo'].lower() != name.lower():
            raise ValueError('仅可选择公开仓库；私有仓库须另行授权。')
        if not item['branch']:
            raise ValueError('仓库尚无默认分支，请选择其他仓库。')
        data = public_request(fetch, f"repos/{name}/git/ref/heads/{quote(item['branch'], safe='')}")
    except PublicUnavailable as exc:
        if isinstance(exc,PublicRateLimit) and not exc.primary: raise
        try: return public_git_head(name)
        except ValueError as fallback:
            raise ValueError(f'{exc} {fallback}') from None
    sha = data.get('object', {}).get('sha', '')
    if data.get('object', {}).get('type') != 'commit' or not re.fullmatch(r'[a-fA-F0-9]{40}', sha):
        raise ValueError('未能固定仓库当前版本，请重试。')
    return {**item, 'sha': sha.lower(), 'spec': item['repo'] + '@' + sha.lower()}


_DISCOVERY_CACHE=OrderedDict()
_CACHE_LOCK=threading.RLock()

def discover(body,fetch):
    email=str(body.get('email','')).strip()
    if email:
        query=str(body.get('query','')).strip()
        if not query:return discover({**body,'query':email,'kind':'email','email':''},fetch)
        if not re.fullmatch(LOGIN,query):raise ValueError('同时核对两项线索时，请填写 GitHub 用户名与公开邮箱。')
        account=public_request(fetch,'users/'+query)
        public=str(account.get('email') or '').casefold()
        if public and public!=email.casefold():raise ValueError('该账号的公开邮箱与填写值不符，请核对账号。')
        result=discover({**body,'email':'','kind':'username'},fetch)
        return {**result,'notice':result['notice']+(' 公开邮箱一致。' if public else ' 该账号未展示公开邮箱，请自行核对身份。')}
    key=(fetch,str(body.get('kind','auto')),str(body.get('query','')).strip().casefold(),repr(body.get('page',1)),str(body.get('listing','default')))
    with _CACHE_LOCK:cached=_DISCOVERY_CACHE.get(key)
    if cached and time.time()-cached[0]<300:
        return {**copy.deepcopy(cached[1]),'cached':True}
    try:result=_discover(body,fetch)
    except PublicUnavailable as exc:
        if cached and time.time()-cached[0]<86400:
            return {**copy.deepcopy(cached[1]),'cached':True,'notice':f"{exc} 当前显示此前缓存的公开结果。"}
        raise
    result['queried_at']=time.time()
    with _CACHE_LOCK:
        _DISCOVERY_CACHE[key]=(time.time(),copy.deepcopy(result))
        while len(_DISCOVERY_CACHE)>128:_DISCOVERY_CACHE.popitem(last=False)
    return result

def public_git_head(name):
    allowed={'path','systemroot','comspec','temp','tmp','userprofile','home','localappdata','appdata','http_proxy','https_proxy','all_proxy','no_proxy','pathext'}
    environment={k:v for k,v in os.environ.items() if k.casefold() in allowed}
    environment.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0',GIT_ASKPASS='')
    try:
        completed=subprocess.run(['git','-c','credential.helper=','-c','core.askpass=',
            '-c','http.extraHeader=','-c','http.followRedirects=false','ls-remote','--symref',
            'https://github.com/'+name+'.git','HEAD'],capture_output=True,text=True,timeout=20,env=environment,
            cwd=Path(os.path.abspath(os.sep)),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError('GitHub API 不可用，公开版本查询也未完成，请稍后重试。') from None
    sha_match=re.search(r'^([a-fA-F0-9]{40})\s+HEAD$',completed.stdout,re.M)
    branch_match=re.search(r'^ref: refs/heads/(.+)\s+HEAD$',completed.stdout,re.M)
    if completed.returncode or not sha_match:
        raise ValueError('未能匿名确认公开仓库版本；私有仓库请使用单独授权。')
    sha=sha_match[1].lower()
    return {'repo':name,'url':'https://github.com/'+name,'sha':sha,'spec':name+'@'+sha,
            'branch':branch_match[1] if branch_match else '', 'version_source':'anonymous_git_refs'}
