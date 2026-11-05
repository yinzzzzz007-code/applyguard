"""Fetch a pinned MIT subset, verify Git blob IDs, retain exact upstream bytes.

Run only for an intentional dependency update, never on application startup.
"""
import hashlib,json
from pathlib import Path
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO='Hisn00w/ASu-skills'
COMMIT='d27fd2a3864c48472a5c8ed942410098ba9cd35f'
FILES=('LICENSE','skills/great-resume/SKILL.md',
       'skills/great-resume/references/claim-evidence-ledger.md',
       'skills/great-resume/references/business-analysis-evidence.md',
       'assets/career-claim-ledger-template.json','scripts/validate_claim_ledger.py')

def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'ApplyGuard-source-review'}),timeout=30) as response:
        return response.read(1_000_001)

def main():
    tree=json.loads(fetch(f'https://api.github.com/repos/{REPO}/git/trees/{COMMIT}?recursive=1'))
    if tree.get('truncated'):raise ValueError('Incomplete upstream tree')
    blobs={row['path']:row['sha'] for row in tree['tree'] if row['type']=='blob'}
    content={}
    for name in FILES:
        raw=fetch(f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/{name}')
        if len(raw)>1_000_000:raise ValueError('Unexpected asset size')
        digest=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        if digest!=blobs[name]:raise ValueError('Upstream blob mismatch: '+name)
        content[name]=raw
    if b'MIT License' not in content['LICENSE']:raise ValueError('Expected MIT license')
    directory=ROOT/'third_party/asu-skills'
    for name,raw in content.items():
        path=directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    manifest={'repo':REPO,'commit':COMMIT,'committed_at':'2026-10-28T01:14:31Z','license':'MIT',
        'files':{name:{'git_blob_sha1':blobs[name],'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)} for name,raw in content.items()},
        'scope':'Exact original great-resume instructions, references, ledger template and standalone validator; no plugin installation.'}
    (directory/'UPSTREAM.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'repo':REPO,'commit':COMMIT,'files':len(content),'bytes':sum(map(len,content.values()))}))

if __name__=='__main__':main()
