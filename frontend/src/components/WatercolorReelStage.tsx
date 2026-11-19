import type { CSSProperties } from 'react'
import type { OnboardingStep } from '../motion/onboarding'
import type { reelFrame } from '../motion/reel'
import { Icon } from './Icon'

interface WatercolorReelStageProps {
  frame: ReturnType<typeof reelFrame>
  step: OnboardingStep
  still: boolean
}

export function WatercolorReelStage({ frame, step, still }: WatercolorReelStageProps) {
  const chapter = frame.phase === 'project'
  const opening = frame.phase === 'open'
  const title = chapter ? step.title : opening ? 'Apply with care.' : '先核对，再申请。'
  const caption = chapter ? step.excerpt : opening ? '用自己的材料，准备一份申请。' : '核对事实，并保留可恢复的草稿版本。'
  const style = { '--wash-reveal': still ? 1 : Math.min(1, frame.local / .7) } as CSSProperties

  return <div className="watercolor-reel-sheet" data-reel-scene={chapter ? step.id : frame.phase} style={style} aria-hidden="true">
    <div>
      <p className="watercolor-reel-label">{chapter ? `第 ${frame.index + 1} 步` : 'ApplyGuard'}</p>
      <strong className="watercolor-reel-title">{title}</strong>
      <p className="watercolor-reel-caption">{caption}</p>
    </div>
    {chapter ? <ol className="watercolor-reel-checklist">
      {step.terms.map(term => <li key={term}><Icon name="check" />{term}</li>)}
    </ol> : <div className="watercolor-reel-illustration">
      <Icon name={opening ? 'file' : 'shield'} />
    </div>}
  </div>
}
