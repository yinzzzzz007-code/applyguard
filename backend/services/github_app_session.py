"""Explicit short-lived GitHub App device authorizations, scoped to this server."""
import json
import os
import re
import secrets
import threading
import time
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

SESSIONS = {}
LOCK = threading.RLock()


def oauth(path, data):
    req=Request('https://github.com/login/'+path, urlencode(data).encode(),
                {'Accept':'application/json','User-Agent':'ApplyGuard'})
    with urlopen(req,timeout=15) as response:
        return json.load(response)


def current(handle):
    row=SESSIONS.get(str(handle))
    if not row or row['expires']<=time.time():
        raise ValueError('GitHub 授权已撤销或过期，请重新连接。')
    return row


def authorized():
    with LOCK:return any(r.get('token') and r['expires']>time.time() for r in SESSIONS.values())


def repo_token(handle, name, sha=None):
    with LOCK:
        row=current(handle)
        if not row.get('token') or name.casefold() not in row.get('repos',{}):
            raise ValueError('请先在 GitHub 官方页面授权，并选择获准的仓库。')
        if sha is not None and (name.casefold(),sha.lower()) not in row.get('selected',set()):
            raise ValueError('请先选择并确认这个仓库的提交版本。')
        return row['token']


def pages(fetch,path,key,token):
    for page in range(1,11):
        values=fetch(path+f'?per_page=100&page={page}',token)[key]
        yield from values
        if len(values)<100:return


def handle(body,fetch):
    action=body['action']
    client=os.getenv('APPLYGUARD_GITHUB_APP_CLIENT_ID','').strip()
    if action=='github_app_start':
        if not client:raise ValueError('本机未配置 GitHub App Client ID。请管理员启用 Device Flow，仅申请 Contents 只读权限。')
        data=oauth('device/code',{'client_id':client})
        if not data.get('device_code') or not data.get('user_code'):raise ValueError('GitHub 未签发设备码，请检查 App 的 Device Flow 设置。')
        key=secrets.token_urlsafe(32);now=time.time()
        with LOCK:
            for entry in list(SESSIONS):
                if SESSIONS[entry]['expires']<=now:del SESSIONS[entry]
            if len(SESSIONS)>=32:raise ValueError('待确认的授权过多，请稍后再试。')
            SESSIONS[key]={'device':data['device_code'],'expires':now+min(900,data['expires_in']),
                           'interval':max(5,data.get('interval',5)), 'poll_after':now}
        return {'handle':key,'user_code':data['user_code'],'url':'https://github.com/login/device'}
    key=body.get('handle','')
    with LOCK:
        if action=='github_app_revoke':
            SESSIONS.pop(key,None);return {'revoked':True}
        row=current(key)
        if action=='github_app_poll':
            if row.get('token'):return {'repos':list(row['repos'].values()),'authorized':True}
            if time.time()<row['poll_after']:return {'authorized':False}
            row['poll_after']=time.time()+row['interval']
            device=row['device']
    if action=='github_app_poll':
        data=oauth('oauth/access_token',{'client_id':client,'device_code':device,'grant_type':'urn:ietf:params:oauth:grant-type:device_code'})
        if data.get('error') in {'authorization_pending','slow_down'}:
            if data['error']=='slow_down':
                with LOCK:
                    row['interval']+=5;row['poll_after']=time.time()+row['interval']
            return {'authorized':False}
        token=data.get('access_token')
        if not token:raise ValueError('GitHub 未授予访问权限，请重新开始。')
        repos={}
        for inst in pages(fetch,'user/installations','installations',token):
            if inst.get('client_id') and inst['client_id']!=client:continue
            permissions=inst.get('permissions',{})
            if permissions.get('contents')!='read' or any(v in {'write','admin'} for v in permissions.values()):continue
            for repo in pages(fetch,f"user/installations/{int(inst['id'])}/repositories",'repositories',token):
                if repo.get('private'):
                    repos[repo['full_name'].casefold()]=repo['full_name']
        with LOCK:
            current(key).update(token=token,repos=repos,expires=time.time()+min(1800,data.get('expires_in',1800)))
        return {'repos':list(repos.values()),'authorized':True}
    if action=='github_app_pin':
        name=str(body.get('repo',''));token=repo_token(key,name)
        info=fetch('repos/'+name,token)
        ref=fetch('repos/'+name+'/git/ref/heads/'+quote(info['default_branch'],safe=''),token)
        sha=ref.get('object',{}).get('sha','')
        if not re.fullmatch(r'[a-f0-9]{40}',sha) or ref['object'].get('type')!='commit':raise ValueError('未能确认版本。')
        with LOCK:
            current(key).setdefault('selected',set()).add((name.casefold(),sha))
        return {'spec':name+'@'+sha}
    raise ValueError('未知 GitHub 授权操作。')
