"""Capture non-sensitive failure class from one real interview request."""
import getpass, json, os, sys
from decimal import Decimal
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'scripts')]
from start_recording_workspace import configure
from session_budget import install
out=root/'output/desktop-check/live-api-journey'
configure(out/'workspace',out/'sag',0)
os.environ.update(APPLYGUARD_AI_MAX_TOKENS='8192',APPLYGUARD_AI_TIMEOUT='180')
os.environ['APPLYGUARD_AI_API_KEY']=getpass.getpass('Model API key (hidden): ').strip()
install(root/'output/desktop-check/session-budget.json',Decimal('20'))
from backend.services import interview_guide
from backend.services.model_client import HttpModelClient, json_schema_instruction, uses_json_object_structured
from jsonschema import Draft202012Validator
class InspectClient(HttpModelClient):
    def complete_structured(self, system_prompt, user_prompt, schema):
        if uses_json_object_structured(self.base_url,self.model):
            system_prompt+='\n'+json_schema_instruction(schema)
        result=self._complete(system_prompt,user_prompt,schema=schema)
        errors=list(Draft202012Validator(schema).iter_errors(result))
        for error in errors[:8]:
            print('SCHEMA_FAILURE',list(error.absolute_path),error.validator,flush=True)
        return result
if '--inspect' in sys.argv:
    interview_guide.HttpModelClient=InspectClient
original=interview_guide.structured
def capture(*args,**kwargs):
    try:return original(*args,**kwargs)
    except Exception as exc:
        print('MODEL_FAILURE',type(exc).__name__,getattr(exc,'code',None),getattr(exc,'http_status',None),str(exc)[:200],flush=True)
        raise
interview_guide.structured=capture
try:
    result=interview_guide.generate_interview({'jd_text':'算法工程师岗位职责：负责构建模型评测流程，整理测试数据，分析模型错误。任职要求：熟悉 Python，具备机器学习与评测经验。',
        'resume':{'projects':[{'title':'模型评测模拟项目','description':'使用 Python 实现模型评测流程，整理测试样本并分析错误类型。'}]}})
    report={'success':True,'questions':len(result['questions']),'has_practice':bool(result.get('practice'))}
    from backend.services.interview_practice import practice
    try:
        reply=practice({**result['practice'],'action':'answer',
                        'answer':'我会先整理测试样本，检查数据分布，再按错误类型分析模型输出。'})
        report['answer_scored']=bool(reply.get('scores'))
        report['followup_received']=bool(reply.get('question'))
    except Exception as exc:
        report['practice_error_type']=type(exc).__name__
        report['practice_error']=str(exc)[:200]
except Exception as exc:
    report={'success':False,'error_type':type(exc).__name__,'error':str(exc)[:200]}
(out/'interview-diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
