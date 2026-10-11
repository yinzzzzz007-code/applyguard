"""Three reproducible offline workflows, even when an API key exists in the environment."""
import json
from pathlib import Path
from backend.services.model_client import ModelFailure
from backend.services.resume_selector import ResumeSelector
from backend.services.skill_router import SkillRouter

ROOT = Path(__file__).resolve().parents[1]
class TimeoutModel:
    def complete_json(self, *args):
        raise ModelFailure('Simulated timeout; no network used')
class InflatedSelector(ResumeSelector):
    def select(self, *args, **kwargs):
        result=super().select(*args, **kwargs)
        for claim in result.claims: claim['text']+=' Used CUDA.'
        return result

def run():
    mapping=json.loads((ROOT/'data/form-mapping.example.json').read_text())
    results={}
    for name,options in (('normal',{}),('unsupported_block',{'selector':InflatedSelector()}),('timeout_fallback',{'model':TimeoutModel()})):
        results[name]=SkillRouter(ROOT/'data/career-vault.seed.json',mapping,**options).run({
            'candidate_id':'cand_demo_001','jd_text':'Backend Developer requires Python and automated tests.'})
    assert results['normal']['workflow_status']=='AWAITING_HUMAN_CONFIRMATION'
    assert results['unsupported_block']['workflow_status']=='BLOCKED'
    assert results['timeout_fallback']['step_trace'][1]['fallback_reason']=='ModelFailure'
    return results

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False,indent=2))
