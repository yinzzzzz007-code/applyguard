import assert from 'node:assert/strict'
import {test} from 'node:test'
import {NAV_GROUPS} from '../src/navigation.ts'
import {resumeCompleteness,normalizeResumeForm} from '../src/resume/formModel.ts'

test('evidence belongs to primary preparation, and every existing route appears exactly once',()=>{
 const paths=NAV_GROUPS.flatMap(group=>group.items.map(item=>item.path))
 assert.equal(new Set(paths).size,paths.length)
 assert.deepEqual(new Set(paths),new Set(['/','/vault','/evidence','/jobs','/jd','/match','/resume','/claims','/ats','/confirm','/history']))
 assert.ok(NAV_GROUPS[0].items.some(item=>item.path==='/evidence'))
})
test('optional identity and demographic fields never increase core readiness',()=>{
 const form=normalizeResumeForm({candidateId:'test',basic:{name:'虚构用户'},intention:{},education:[],internships:[],projects:[],awards:[],extras:{}})
 const before=resumeCompleteness(form)
 const withOptional={...form,basic:{...form.basic,gender:'女',birthday:'2004-01-01',idType:'其他',idNo:'FICTIONAL',ethnicity:'汉族',politics:'群众',hukou:'演示城市'}}
 assert.equal(resumeCompleteness(withOptional),before)
 assert.ok(before>=0&&before<=100)
})
