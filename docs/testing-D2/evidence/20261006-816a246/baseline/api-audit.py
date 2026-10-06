"""Read-only local/offline probes; inputs are fictional and evidence is retained."""
import json, sys, hashlib, platform, urllib.request, urllib.error
from pathlib import Path
from backend.app import build_mock_workflow
from backend.services.claim_validator import ClaimValidator
root=Path(__file__).resolve().parents[2]
out=root/'output/d2-audit'
vault=json.loads((root/'data/career-vault.seed.json').read_text(encoding='utf-8'))
results={}
results['runtime']={'python':sys.version,'platform':platform.platform()}
for key,jd in {
 'default_chinese':'后端开发实习生。岗位职责：使用 Python 编写接口服务、补充自动化测试，并使用版本协作。加分项：有数据处理相关项目经验。',
 'unrelated_ml':'算法开发实习生\n任职要求\n熟悉推荐系统。熟悉强化学习。熟悉多模态。',
}.items():
    results[key]=build_mock_workflow({'candidate_id':'cand_demo_001','jd_text':jd,'parse_mode':'offline'})
results['chinese_seed_verification']=[]
for exp in vault['experiences']:
    for c in exp['claims']:
        result=ClaimValidator().verify({**c,'evidence_support_score':0.9},vault['experiences'],'cand_demo_001')
        results['chinese_seed_verification'].append({'claim_id':c['claim_id'],'state':result['state']})
results['manual_backend_verification']=ClaimValidator().verify({'claim_id':'claim_manual_probe','text':'我独立负责千万用户推荐系统，获得全国竞赛一等奖。','evidence_ids':[],'evidence_support_score':0},vault['experiences'],'cand_demo_001')
results['static_routes']=[]
for route in ['/', '/health','/data/career-vault.seed.json','/prerecorded/unsupported_block.json','/jd']:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000'+route) as r:
            results['static_routes'].append({'path':route,'status':r.status,'type':r.headers['Content-Type']})
    except urllib.error.HTTPError as e:
        results['static_routes'].append({'path':route,'status':e.code,'body':e.read().decode()})
results['seed_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'data/career-vault.seed.json',root/'frontend/public/data/career-vault.seed.json']}
(out/'api-audit-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'seed_checks':results['chinese_seed_verification'],'manual_backend':results['manual_backend_verification'],'routes':results['static_routes'],'seed_hash':results['seed_sha256'],'ml_requirements':results['unrelated_ml']['parsed_jd']['requirements'],'ml_matches':results['unrelated_ml']['evidence_match']},ensure_ascii=False,indent=2))
