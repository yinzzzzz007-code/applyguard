"""Adapt the MIT kinetic-reel template into an application-owned renderer.
No browser automation, model calls or resume data are used by this build script.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / 'vendor/kinetic-reel'
raw = (UPSTREAM / 'skills/kinetic-reel/template/reel/reel.js').read_text(encoding='utf-8')
# Retain the actual template's drawing, shader, typography and transition core.
core = raw[raw.index('// ---------- math ----------'):raw.index('// ---------- demo scenes')]
core = core.replace("const out = document.getElementById('out');", '')
core = core[:core.index('// ---------- GL layer 3:')] + core[core.index('// ---------- post pass ----------'):]
core = core.replace('const nx = 220, nz = 140', 'const nx = 128, nz = 80')
core = core.replace('RA.setPixelRatio(1); RA.setSize(W, H, false);', 'RA.setPixelRatio(1); RA.setSize(Math.round(W * .67), Math.round(H * .67), false);')
core = core.replace('RP.setPixelRatio(1); RP.setSize(W, H, false);', 'RP.setPixelRatio(1); RP.setSize(Math.round(W * .83), Math.round(H * .83), false);')
core = core.replace('vec3 blue = vec3(.19,.24,1.), red = vec3(.93,.33,.23), lil = vec3(.75,.68,.98), navy = vec3(.06,.07,.32), cream = vec3(.98,.9,.86);', 'vec3 blue = vec3(.145,.388,.922), red = vec3(.577,.20,.918), lil = vec3(.80,.75,.98), navy = vec3(.09,.13,.22), cream = vec3(.97,.98,.99);')
core = core.replace('const n = s.length;', 'const glyphs = Array.from(s); const n = glyphs.length;').replace("const ch = s[i];", "const ch = glyphs[i];").replace('s.slice(0, i)', "glyphs.slice(0, i).join('')")
# Drop template-only examples and unused helpers rather than suppressing lint.
import re
for first,last in [
    ('// the Jelly mark:', '// HUD:'),
    ('// ---------- scenes ----------','// ---------- v2 helpers ----------'),
    ('// a label chip,','function arrow('),
    ('// big number + small label','// drop-in word:'),
    ('function redacted(', 'const bez ='),
    ('const trZoom =','const trPush ='),
    ('const trGrid =','// ---------- demo scenes'),
]:
    if first in core:
        end = core.index(last) if last in core else len(core)
        core = core[:core.index(first)] + core[end:]
for prefix in ['const backOut =','const hash =','const sec =','const count =','const glitchIn =','const DARK =','const easeOut =','let TRANS =']:
    core = re.sub(r'^'+re.escape(prefix)+r'.*\n','',core,flags=re.M)
core = re.sub(r'^// ---------- (01 MICROSOFT|02 UW|03 ENTERPRISE|index|finale).*\n','',core,flags=re.M)
# Avoid an accidental flashlight on cuts: motion carries the impact.
header = '''/* Derived from kinetic-reel by tuzhechen2005, MIT, commit 59744a69c7b916cfbe4c4ec84006b0c2f5e2fde1.
 * Adapted for ApplyGuard: local project text, responsive scenes, 24s, blue/violet palette,
 * optional WebGL, reduced-motion stills and explicit GPU cleanup. See THIRD-PARTY-NOTICES.md.
 */
import * as THREE from 'three';
import {projectStart,REEL_DURATION} from './reel.ts';
export async function createKineticReel(out, projects, options = {}) {
const compact = options.compact === true;
const W = compact ? 1080 : 1920, H = compact ? 1350 : 1080, FPS = 30, BEAT = .5;
const starts = projects.map((_,index)=>projectStart(index,projects.length));
const C = { dur: REEL_DURATION, CH: [['OPEN',0,3],...projects.map((p,i)=>[String(i+1),starts[i],starts[i+1]??21]),['END',21,24]] };
const K = {ink:'#111318', ink2:'#242933', cream:'#F8FAFC', lime:'#2563EB', blue:'#2563EB', red:'#9333EA', grey:'#CBD5E1', mid:'#64748B'};
const F = {cond:'"Reel Anton"', wide:'"Reel Archivo"', serif:'"Reel Instrument"', mono:'"Consolas",monospace', zh:'"Microsoft YaHei","PingFang SC",sans-serif'};
'''
scenes = r'''
// ---------- ApplyGuard: a source becomes an authored film ----------
const M = compact ? 76 : 140;
const metaFont = font(F.zh, compact ? 25 : 28, 500);
function cropText(text, size, width, maxLines = 2, face = F.zh, weight = 700) {
  const f = font(face, size, weight), chars = Array.from(String(text).replace(/\s+/g,' '));
  const lines = []; let lineText = '';
  for (const ch of chars) {
    if (measure(lineText + ch, f) > width && lineText && !/^[。，；！？、：）》】]$/.test(ch)) { lines.push(lineText); lineText = ''; }
    lineText += ch;
  }
  if (lineText) lines.push(lineText);
  if (lines.length > maxLines) {
    lines.length = maxLines;
    while (measure(lines[maxLines-1] + '…', f) > width) lines[maxLines-1] = Array.from(lines[maxLines-1]).slice(0,-1).join('');
    lines[maxLines-1] += '…';
  }
  return {lines, f};
}
function block(text, x, y, width, size, color, maxLines = 2, t = 2, t0 = 0) {
  const {lines, f} = cropText(text, size, width, maxLines);
  ctx.save();ctx.beginPath();ctx.rect(x-5,y-size*1.16,width+10,size*(maxLines*1.32+.1));ctx.clip();
  lines.forEach((s,i) => dropWord(s,x,y+i*size*1.32,f,t0+i*.12,t,{fill:color,fall:100,stag:.02,dur:.38}));
  ctx.restore();
  return lines.length * size * 1.32;
}
function filmHud(t, title, dark = true, schematic = false) {
  hud(t, { dark, tl:'APPLYGUARD / QUICK START', tr:tc(t),
    bl:title, br:schematic?'WORKFLOW / HOW TO USE':'QUICK START / APPLYGUARD',
    zh:'先核对，再采用；缺依据先处理', zhRight:true, brackets:true });
}
function sourcePieces(project) {
  const text=project.body||project.original;
  const clauses = text.split(/(?<=[。；;])/).map(s=>s.trim()).filter(Boolean);
  return clauses.length ? clauses : [text];
}
function terms(project) {
  return project.terms || [];
}

function open(t) {
  bg(K.ink); glShot(terrain(t,{fade:.55,amp:1.6,push:t*.35,camY:2.4}));
  const titleY = compact ? 360 : 430, big = compact ? 235 : 300;
  for(let i=-1;i<3;i++) txt('APPLY',M,titleY+i*big*.94,{font:font(F.wide,big),fill:null,stroke:'rgba(248,250,252,.12)',lw:2});
  dropWord('APPLY',M,titleY,font(F.wide,big),0,t,{fall:260,stag:.09,fill:K.cream});
  dropWord('WITH CARE.',M,titleY+(compact?180:205),font(F.cond,compact?142:190),.5,t,{fall:160,stag:.035,fill:K.lime});
  const yy=compact?890:790;
  txt('用自己的材料，准备一份申请。',M,yy,{font:font(F.zh,compact?38:44,700),fill:K.cream,a:seg(t,1,1.5)});
  txt(`${projects.length} 个阶段 / 24 秒快速入门`,M,yy+68,{font:metaFont,fill:K.grey,a:seg(t,1.5,1.8)});
  const cx=compact?880:1600,cy=compact?960:700;
  circle(cx,cy,60+beatPulse(t)*12,{stroke:K.lime,lw:3,a:seg(t,1.5,2)});
  circle(cx,cy,8,{fill:K.cream}); RECT.open=[cx-64,cy-64,128,128];
  filmHud(t,'QUICK START / 24s');
}
function projectOne(t, p, start, index) {
  const lt=t-start; bg(K.blue);
  const numX=compact?750:1500,numY=compact?380:520;
  txt(String(index+1).padStart(2,'0'),numX,numY,{font:font(F.cond,compact?370:500),fill:'rgba(248,250,252,.13)',align:'center'});
  dropWord(p.word || 'START.',M,compact?290:320,font(F.cond,compact?180:230),start,t,{fill:K.cream,fall:200,stag:.05});
  block(p.title,M,compact?430:455,compact?920:1510,compact?77:100,K.cream,2,t,start+.5);
  const meta=cropText([p.role,p.period].filter(Boolean).join(' / '),compact?25:28,compact?920:1500,1,F.zh,500);
  txt(meta.lines[0]||'',M,compact?680:690,{font:meta.f,fill:K.cream,a:seg(lt,1.2,1.6)});
  let words=terms(p); if(!words.length) words=[p.title];
  const yy=compact?865:830, cellW=compact?280:245,gap=compact?24:20;
  words.slice(0,compact?3:6).forEach((word,i)=>{
    const x=M+i*(cellW+gap), k=seg(lt,1.5+i*.15,1.8+i*.15);
    rrect(x,yy,cellW,92*expoOut(k),0,{fill:K.cream,a:k});
    const {lines,f}=cropText(word,compact?34:35,cellW-30,1,F.cond,500);
    txt(lines[0]||'',x+15,yy+61,{font:f,fill:K.blue,a:k});
    if(i<words.length-1 && i<(compact?2:5)) arrow(x+cellW+2,yy+46,x+cellW+gap-3,yy+46,K.cream,2,k,5);
    const phase=((lt-2-i*.5)%2+2)%2, hop=seg(phase,0,.5);
    if(lt>2+i*.5) circle(x+cellW*hop,yy-18,7,{fill:K.cream});
  });
  const original=p.body||p.original;
  const text=Array.from(original).slice(0,compact?38:64).join('')+(Array.from(original).length>(compact?38:64)?'…':'');
  block(text,M,compact?1080:950,compact?920:1600,compact?30:27,K.cream,compact?2:1,t,start+2);
  filmHud(t,`STEP ${index+1} / START HERE`,true,true);
}
function projectTwo(t,p,start,index) {
  const lt=t-start; bg(K.cream);
  const y=compact?220:260;
  dropWord('ADD',M,y,font(F.cond,compact?150:180),start,t,{fill:K.ink,fall:150});
  const src=liquid(t,{zoom:1.4,seed:index+3});
  texWindow(()=>{txt('EVIDENCE.',M,y+(compact?155:180),{font:font(F.cond,compact?177:220),fill:K.ink});},src);
  block(p.title,M,compact?600:565,compact?920:1480,compact?67:83,K.ink,2,t,start+.5);
  const pieces=sourcePieces(p).slice(0,3), yy=compact?825:755, row=compact?100:74;
  pieces.forEach((piece,i)=>{
    const k=seg(lt,.9+i*.5,1.3+i*.5),x=M+(1-expoOut(k))*90;
    line([[x,yy+i*row+19],[x+35,yy+i*row+19]],K.blue,4,k);
    const {lines,f}=cropText(piece,compact?30:29,compact?840:1460,1);
    txt(lines[0]||'',x+60,yy+i*row+30,{font:f,fill:K.ink,a:k});
  });
  circle(W-M-20,compact?650:570,30+14*beatPulse(t),{stroke:K.blue,lw:4});
  filmHud(t,`STEP ${index+1} / ADD EVIDENCE`,false);
}
function projectThree(t,p,start,index) {
  const lt=t-start; bg(K.ink); glShot(terrain(t,{fade:.25,amp:1,push:1.5,camY:4}));
  dropWord(p.word || 'MATCH.',M,compact?260:300,font(F.cond,compact?165:210),start,t,{fill:K.cream,fall:170});
  block(p.title,M,compact?430:455,compact?920:1530,compact?68:88,K.cream,2,t,start+.5);
  const pieces=sourcePieces(p).slice(0,3), count=pieces.length, y=compact?820:760;
  const width=compact?920:1640, gap=compact?24:45, cell=(width-gap*(count-1))/count;
  pieces.forEach((piece,i)=>{
    const x=M+i*(cell+gap),k=seg(lt,1+i*.3,1.4+i*.3);
    rrect(x,y,cell,compact?220:160,8,{fill:i===Math.floor(Math.max(0,lt-2)*2)%count?K.blue:K.ink2,a:k});
    const {lines,f}=cropText(piece,compact?29:30,cell-42,compact?5:3);
    lines.forEach((s,j)=>txt(s,x+21,y+50+j*(compact?37:40),{font:f,fill:K.cream,a:k}));
    if(i<count-1) thread([x+cell,y+80],[x+cell+gap,y+80],seg(lt,1.5+i*.5,2+i*.5),K.red,4);
  });
  filmHud(t,`STEP ${index+1} / PREPARE ONE JOB`,true,true);
}
function finale(t) {
  const lt=t-21; bg(K.ink);
  glShot(terrain(t,{fade:.5,amp:1.8,push:2,camY:2.5}));
  dropWord('CHECK.',M,compact?330:350,font(F.cond,compact?210:230),21,t,{fill:K.cream,fall:100});
  dropWord('THEN.',M,compact?535:560,font(F.cond,compact?210:230),21.25,t,{fill:K.cream,fall:100});
  dropWord('APPLY.',M,compact?740:770,font(F.cond,compact?195:230),21.5,t,{fill:K.lime,fall:100});
  txt('Check first. Then apply.',compact?M:1090,compact?1140:530,{font:`italic ${compact?48:72}px ${F.serif}`,fill:K.cream,a:seg(lt,1.3,1.8)});
  const base=compact?920:875,total=compact?900:1640;
  projects.forEach((p,i)=>{
    const x=M+total*(starts[i]-3)/18,w=total*((starts[i+1]??21)-starts[i])/18-14,k=seg(lt,.7+i*.2,1+i*.2);
    rrect(x,base,w*expoOut(k),12,0,{fill:i===0?K.lime:i===1?K.cream:K.red});
    const {lines,f}=cropText(p.title,compact?24:28,w,1);
    txt(lines[0]||'',x,base+52,{font:f,fill:K.cream,a:k});
  });
  filmHud(t,'APPLYGUARD / 先核对，再申请');
}
const SCENES=[[0,open,'open'],...projects.map((p,i)=>[starts[i],t=>[projectOne,projectTwo,projectThree,projectOne][i%4](t,p,starts[i],i),'p'+i]),[21,finale,'end']];
const TR={p0:[.55,trIris(compact?880:1600,compact?960:700,K.blue)],p1:[.5,trPush(1,0)],p2:[.55,trWipe(K.red)],p3:[.5,trIris(W/2,H/2,K.blue)],end:[.6,trSlats(8)]};
function renderInto(i,t,buf) {
 ctx=buf.getContext('2d');ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.clearRect(0,0,W,H);SCENES[i][1](t);ctx=mainCtx;
}
function frame(t,still=false) {
 t=((t%C.dur)+C.dur)%C.dur;
 FX={split:0,slice:0,seed:0,grain:.018,vign:.13,flash:0,flashCol:K.cream};
 let i=0;while(i+1<SCENES.length&&t>=SCENES[i+1][0])i++;
 const [s,fn,key]=SCENES[i],tr=TR[key];
 ctx=mainCtx;ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.shadowBlur=0;
 if(still){fn(Math.max(t,s+1.8));}
 else if(tr&&i>0&&t<s+tr[0]){
   renderInto(i-1,s-1/FPS,bufA);renderInto(i,t,bufB);tr[1](seg(t,s,s+tr[0]),bufA,bufB,ctx);
 }else{fn(t);}
 post(t,FX);
}
await Promise.all([document.fonts.load('100px "Reel Anton"'),document.fonts.load('100px "Reel Archivo"'),document.fonts.load('italic 100px "Reel Instrument"')]);
return { draw:frame, dispose(){RA.dispose();RP.dispose();RA.forceContextLoss();RP.forceContextLoss();[c2,bufA,bufB,bufT,glA].forEach(c=>{c.width=1;c.height=1;});} };
}
'''
(ROOT / 'frontend/src/motion/kineticEngine.js').write_text(header + core + scenes, encoding='utf-8')
notices = ROOT / 'THIRD-PARTY-NOTICES.md'
notices.write_text('# Kinetic reel\n\nAdapted from tuzhechen2005/opus-video-skills, commit 59744a69c7b916cfbe4c4ec84006b0c2f5e2fde1.\n\n' + (UPSTREAM / 'LICENSE').read_text(encoding='utf-8') + '\n\nSelf-hosted fonts are under the SIL Open Font License. See frontend/public/assets/fonts/*-OFL.txt.\nThree.js 0.160.0:\n\n' + (ROOT/'vendor/three-LICENSE.txt').read_text(encoding='utf-8'), encoding='utf-8')
print('Created kineticEngine.js from upstream shader, drawing and transition core.')
