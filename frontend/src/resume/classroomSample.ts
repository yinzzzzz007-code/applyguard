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
