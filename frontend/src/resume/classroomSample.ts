import type { TextVersion } from './groundingHistory'

export const CLASSROOM_APPLICATION_ID = 'app_classroom_sample'

export const classroomInitialVersion: TextVersion = {
  id: 'classroom-initial-draft',
  createdAt: '',
  label: '课堂初稿',
  applicationId: CLASSROOM_APPLICATION_ID,
  candidateId: 'cand_demo_ai_fullstack',
  claims: [{
    claim_id: 'claim_demo_a_llm',
    text: '使用 Python 和 PyTorch 搭建轻量 Llama 3 模型的训练流程，完成预训练、SFT、LoRA 微调和 DPO 偏好对齐实验。',
  }],
}

const original = classroomInitialVersion.claims[0].text
const suggestion = '基于 Python 与 PyTorch 构建轻量 Llama 3 训练流程，开展预训练、SFT、LoRA 微调与 DPO 偏好对齐实验。'
const excerpt = 'DPO 偏好对齐实验'
const quote = '模拟材料：尚未开展 DPO 偏好对齐实验。'
const start = original.indexOf(excerpt)
const simulatedResult = {
  state:'NEEDS_REVIEW' as const, original_text:original, final_text:original,
  proposed_text:suggestion, claim_text_sha256:'模拟课堂数据', complete:false,
  relation:'INSUFFICIENT' as const, material_status:'checked', retrieved_sources:[],
  atoms:[{atom_id:'simulated-1',text:'项目完成了 DPO 偏好对齐实验。',
    relation:'CONTRADICTED' as const,reason:'模拟材料明确表示尚未开展该实验。',
    claim_spans:[{start,end:start+excerpt.length,quote:excerpt}],
    citations:[{source_id:'sample-source',evidence_id:'sample-evidence',quote,
      source_sha256:'课堂模拟',start:0,end:quote.length}]}],
}

export const classroomReplayVersions: TextVersion[] = (['polish','verify'] as const).map(operation => ({
  ...classroomInitialVersion,
  id:`classroom-replay-${operation}`,
  label:operation === 'polish' ? '课堂模拟 · 润色回放' : '课堂模拟 · 原子核验回放',
  stateSnapshot:{workflowStatus:'AWAITING_HUMAN_CONFIRMATION',requiresReverification:true,
    claimStates:[{claim_id:'claim_demo_a_llm',state:'NEEDS_REVIEW'}],removedClaims:[],
    proposals:operation === 'polish' ? [{claim_id:'claim_demo_a_llm',text:suggestion,rejected:false}] : [],
    operation,runId:'课堂模拟',historicalResults:{claim_demo_a_llm:
      operation === 'polish' ? simulatedResult : {...simulatedResult,proposed_text:undefined}}},
}))
