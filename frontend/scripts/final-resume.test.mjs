import assert from 'node:assert/strict'
import {test} from 'node:test'
import {reviewedResume} from '../src/resume/finalResume.ts'
import {normalizeResumeForm} from '../src/resume/formModel.ts'
import {buildPlainResume,resumeBlocks} from '../src/resume/generate.ts'
import {buildLatex} from '../src/resume/latex.ts'
test('final preview and TXT/TeX use accepted wording and exclusions, without changing the vault',()=>{
  const blank={organization:'',role:'',start:'',end:'',location:'',techStack:'',link:''}
  const form=normalizeResumeForm({candidateId:'cand_1',basic:{name:'演示用户'},projects:[{...blank,id:'proj_1',title:'AI项目',description:'旧原文'},{...blank,id:'proj_2',title:'排除项目',description:'不应导出'}]})
  const workflow={candidate_id:'cand_1',resume_claims:[{claim_id:'claim_proj_1',text:'已采用的新文字'},{claim_id:'claim_proj_2',text:'不应导出'}]}
  const result=reviewedResume(form,workflow,{claim_proj_2:{decision:'reject'}})
  assert.equal(result.projects.length,1)
  assert.equal(result.projects[0].description,'已采用的新文字')
  assert.equal(form.projects[0].description,'旧原文')
  for(const output of [buildPlainResume(result,'cn-academic'),buildLatex(resumeBlocks(result,'cn-academic'))]){
    assert.ok(output.includes('已采用的新文字'));assert.ok(!output.includes('旧原文'));assert.ok(!output.includes('不应导出'))
  }
  assert.equal(reviewedResume(form,{...workflow,candidate_id:'cand_other'},{}),form)
})
