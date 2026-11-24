import {githubGuideSteps} from '../githubGuide'

export function GithubGuideTip({step,privateRepo,target,blocker,onBack,onNext,onClose}:{
  step:number;privateRepo:boolean;target:string;blocker:string;onBack:()=>void;onNext:()=>void;onClose:()=>void
}) {
  const steps=githubGuideSteps(privateRepo)
  const item=steps[step]
  if (!item || item.target!==target) return null
  return <aside className="github-guide-tip" aria-label="GitHub 检索引导">
    <div className="github-guide-heading"><span>{step+1} / {steps.length}</span><strong>{item.title}</strong>
      <button type="button" className="text-action" onClick={onClose} aria-label="关闭 GitHub 引导">跳过引导</button></div>
    <p>{blocker || item.description}</p>
    <div className="btn-row">
      {step>0 && target!=='launch' && <button type="button" className="btn secondary" onClick={onBack}>上一步</button>}
      {!blocker && target!=='authorize' && <button type="button" className="btn secondary" onClick={target==='launch'?onClose:onNext}>{target==='launch'?'完成引导':'下一步'}</button>}
    </div>
  </aside>
}
