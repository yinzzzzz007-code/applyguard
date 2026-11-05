/* Derived from kinetic-reel by tuzhechen2005, MIT, commit 59744a69c7b916cfbe4c4ec84006b0c2f5e2fde1.
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
// ---------- math ----------
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const ease = x => { x = clamp(x); return x * x * (3 - 2 * x); };
const easeIn = x => Math.pow(clamp(x), 3);
const expoOut = x => { x = clamp(x); return x === 1 ? 1 : 1 - Math.pow(2, -10 * x); };
const beatPulse = (t, k = 7) => Math.exp(-((t / BEAT) % 1) * k);
const TAU = Math.PI * 2;

// ---------- canvases ----------

const c2 = document.createElement('canvas'); c2.width = W; c2.height = H;
let ctx = c2.getContext('2d');   // swapped to an offscreen buffer while a transition renders its two scenes
const mainCtx = ctx;
const mkBuf = () => { const c = document.createElement('canvas'); c.width = W; c.height = H; return c; };
const bufA = mkBuf(), bufB = mkBuf(), bufT = mkBuf();   // outgoing scene · incoming scene · text-mask scratch
const RECT = {};                                         // rects scenes register for zoom-through transitions
const glA = document.createElement('canvas'); glA.width = W; glA.height = H;
const RA = new THREE.WebGLRenderer({ canvas: glA, antialias: true, alpha: true, preserveDrawingBuffer: true });
RA.setPixelRatio(1); RA.setSize(Math.round(W * .67), Math.round(H * .67), false);
const RP = new THREE.WebGLRenderer({ canvas: out, antialias: false, preserveDrawingBuffer: true });
RP.setPixelRatio(1); RP.setSize(Math.round(W * .83), Math.round(H * .83), false); RP.outputColorSpace = THREE.LinearSRGBColorSpace;

// ---------- GL layer 1: particle terrain ----------
const terrain = (() => {
  const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(42, W / H, .1, 100);
  const nx = 128, nz = 80, pos = new Float32Array(nx * nz * 3);
  for (let i = 0; i < nx; i++) for (let j = 0; j < nz; j++) { const k = (i * nz + j) * 3; pos[k] = (i / (nx - 1) - .5) * 26; pos[k + 1] = 0; pos[k + 2] = -j / (nz - 1) * 30 + 3; }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    uniforms: { time: { value: 0 }, amp: { value: 1 }, fade: { value: 1 }, tint: { value: new THREE.Color(K.cream) } },
    vertexShader: `uniform float time, amp; varying float vA;
      float wave(vec2 p, float t){ return sin(p.x*.5+t*.9)*.45 + sin(p.y*.38-t*.7)*.6 + sin((p.x+p.y)*.27+t*.5)*.7 + sin(length(p-vec2(3.,-9.))*.8-t*1.4)*.4; }
      void main(){ vec3 p = position; p.y = wave(p.xz, time)*amp; vec4 mv = modelViewMatrix*vec4(p,1.);
        gl_PointSize = 5.5 * (6.0 / -mv.z); float d = -mv.z; vA = clamp(1.0 - d/30.0, 0., 1.) * (.25 + .75*smoothstep(-1.2, 1.6, p.y)) * smoothstep(0.5, 3.5, d);
        gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `uniform float fade; uniform vec3 tint; varying float vA;
      void main(){ vec2 c = gl_PointCoord-.5; float r = dot(c,c); if (r>.25) discard; gl_FragColor = vec4(tint, vA*fade*(1.0-r*2.5)); }`,
  });
  scene.add(new THREE.Points(g, mat));
  return (t, o = {}) => {
    mat.uniforms.time.value = t; mat.uniforms.amp.value = o.amp ?? 1; mat.uniforms.fade.value = o.fade ?? 1;
    cam.position.set(Math.sin(t * .15) * 1.5, o.camY ?? 3.2, 5 - (o.push ?? 0)); cam.lookAt(0, -.4, -8); cam.rotation.z += o.roll ?? 0;
    RA.setClearColor(0x000000, 0); RA.clear(); RA.render(scene, cam);
    return glA;
  };
})();

// ---------- GL layer 2: liquid marble (domain-warped fbm, banded) ----------
const liquid = (() => {
  const scene = new THREE.Scene(), cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const mat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, res: { value: new THREE.Vector2(W, H) }, strips: { value: 0 }, stripAmt: { value: 0 }, zoom: { value: 1.6 }, seed: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }`,
    fragmentShader: `uniform float time, strips, stripAmt, zoom, seed; uniform vec2 res; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      float n(vec2 p){ vec2 i=floor(p), f=fract(p); f=f*f*(3.-2.*f); return mix(mix(h(i),h(i+vec2(1,0)),f.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x), f.y); }
      float fbm(vec2 p){ float s=0., a=.5; for(int i=0;i<5;i++){ s+=a*n(p); p=p*2.03+vec2(1.7,9.2); a*=.5; } return s; }
      void main(){
        vec2 uv = vUv; vec2 p = (uv-.5)*vec2(res.x/res.y,1.)*zoom + seed;
        if (strips > 0.) { float s = floor(uv.x*strips); p.y += (h(vec2(s,3.))-.5)*stripAmt; p.x += (h(vec2(s,7.))-.5)*stripAmt*.25; }
        vec2 q = vec2(fbm(p + time*.06), fbm(p + vec2(5.2,1.3) - time*.05));
        vec2 r = vec2(fbm(p + 3.6*q + vec2(1.7,9.2) + time*.13), fbm(p + 3.6*q + vec2(8.3,2.8) - time*.11));
        float f = fbm(p + 3.8*r);
        float band = sin(f*22.0 + r.x*7.0)*.5+.5;
        vec3 blue = vec3(.145,.388,.922), red = vec3(.577,.20,.918), lil = vec3(.80,.75,.98), navy = vec3(.09,.13,.22), cream = vec3(.97,.98,.99);
        vec3 col = mix(blue, red, smoothstep(.38,.62,f));
        col = mix(col, lil, smoothstep(.62,.95,band)*.55);
        col = mix(col, navy, smoothstep(.55,.95,1.0-f)*.75);
        col = mix(col, cream, smoothstep(.93,1.,band)*smoothstep(.45,.7,f)*.5);
        gl_FragColor = vec4(col,1.);
      }`,
  });
  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat));
  return (t, o = {}) => {
    const u = mat.uniforms; u.time.value = t; u.strips.value = o.strips || 0; u.stripAmt.value = o.stripAmt || 0; u.zoom.value = o.zoom ?? 1.6; u.seed.value = o.seed || 0;
    RA.setClearColor(0x000000, 1); RA.clear(); RA.render(scene, cam);
    return glA;
  };
})();

// ---------- post pass ----------
const post = (() => {
  const tex = new THREE.CanvasTexture(c2); tex.colorSpace = THREE.NoColorSpace; tex.minFilter = tex.magFilter = THREE.LinearFilter;
  const mat = new THREE.ShaderMaterial({
    uniforms: { tex: { value: tex }, split: { value: 0 }, slice: { value: 0 }, seed: { value: 0 }, grain: { value: .05 }, time: { value: 0 }, vign: { value: .5 }, flash: { value: 0 }, flashCol: { value: new THREE.Color(1, 1, 1) }, res: { value: new THREE.Vector2(W, H) } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }`,
    fragmentShader: `uniform sampler2D tex; uniform float split, slice, seed, grain, time, vign, flash; uniform vec3 flashCol; uniform vec2 res; varying vec2 vUv;
      float h(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7)))*43758.5453); }
      void main(){
        vec2 uv = vUv;
        float band = floor(uv.y*28.0 + h(vec2(seed,1.))*3.0), hb = h(vec2(band, seed));
        if (hb < slice) uv.x += (h(vec2(band, seed+2.)) - .5) * .16 * slice;
        vec2 d = vec2(split, split*.15);
        vec3 c = vec3(texture2D(tex, uv + d).r, texture2D(tex, uv).g, texture2D(tex, uv - d).b);
        c += (h(vUv*res + time*61.7) - .5) * grain;
        vec2 q = vUv - .5; c *= 1.0 - vign*dot(q,q)*.9;
        c = mix(c, flashCol, flash);
        gl_FragColor = vec4(c, 1.);
      }`,
  });
  const scene = new THREE.Scene(), cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat));
  return (t, fx) => {
    tex.needsUpdate = true;
    const u = mat.uniforms; u.split.value = fx.split; u.slice.value = fx.slice; u.seed.value = fx.seed; u.time.value = Math.floor(t * FPS);
    u.grain.value = fx.grain; u.vign.value = fx.vign; u.flash.value = fx.flash; u.flashCol.value.set(fx.flashCol);
    RP.render(scene, cam);
  };
})();

// ---------- 2D helpers ----------
let FX;
const font = (fam, size, weight = '') => `${weight} ${size}px ${fam}`.trim();
function txt(s, x, y, o = {}) {
  ctx.save();
  ctx.font = o.font; ctx.textAlign = o.align || 'left'; ctx.textBaseline = o.base || 'alphabetic'; ctx.letterSpacing = (o.ls || 0) + 'px';
  ctx.globalAlpha = o.a ?? 1;
  if (o.glow) { ctx.shadowColor = o.glow; ctx.shadowBlur = o.glowR || 28; }
  if (o.stroke) { ctx.lineWidth = o.lw || 2; ctx.strokeStyle = o.stroke; ctx.strokeText(s, x, y); }
  if (o.fill !== null) { ctx.fillStyle = o.fill || K.cream; ctx.fillText(s, x, y); }
  ctx.restore();
}
// per-letter animation: fn(i, n) → { dx, dy, r, s, a }
function letters(s, x, y, o, fn) {
  ctx.save(); ctx.font = o.font; ctx.letterSpacing = (o.ls || 0) + 'px';
  const total = ctx.measureText(s).width, x0 = o.align === 'center' ? x - total / 2 : o.align === 'right' ? x - total : x;
  const glyphs = Array.from(s); const n = glyphs.length;
  for (let i = 0; i < n; i++) {
    const ch = glyphs[i]; if (ch === ' ') continue;
    const px = ctx.measureText(glyphs.slice(0, i).join('')).width, cw = ctx.measureText(ch).width, a = fn(i, n);
    if ((a.a ?? 1) <= 0.001) continue;
    ctx.save(); ctx.globalAlpha = a.a ?? 1; ctx.translate(x0 + px + cw / 2 + (a.dx || 0), y + (a.dy || 0)); ctx.rotate(a.r || 0); ctx.scale(a.s ?? 1, a.s ?? 1);
    ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
    if (o.stroke) { ctx.lineWidth = o.lw || 2; ctx.strokeStyle = o.stroke; ctx.strokeText(ch, 0, 0); }
    if (o.fill !== null) { ctx.fillStyle = a.fill || o.fill || K.cream; ctx.fillText(ch, 0, 0); }
    ctx.restore();
  }
  ctx.restore();
  return total;
}
const measure = (s, f, ls = 0) => { ctx.save(); ctx.font = f; ctx.letterSpacing = ls + 'px'; const w = ctx.measureText(s).width; ctx.restore(); return w; };
const bg = col => { ctx.fillStyle = col; ctx.fillRect(0, 0, W, H); };
function line(pts, col, lw = 2, a = 1) { ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.stroke(); ctx.restore(); }
function circle(x, y, r, o = {}) { if (!(r > .01)) return; ctx.save(); ctx.globalAlpha = o.a ?? 1; ctx.beginPath(); ctx.arc(x, y, r, o.a0 ?? 0, o.a1 ?? TAU); if (o.fill) { ctx.fillStyle = o.fill; ctx.fill(); } if (o.stroke) { ctx.strokeStyle = o.stroke; ctx.lineWidth = o.lw || 2; ctx.stroke(); } ctx.restore(); }
// HUD: corner brackets + micro-type in the four corners + a progress rule
function hud(t, o) {
  const dark = o.dark !== false, col = dark ? 'rgba(241,238,230,.85)' : 'rgba(14,15,14,.85)', dim = dark ? 'rgba(241,238,230,.45)' : 'rgba(14,15,14,.45)';
  const k = o.k ?? 1, m = 40, L = 26 * k;
  if (o.brackets !== false) for (const [cx, cy, sx, sy] of [[m, m, 1, 1], [W - m, m, -1, 1], [m, H - m, 1, -1], [W - m, H - m, -1, -1]]) line([[cx, cy + sy * L], [cx, cy], [cx + sx * L, cy]], col, 2, k);
  const f = font(F.mono, 17, 500), a = clamp(k * 1.4 - .3);
  if (o.tl) txt(o.tl, m + 18, m + 30, { font: f, fill: col, ls: 2.5, a });
  if (o.tr) txt(o.tr, W - m - 18, m + 30, { font: f, fill: col, ls: 2.5, align: 'right', a });
  if (o.bl) txt(o.bl, m + 18, H - m - 18, { font: f, fill: col, ls: 2.5, a });
  if (o.br) txt(o.br, W - m - 18, H - m - 18, { font: f, fill: col, ls: 2.5, align: 'right', a });
  if (o.zh) txt(o.zh, o.zhRight ? W - m - 18 : m + 18, H - m - 52, { font: font(F.zh, 21, 500), fill: dim, ls: 3, align: o.zhRight ? 'right' : 'left', a });
  if (o.progress !== false) {   // the reel as a trace: one segment per chapter, filled as it plays
    const y = H - m + 10, x0 = m + 18, x1 = W - m - 18, X = s => lerp(x0, x1, s / C.dur);
    for (const [, a0, a1] of C.CH) {
      const xa = X(a0) + 3, xb = X(a1) - 3, on = t >= a0 && t < a1;
      line([[xa, y], [xb, y]], dim, 1, a * .6);
      if (t > a0) line([[xa, y], [Math.min(xb, X(t)), y]], col, on ? 3 : 2, a);
    }
  }
}
const tc = t => { const f = Math.floor(t * FPS), s = Math.floor(f / FPS), fr = f % FPS, p = n => String(n).padStart(2, '0'); return `TC 00:00:${p(s)}:${p(fr)}`; };
const glShot = (canvas, a = 1) => { ctx.save(); ctx.globalAlpha = a; ctx.drawImage(canvas, 0, 0, W, H); ctx.restore(); };

// ---------- v2 helpers ----------
function rrect(x, y, w, h, r, o = {}) { if (!(w > .5) || !(h > .5)) return; ctx.save(); ctx.globalAlpha = o.a ?? 1; ctx.beginPath(); ctx.roundRect(x, y, w, h, Math.min(r, w / 2, h / 2)); if (o.fill) { ctx.fillStyle = o.fill; ctx.fill(); } if (o.stroke) { ctx.strokeStyle = o.stroke; ctx.lineWidth = o.lw || 2; ctx.stroke(); } ctx.restore(); }
function arrow(x0, y0, x1, y1, col, lw = 2, a = 1, head = 13) {
  if (a <= 0) return;
  line([[x0, y0], [x1, y1]], col, lw, a); const g = Math.atan2(y1 - y0, x1 - x0);
  line([[x1 - Math.cos(g - .45) * head, y1 - Math.sin(g - .45) * head], [x1, y1], [x1 - Math.cos(g + .45) * head, y1 - Math.sin(g + .45) * head]], col, lw, a);
}
// drop-in word: letters fall from above with overshoot
const dropWord = (s, x, y, f, t0, t, o = {}) => letters(s, x, y, { font: f, fill: o.fill || K.cream, align: o.align }, (i) => {
  const k = seg(t, t0 + i * (o.stag ?? .03), t0 + i * (o.stag ?? .03) + (o.dur ?? .32)); return { dy: (1 - expoOut(k)) * (o.fall ?? 220), a: k > 0 ? 1 : 0, fill: o.fillAt ? o.fillAt(i) : undefined };
});
// ---------- v3 helpers ----------
// Letters as windows onto a shader: draw() into a scratch buffer, keep only `src` inside what was drawn.
function texWindow(draw, src) {
  const saved = ctx, g = bufT.getContext('2d');
  g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1; g.clearRect(0, 0, W, H);
  ctx = g; draw(); ctx = saved;
  g.globalCompositeOperation = 'source-in'; g.drawImage(src, 0, 0, W, H); g.globalCompositeOperation = 'source-over';
  ctx.drawImage(bufT, 0, 0);
}
const bez = (p0, c0, c1, p1, u) => { const v = 1 - u; return [v * v * v * p0[0] + 3 * v * v * u * c0[0] + 3 * v * u * u * c1[0] + u * u * u * p1[0], v * v * v * p0[1] + 3 * v * v * u * c0[1] + 3 * v * u * u * c1[1] + u * u * u * p1[1]]; };
function thread(p0, p1, k, col, lw = 2.5) {   // a cubic "citation thread", drawn up to k
  if (k <= 0) return; const c0 = [p0[0] + 160, p0[1]], c1 = [p1[0] - 160, p1[1]], pts = [];
  for (let i = 0; i <= 40 * k; i++) pts.push(bez(p0, c0, c1, p1, i / 40));
  if (pts.length > 1) line(pts, col, lw);
}

// ---------- transitions (into a scene; A = outgoing scene frozen on its last frame, B = incoming, live) ----------
const easeInOut = x => { x = clamp(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
const ioExpo = x => { x = clamp(x); return x === 0 ? 0 : x === 1 ? 1 : x < .5 ? Math.pow(2, 20 * x - 10) / 2 : (2 - Math.pow(2, -20 * x + 10)) / 2; };
const trIris = (cx, cy, ring = K.lime) => (k, A, B, g) => {
  const e = easeIn(k) * .6 + ease(k) * .4, R = e * Math.hypot(W, H);
  g.drawImage(A, 0, 0); g.save(); g.beginPath(); g.arc(cx, cy, R, 0, TAU); g.clip(); g.drawImage(B, 0, 0); g.restore();
  g.save(); g.strokeStyle = ring; g.lineWidth = 2 + 10 * (1 - e); g.beginPath(); g.arc(cx, cy, R, 0, TAU); g.stroke(); g.restore();
};
const trPush = (dx, dy) => (k, A, B, g) => { const e = ioExpo(k); g.drawImage(A, -dx * W * e, -dy * H * e); g.drawImage(B, dx * W * (1 - e), dy * H * (1 - e)); FX.split = Math.max(FX.split, .012 * Math.sin(Math.PI * e)); };
const trWipe = (col = K.lime) => (k, A, B, g) => { const x = easeInOut(k) * (W + 40); g.drawImage(A, 0, 0); g.save(); g.beginPath(); g.rect(0, 0, x, H); g.clip(); g.drawImage(B, 0, 0); g.restore(); g.fillStyle = col; g.fillRect(x - 4, 0, 8, H); };
const trSlats = (n = 12) => (k, A, B, g) => { g.drawImage(A, 0, 0); const sw = W / n; for (let i = 0; i < n; i++) { const kk = easeInOut(seg(k, i * .035, i * .035 + .6)); if (kk <= 0) continue; g.save(); g.beginPath(); g.rect(i * sw, 0, sw * kk + 1, H); g.clip(); g.drawImage(B, 0, 0); g.restore(); } };

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
