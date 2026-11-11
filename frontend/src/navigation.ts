import type { IconName } from './components/Icon'

export const NAV_GROUPS: Array<{label: string; items: Array<{path: string; label: string; icon: IconName}>}> = [
  {label:'我的资料',items:[{path:'/',label:'简历导入',icon:'upload'},{path:'/vault',label:'经历库',icon:'folder'},{path:'/evidence',label:'证明材料',icon:'library'}]},
  {label:'目标岗位',items:[{path:'/jobs',label:'岗位雷达',icon:'compass'},{path:'/jd',label:'岗位说明',icon:'briefcase'}]},
  {label:'审核草稿',items:[{path:'/match',label:'证据匹配',icon:'layers'},{path:'/resume',label:'简历审查',icon:'file'},{path:'/claims',label:'陈述核验',icon:'shield'}]},
  {label:'导出与记录',items:[{path:'/ats',label:'申请内容检查',icon:'window'},{path:'/confirm',label:'最终确认',icon:'check'},{path:'/history',label:'简历生成',icon:'history'}]},
]
