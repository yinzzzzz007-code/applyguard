import type {GroundingClaimResult} from '../api/types'

type Atom = GroundingClaimResult['atoms'][number]
type Range = {start:number; end:number}
export type ReviewMark = Range & {kind:'pending'|'conflict'; reason:string; evidence?:string}
type Candidate = Range & {mark:ReviewMark|null}

function uniqueRange(text:string, quote:string): Range[] {
  const start = text.indexOf(quote)
  return quote.trim() && start >= 0 && start === text.lastIndexOf(quote) ? [{start,end:start+quote.length}] : []
}

function anchoredRanges(text:string, atom:Atom): Range[] {
  const spans = atom.claim_spans ?? []
  const excerpt = atom.claim_excerpt?.trim()
  if (!spans.length) return atom.anchor_reason ? [] : uniqueRange(text,excerpt || atom.text.trim())
  const chars = Array.from(text)
  return spans.flatMap(({start,end,quote}) => {
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start || end > chars.length ||
        !quote.trim() || chars.slice(start,end).join('') !== quote) return []
    const offset = chars.slice(0,start).join('').length
    const inside = excerpt ? uniqueRange(quote,excerpt)[0] : undefined
    return inside ? [{start:offset+inside.start,end:offset+inside.end}] : [{start:offset,end:offset+quote.length}]
  })
}

const metrics = /(?:(?:约|近|超过|至少|最多|Top\s*)\s*)?\d+(?:,\d{3})*(?:\.\d+)?\s*(?:\/\s*\d+(?:,\d{3})*|个百分点|[%％]|毫秒|人次|万元|倍|种|项|名|秒|ms\b|fps\b)|第\s*\d+\s*名/gi
const roles = /(?:共同|独立)?(?:第一作者|通讯作者|一作)|(?:项目|技术)负责人|核心成员|(?:已)?(?:录用|投稿|发表)|(?:国家|省|校)级(?:大创|奖项)?|(?:金|银|铜)牌|[一二三]等奖|\b(?:accepted|submitted|(?:Kaggle\s+)?(?:silver|bronze|gold)(?:\s+medal)?)\b/gi

function readingCues(text:string): ReviewMark[] {
  const marks:ReviewMark[] = []
  for (const [pattern,reason] of [[metrics,'请对照原件核对数值、单位和统计口径。'],[roles,'请对照原件核对身份、奖项或发表状态。']] as const) {
    for (const m of text.matchAll(pattern)) marks.push({start:m.index,end:m.index+m[0].length,kind:'pending',reason})
  }
  if (!marks.length) {
    const clauses = [...text.matchAll(/[^，,。；;\n]+/g)].filter(m=>m[0].trim())
    const action = clauses.find(m=>/实现|设计|开发|构建|评测|测量|定位|部署|负责|研究|比较|built|implemented|evaluated/i.test(m[0])) ?? clauses[0]
    if (action) {
      const quote = action[0].trim()
      const start = action.index + action[0].indexOf(quote)
      marks.push({start,end:start+quote.length,kind:'pending',reason:'可从这段经历描述开始，对照原件确认工作内容。'})
    }
  }
  return marks.sort((a,b)=>a.start-b.start)
}

export function reviewMarks(text:string, result:GroundingClaimResult|undefined, current:boolean, needsReview:boolean, fragments:string[]=[]): ReviewMark[] {
  if (!needsReview || !text.trim()) return []
  const modelSplit = result?.atoms.some(atom => atom.method === 'model_split_without_sources')
  if (!current || !result || (result.material_status === 'no_related_material' && !modelSplit) || result.material_status === 'service_error') {
    // A legacy check can supply exact fragments even when it has no atomic report.
    if (current && !result) {
      const exact = fragments.flatMap(f=>uniqueRange(text,f).map(r=>({...r,kind:'pending' as const,reason:'本次检查将这段原文列为待复核。'})))
      if (exact.length) return resolveRanges(exact.map(mark=>({...mark,mark})))
    }
    return readingCues(text)
  }
  const candidates:Candidate[] = []
  for (const atom of result.atoms) {
    const cite = atom.citations.find(c => c.quote?.trim() && c.end > c.start)
    for (const range of anchoredRanges(text,atom)) {
      const supported = atom.relation === 'SUPPORTED' && cite
      const conflict = atom.relation === 'CONTRADICTED' && cite
      candidates.push({...range,mark:supported ? null : {...range,kind:conflict ? 'conflict' : 'pending',
        reason:atom.reason || '请对照材料核对这段原文。', evidence:conflict ? cite.quote : undefined}})
    }
  }
  if (!result.atoms.length) {
    for (const f of fragments) for (const r of uniqueRange(text,f)) {
      candidates.push({...r,mark:{...r,kind:'pending',reason:'这段原文仍待核对。'}})
    }
  }
  return candidates.length || !modelSplit ? resolveRanges(candidates) : readingCues(text)
}

function resolveRanges(candidates:Candidate[]): ReviewMark[] {
  // A narrow fact can refine a broader clause. Preserve any documented conflict.
  const ordered = [...candidates].sort((a,b)=>
    Number(b.mark?.kind==='conflict')-Number(a.mark?.kind==='conflict') ||
    (a.end-a.start)-(b.end-b.start) || Number(a.mark!==null)-Number(b.mark!==null))
  const boundaries = [...new Set(candidates.flatMap(r=>[r.start,r.end]))].sort((a,b)=>a-b)
  const marks:ReviewMark[] = []
  let previous:Candidate|undefined
  for (let i=1;i<boundaries.length;i++) {
    const start=boundaries[i-1], end=boundaries[i]
    const match=ordered.find(c=>c.start<=start && c.end>=end)
    if (match?.mark) {
      if (match===previous) marks[marks.length-1].end=end
      else marks.push({...match.mark,start,end})
    }
    previous=match
  }
  return marks
}
