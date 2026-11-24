import ts from 'typescript'
import {readdir,readFile,mkdir,writeFile} from 'node:fs/promises'
import {resolve,relative,join} from 'node:path'
const root=resolve(import.meta.dirname,'..'), rows=[]
async function scan(dir){for(const entry of await readdir(dir,{withFileTypes:true})){
 const path=join(dir,entry.name)
 if(entry.isDirectory()){await scan(path);continue}
 if(!path.endsWith('.tsx'))continue
 const text=await readFile(path,'utf8'), file=ts.createSourceFile(path,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX)
 function visit(node){if(ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node)){
  const tag=node.tagName.getText(file)
  if(['button','Button','ActionButton'].includes(tag)){
   const props=node.attributes.properties.filter(ts.isJsxAttribute), disabled=props.find(p=>p.name.getText(file)==='disabled')
   rows.push({file:relative(root,path).replaceAll('\\','/'),line:file.getLineAndCharacterOfPosition(node.getStart(file)).line+1,
    label:node.parent.getText(file).slice(0,700).replace(/\s+/g,' '),disabled:disabled?.initializer?.getText(file)??null,
    reason:props.find(p=>p.name.getText(file)==='disabledReason')?.initializer?.getText(file)??null,
    title:props.find(p=>p.name.getText(file)==='title')?.initializer?.getText(file)??null})
  }
 }ts.forEachChild(node,visit)}visit(file)
}}
await scan(join(root,'src'))
const directory=resolve(root,'../output/ui-followup');await mkdir(directory,{recursive:true})
await writeFile(join(directory,'button-source-inventory.json'),JSON.stringify({scope:'Static source inventory; runtime availability still requires UI verification.',buttons:rows.length,conditional:rows.filter(r=>r.disabled!==null).length,items:rows},null,2))
console.log(JSON.stringify({buttons:rows.length,conditional:rows.filter(r=>r.disabled!==null).length,files:new Set(rows.map(r=>r.file)).size,report:join(directory,'button-source-inventory.json')}))

const missing=rows.filter(r=>r.disabled&&!r.reason&&!r.file.endsWith("ui/action-button.tsx"));if(missing.length){console.error(JSON.stringify(missing));process.exitCode=1}
