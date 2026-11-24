import {reviewMarks} from '../src/resume/reviewHighlights.ts'
import {test} from 'node:test'
import assert from 'node:assert/strict'
import {evidenceCoverage,isQuantitative,retainRemaining,retainedFieldValue} from '../src/resume/claimReview.ts'
import {buildLatex} from '../src/resume/latex.ts'
import {splitBullets} from '../src/resume/generate.ts'

const citation = {start:0,end:3,quote:'247'}
const atom = (text,relation,citations=[]) => ({text,relation,citations})
const grade = (atoms, state='NEEDS_REVIEW') => evidenceCoverage({atoms,state,complete:state==='VERIFIED',retrieved_sources:[{}]},false,false,true,'ready')

test('distinguishes missing, candidate, linked and backed evidence',()=>{
  assert.equal(evidenceCoverage(undefined,false,false,false,'ready').label,'暂无已关联材料')
  assert.match(evidenceCoverage(undefined,false,true,false,'ready').label,/候选/)
  assert.match(evidenceCoverage(undefined,true,false,false,'ready').label,/已关联/)
  assert.match(evidenceCoverage(undefined,false,false,false,'error').label,/查询未完成/)
  const supported=atom('获得银牌','SUPPORTED',[citation])
  assert.equal(grade([supported],'VERIFIED').label,'材料已支持')
  assert.equal(grade([atom('独立实现','SUPPORTED')]).supported.length,0)
  const partial=grade([supported,atom('LoRA 训练','INSUFFICIENT'),atom('Top 4.7%','INSUFFICIENT')])
  assert.equal(partial.label,'材料支持部分事实')
  assert.deepEqual(partial.unresolved.map(a=>a.text),['Top 4.7%','LoRA 训练'])
  assert.equal(grade([supported,atom('排名 246','CONTRADICTED',[citation])]).label,'材料有冲突')
  assert.equal(isQuantitative('使用 Nemotron-3-Nano-30B-A3B'),false)
  assert.equal(evidenceCoverage({atoms:[supported],retrieved_sources:[{}]},false,false,false,'ready').supported.length,0)
})

test('bulk retention is idempotent, leaves exclusions and edits intact',()=>{
  const claims=['a','b','c'].map(claim_id=>({claim_id}))
  const previous={b:{claim_id:'b',decision:'reject',freshness:'rejected'},c:{claim_id:'c',decision:'edit',editedText:'新文字',freshness:'edited_pending_reverify'}}
  const next=retainRemaining(claims,previous)
  assert.equal(next.a.decision,'confirm')
  assert.equal(next.b,previous.b)
  assert.equal(next.c,previous.c)
  assert.equal(retainRemaining(claims,next),next)
})

test('TeX exports readable sections, balanced lists, literal user text and numerical facts',()=>{
  const tex=buildLatex([{kind:'name',text:'王 & Li'}, {kind:'heading',text:'Projects'}, {kind:'bullet',text:'4.7% · C# · data_set'}, {kind:'bullet',text:'$1 ~ ^'}, {kind:'text',text:'\\input{file}\n下一句'}])
  assert.match(tex,/\\section\*\{Projects\}/)
  assert.ok(tex.includes('王 \\& Li'))
  assert.ok(tex.includes('4.7\\% · C\\# · data\\_set'))
  assert.ok(tex.includes('\\textbackslash{}input\\{file\\}\\par\n下一句'))
  assert.ok(tex.indexOf('\\end{itemize}')<tex.indexOf('\\textbackslash{}'))
  assert.ok(tex.endsWith('\\end{document}\n'))
  assert.deepEqual(splitBullets('4.7% 提升\n247/5,255\n1. 完成评测'),['4.7% 提升','247/5,255','完成评测'])
})

test('retained summaries omit excluded source text from the next two screens',()=>{
  const field={field_id:'candidate_summary',label:'候选人摘要',source_claim_ids:['a','b'],value:'旧的合并摘要'}
  const w={resume_claims:[{claim_id:'a',text:'修订后的项目'},{claim_id:'b',text:'排除项'}],field_controls:[]}
  const decisions={b:{claim_id:'b',decision:'reject',freshness:'rejected'}}
  assert.equal(retainedFieldValue(w,field,decisions),'修订后的项目')
  assert.equal(retainedFieldValue(w,{...field,field_id:'other',label:'经验'},decisions),'')
  assert.equal(retainedFieldValue(w,field,{}),'旧的合并摘要')
})

test('unlinked and stale claims still point to current metrics and roles without alleging conflict',()=>{
  const text='Kaggle Silver, 246/5,252, Top 4.7% · 共同第一作者 · Nemotron-3-Nano-30B'
  const report={material_status:'no_related_material',atoms:[]}
  const marks=reviewMarks(text,report,true,true)
  assert.deepEqual(marks.map(m=>text.slice(m.start,m.end)),['Kaggle Silver','246/5,252','Top 4.7%','共同第一作者'])
  assert.ok(marks.every(m=>m.kind==='pending'))
  assert.equal(reviewMarks(text,report,true,false).length,0)
  assert.ok(reviewMarks('提交报告',undefined,false,true).length)
  assert.equal(reviewMarks('当前排名第 3 名',{atoms:[{relation:'CONTRADICTED'}]},false,true)[0].kind,'pending')
})

test('exact text and same-version spans locate conflict, including repeated words after emoji',()=>{
  const text='🧪 第3名，原稿第3名。'
  const atom={claim_excerpt:'第3名',text:'排名第三',relation:'CONTRADICTED',citations:[{start:0,end:3,quote:'第4名'}],claim_spans:[{start:6,end:11,quote:'原稿第3名'}],reason:'证书写第4名'}
  let marks=reviewMarks(text,{atoms:[atom]},true,true)
  assert.deepEqual(marks.map(m=>[m.start,text.slice(m.start,m.end),m.kind,m.evidence]),[[text.lastIndexOf('第3名'),'第3名','conflict','第4名']])
  assert.equal(reviewMarks(text,{atoms:[{...atom,relation:'SUPPORTED'}]},true,true).length,0)
  assert.equal(reviewMarks(text,{atoms:[{...atom,citations:[]}]},true,true)[0].kind,'pending')
  assert.equal(reviewMarks(text,{atoms:[{...atom,claim_spans:[],anchor_reason:'ambiguous_excerpt'}]},true,true).length,0)
  assert.equal(reviewMarks(text,{atoms:[{...atom,claim_spans:[{start:3,end:5,quote:'不匹配'}]}]},true,true).length,0)
})

test('overlapping claims keep a supported subphrase plain while cited conflicts retain their exact location',()=>{
  const text='取得银牌，排名第3名'
  const a=(quote,relation,citations=[])=>({text:quote,claim_excerpt:quote,relation,citations,reason:'查看原件'})
  const cite=[{quote:'比赛证书',start:1,end:5}]
  const marks=reviewMarks(text,{atoms:[a(text,'INSUFFICIENT'),a('银牌','SUPPORTED',cite),a('第3名','CONTRADICTED',cite)]},true,true)
  assert.deepEqual(marks.map(m=>[text.slice(m.start,m.end),m.kind]),[['取得','pending'],['，排名','pending'],['第3名','conflict']])
})
