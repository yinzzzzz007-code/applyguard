"""Exercise a real model suggestion on a user-approved simulated local source."""
import getpass, json, os, sys
from decimal import Decimal
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'scripts')]
from start_recording_workspace import configure
from session_budget import install
workspace=root/'output/desktop-check/live-experience-suggestion'
configure(workspace/'local',workspace/'sag',0)
os.environ['APPLYGUARD_AI_API_KEY']=getpass.getpass('Model API key (hidden): ').strip()
install(root/'output/desktop-check/session-budget.json',Decimal('20'))
from backend.services import agent_bridge as bridge
source=Path(r'E:\pdf-collection\01_AI-Infra_演示材料\02_AI编译器动态计算图优化')
conn=bridge.create({'mode':'local','roots':[str(source)],'repos':[],
                    'task':'查找 AI 编译器优化项目经历','purpose':'contribution','disclosure':'cloud_allowed'})
try:
    bridge.agent_call({'id':conn['id'],'action':'task'},conn['token'])
    found=bridge.agent_call({'id':conn['id'],'action':'search','arguments':{'query':'编译器 优化'}},conn['token'])
    cards=found['cards']
    if not cards:raise ValueError('未找到候选原文')
    card=cards[0]
    bridge.agent_call({'id':conn['id'],'action':'submit','arguments':{'card_id':card['id'],'quote':card['quote'],
                      'version':card['source']['version'],'interpretation':'候选原文，等待用户核对。','missing':['本人职责需确认']}},conn['token'])
    result=bridge.ui_call({'id':conn['id'],'ui_token':conn['ui_token'],'action':'suggest_experience',
                           'card_id':card['id'],'job':'AI 基础设施工程师：编译器图优化、性能测试和内存管理。'})
    report={'candidate_count':len(cards),'source':card['source']['path'],
            'title':result.get('title'),'description':result.get('description'),
            'notice':result.get('notice'),'not_harness_model_session':True}
    workspace.mkdir(parents=True,exist_ok=True)
    (workspace/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
finally:
    bridge.GRANTS.pop(conn['id'],None)
