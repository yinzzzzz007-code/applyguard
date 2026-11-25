export type GuideRequirement = {id:string; label:string; selector?:string; href?:string}
export type GuideRequest = {owner:string; origin:{x:number;y:number}; requirements:GuideRequirement[]}
export const GUIDE_REQUEST='applyguard:guide-request'
export const GUIDE_UPDATE='applyguard:guide-update'
export const GUIDE_COMPLETE='applyguard:guide-complete'
export function requestGuide(owner:string, element:HTMLElement, requirements:GuideRequirement[]) {
  const box=element.getBoundingClientRect()
  window.dispatchEvent(new CustomEvent<GuideRequest>(GUIDE_REQUEST,{detail:{owner,origin:{x:box.x+box.width/2+scrollX,y:box.y+box.height/2+scrollY},requirements}}))
}
export function completeGuideStep(step:string) {if(typeof window!=='undefined')window.dispatchEvent(new CustomEvent(GUIDE_COMPLETE,{detail:step}))}
export function orderRequirements<T extends {id:string}>(items:T[],distance:(item:T)=>number):T[] {
  return [...items].sort((a,b)=>distance(a)-distance(b))
}
export const GUIDE_STEPS=[
  {id:'import',href:'/',selector:'[data-guide="import"]',label:'先选择简历，识别后点击「导入到经历库」。'},
  {id:'vault',href:'/vault',selector:'[data-guide="vault-save"]',label:'核对经历卡片，再点击「保存经历库」。'},
  {id:'evidence',href:'/evidence',selector:'.evidence-workspace',label:'添加证明材料，核对原文后关联到对应经历。'},
  {id:'jd',href:'/jd',selector:'#jd-input',label:'填写目标岗位的职责和要求，再分析岗位。'},
  {id:'match',href:'/match',selector:'[data-guide="match-next"]',label:'检查岗位匹配和缺口，再进入简历审查。'},
  {id:'resume',href:'/resume',selector:'[data-guide="polish"]',label:'先核对按岗位选入的正文，可移除或补选经历；需要时再润色。'},
  {id:'claims',href:'/claims',selector:'#claims-recheck',label:'可用当前材料核验正文，点击正文的蓝色词句看待核对项，红色词句看材料冲突。进入最终确认会保留未排除的陈述。'},
  {id:'confirm',href:'/confirm',selector:'main',label:'核对最终内容；实际投递仍由你本人完成。'},
] as const

export const GUIDE_PAGES = [
  ...GUIDE_STEPS,
  {id:'jobs',href:'/jobs',selector:'.official-job-radar, .radar-page',label:'在岗位雷达刷新官网岗位，查看推荐；点击未读提醒或新增岗位可逐条打开详情。'},
  {id:'history',href:'/history',selector:'#workspace-main h2',label:'在简历生成页选择模板，检查预览和导出内容；之后可继续准备面经。'},
  {id:'interview',href:'/interview',selector:'#interview-jd',label:'核对目标岗位与当前经历，阅读模型使用说明后，自行决定是否生成面经。'},
  {id:'help',href:'/help',selector:'#workspace-main h2',label:'这里说明完整操作流程。选择需要的步骤，即可回到对应功能继续操作。'},
] as const

export type GuideProgress = {dismissed:boolean;completed:string[]}
export function reopenGuide(progress:GuideProgress):GuideProgress {
  return {...progress,dismissed:false}
}

export type GuideContext={hasWorkflow:boolean;hasForm:boolean;formDirty:boolean;claimCount:number;editingIds:string[];historyReplay?:boolean}
export function guideForPage(pathname:string, completedHere?:string, context?:GuideContext) {
  const path=pathname.length>1?pathname.replace(/\/+$/,''):pathname
  const current=GUIDE_PAGES.find(item=>item.href===path)
  if(context?.historyReplay && (current?.id==='resume'||current?.id==='claims'))
    return {...current,selector:'[data-guide="exit-history"]',label:'当前是历史回放，可以查看和编辑当时的结果。点击这里结束回放，保留当前正文并继续正常流程。'}
  if(current?.id==='claims' && context?.editingIds.length && completedHere!=='claims')
    return {...current,selector:`[id=${JSON.stringify('edit-'+context.editingIds[0])}]`,label:'这条陈述还在编辑。在蓝框内选择“保存修改”或“取消编辑”。'}
  if(current?.id==='resume'&&context&&completedHere!=='resume') {
    if(!context.hasWorkflow)return {...current,href:'/jd',selector:'#jd-input',label:'先填写并分析目标岗位，系统才会按岗位从经历库选择相关经历。'}
    if(context.editingIds.length)return {...current,selector:`[data-claim-id=${JSON.stringify(context.editingIds[0])}]`,label:'先保存或取消正在编辑的这一条，再继续润色或核验。'}
    if(!context.claimCount)return context.hasForm
      ?{...current,selector:'[data-guide="draft-pool"]',label:'正文目前为空，请在这里搜索或下拉补选经历；已移除的内容不会自动加回。'}
      :{...current,href:'/vault',selector:'[data-guide="vault-save"]',label:'先在经历库保存项目或实习，之后这里会按岗位自动选入相关经历。'}
    return {...current,selector:'[data-guide="draft-document"]',label:'先核对正文中的经历，不合适的可直接移除；下方可以搜索补选，需要时再润色。'}
  }
  if(!current||completedHere!==current.id)return current
  const index=GUIDE_STEPS.findIndex(item=>item.id===current.id)
  if(index<0)return current
  return GUIDE_STEPS[index+1]??GUIDE_PAGES.find(item=>item.id==='history')
}

export function editingRequirements(drafts:Record<string,string>):GuideRequirement[] {
  return Object.keys(drafts).map(id=>({id:'editing-'+id,label:'先保存或取消这一条正在编辑的句子。',selector:`[data-claim-id=${JSON.stringify(id)}]`}))
}
