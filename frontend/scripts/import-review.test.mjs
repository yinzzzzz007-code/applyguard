import assert from 'node:assert/strict'
import {test} from 'node:test'
import {emptyResumeForm} from '../src/resume/formModel.ts'
import {prepareImport,pendingImport,resolveImport} from '../src/resume/importReview.ts'

const base=()=>({...emptyResumeForm('fictional'),education:[],dirty:false})
const project=(id,description='原有职责',start='2024-01')=>({id,title:'虚构数据平台',organization:'示例组织',role:'开发',start,end:'2024-06',description,location:'',techStack:'Python',link:''})
test('first import classifies rows and saving does not mutate its source',()=>{
 const input=base();input.projects=[project('parsed')]
 const review=prepareImport('fictional',input)
 assert.equal(pendingImport(review,{}),0)
 const saved=resolveImport(review,{})
 assert.equal(saved.projects.length,1);assert.equal(saved.education.length,0);assert.equal(saved.dirty,false)
 assert.equal(review.previous.projects.length,0)
})
test('repeat import is idempotent and retains material target identity',()=>{
 const old=base();old.projects=[{...project('linked-id'),sourceExperienceId:'original-evidence-target'}]
 const input=base();input.projects=[project('new-id')]
 const result=resolveImport(prepareImport('fictional',input,old),{})
 assert.equal(result.projects.length,1);assert.equal(result.projects[0].id,'linked-id')
 assert.equal(result.projects[0].sourceExperienceId,'original-evidence-target')
})
test('changed dates or description require a decision; imported blanks retain manual details',()=>{
 const old=base();old.projects=[{...project('stable'),location:'手动填写地点'}]
 const input=base();input.projects=[project('parsed','本次职责','2025-01')]
 const review=prepareImport('fictional',input,old), key=review.rows[0].key
 assert.equal(pendingImport(review,{}),1);assert.throws(()=>resolveImport(review,{}))
 const result=resolveImport(review,{[key]:{action:'import'}})
 assert.equal(result.projects[0].id,'stable');assert.equal(result.projects[0].start,'2025-01')
 assert.equal(result.projects[0].location,'手动填写地点')
 assert.equal(resolveImport(review,{[key]:{action:'keep'}}).projects[0].description,'原有职责')
 assert.equal(resolveImport(review,{[key]:{action:'both'}}).projects.length,2)
})
test('ambiguous candidates require an explicit target for update',()=>{
 const old=base();old.projects=[project('one'),project('two','另一段职责','2023-01')]
 const input=base();input.projects=[project('parsed','新内容')]
 const review=prepareImport('fictional',input,old),key=review.rows[0].key
 assert.equal(pendingImport(review,{[key]:{action:'import'}}),1)
 const saved=resolveImport(review,{[key]:{action:'import',targetId:'two'}})
 assert.equal(saved.projects[0].description,'原有职责');assert.equal(saved.projects[1].description,'新内容')
})
test('manual entries and missing profile fields survive a newer resume',()=>{
 const old=base();old.basic.email='fictional@example.test';old.projects=[project('manual')]
 const input=base();input.basic.name='虚构用户'
 const saved=resolveImport(prepareImport('fictional',input,old),{})
 assert.equal(saved.basic.email,old.basic.email);assert.equal(saved.projects[0].id,'manual')
})
test('changed profile fields require explicit confirmation',()=>{
 const old=base();old.basic.email='old@example.test'
 const input=base();input.basic.email='new@example.test'
 const review=prepareImport('fictional',input,old),key=review.fields[0].key
 assert.throws(()=>resolveImport(review,{}))
 assert.equal(resolveImport(review,{[key]:{action:'keep'}}).basic.email,old.basic.email)
 assert.equal(resolveImport(review,{[key]:{action:'import'}}).basic.email,input.basic.email)
})
test('duplicate incoming rows are added only once',()=>{
 const input=base();input.projects=[project('a'),project('b')]
 assert.equal(resolveImport(prepareImport('fictional',input),{}).projects.length,1)
})

test('staged import removes only untouched legacy education placeholder',async()=>{
 const {stageResumeImport}=await import('../src/resume/importTransfer.ts')
 const input=base();input.education=[{id:'recognized',school:'Example University',major:'CS',degree:'Bachelor',start:'2020-09',end:'2024-06',gpa:'',rank:'',courses:''}]
 const parsed={filename:'fictional.pdf',extractor:'text',preview:'source',source_text:'complete source',form:input}
 const empty=emptyResumeForm('fictional')
 const result=stageResumeImport(empty,{id:'transfer-empty',result:parsed})
 assert.equal(result.education.length,1);assert.equal(result.education[0].school,'Example University')
 assert.equal(result.dirty,true);assert.equal(result.importContext.text,'complete source')
 empty.education[0].school='Manual University'
 const preserved=stageResumeImport(empty,{id:'transfer-manual',result:parsed})
 assert.ok(preserved.education.some(row=>row.school==='Manual University'))
})
