import base64
import hashlib
import json
import re
from pathlib import PurePosixPath
from backend.services.github_app_session import repo_token
from backend.services.github_discovery import REPO, public_request
from backend.services import evidence_workspace as ew


def import_readme(body,fetch):
    if body.get('confirm') is not True:
        raise ValueError('请先确认所选仓库与版本。')
    name,_,sha=str(body.get('spec','')).partition('@')
    if not REPO.fullmatch(name) or not re.fullmatch('[a-fA-F0-9]{40}',sha):
        raise ValueError('请选择有效的仓库版本。')
    ws=str(body.get('workspace_id',''))
    if not ew.get_workspace(ws):raise ValueError('材料库不存在。')
    handle=body.get('handle')
    path=f'repos/{name}/readme?ref={sha}'
    response=fetch(path,repo_token(handle,name,sha)) if handle else public_request(fetch,path)
    if response.get('type')!='file' or response.get('encoding')!='base64':raise ValueError('未找到可读 README。')
    raw=base64.b64decode(response['content'])
    if len(raw)>220_000:raise ValueError('README 太大，请选择更具体的材料。')
    text=raw.decode('utf-8-sig')
    source={'repo':name,'commit_sha':sha,'path':response['path'],'version':hashlib.sha256(raw).hexdigest()}
    if handle:repo_token(handle,name,sha)
    filename=name.replace('/','_')+'-'+sha[:10]+'-'+PurePosixPath(response['path']).name
    content='# GitHub 来源\n'+json.dumps(source,ensure_ascii=False)+'\n\n'+text
    result=ew.import_files(ws,[{'relative_path':filename if filename.lower().endswith('.md') else filename+'.md','content_base64':base64.b64encode(content.encode()).decode()}])
    file=result['files'][0]
    if file.get('parse_error'):raise ValueError('README 解析失败，请查看材料库。')
    return {'source':source,'evidence_id':file['evidence_id']}
