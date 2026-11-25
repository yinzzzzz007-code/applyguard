import ts from 'typescript'
import fs from 'node:fs'
import path from 'node:path'
const files=[]
function walk(dir){for(const item of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,item.name);if(item.isDirectory())walk(p);else if(p.endsWith('.tsx'))files.push(p)}}
walk('src')
const report={definitions:0,conditionalDisabled:0,emptyHandlers:[],nativeDisabledWithoutDirectReason:[]}
for(const file of files){
 const source=fs.readFileSync(file,'utf8'),ast=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 function visit(node){
  if(ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node)){
   const tag=node.tagName.getText(ast)
   if(['button','Button','ActionButton'].includes(tag)){
    report.definitions++
    const attrs=node.attributes.properties.filter(ts.isJsxAttribute),disabled=attrs.find(a=>a.name.getText(ast)==='disabled'),click=attrs.find(a=>a.name.getText(ast)==='onClick'),line=ast.getLineAndCharacterOfPosition(node.pos).line+1
    if(disabled)report.conditionalDisabled++
    const fn=click?.initializer&&ts.isJsxExpression(click.initializer)?click.initializer.expression:null
    if(fn&&ts.isArrowFunction(fn)&&ts.isBlock(fn.body)&&fn.body.statements.length===0)report.emptyHandlers.push({file,line})
    if(disabled&&tag!=='ActionButton'&&!attrs.some(a=>['title','aria-describedby','disabledReason'].includes(a.name.getText(ast))))report.nativeDisabledWithoutDirectReason.push({file,line,condition:disabled.getText(ast)})
   }
  }
  ts.forEachChild(node,visit)
 }
 visit(ast)
}
console.log(JSON.stringify(report,null,2))
process.exitCode=report.emptyHandlers.length||report.nativeDisabledWithoutDirectReason.length?1:0
