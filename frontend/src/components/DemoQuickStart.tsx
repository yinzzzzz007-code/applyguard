import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import type { DemoScenario, EditableResumeForm } from '../api/types'
import { useDemo } from '../context/DemoContext'
import { getApiClient, loadClassroomDemo } from '../api/client'
import { normalizeResumeForm } from '../resume/formModel'
import { Button } from './ui/button'
import { Card, CardTitle } from './ui/card'

export function DemoQuickStart() {
  const navigate = useNavigate()
  const { setScenario, workflow, resumeForm, setResumeForm, reviewDrafts } = useDemo()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  function start(scenario: DemoScenario) {
    if ((workflow || resumeForm?.dirty || Object.keys(reviewDrafts).length) &&
        !window.confirm('进入预录演示会替换当前工作流并清空未保存编辑。已保存的经历和材料不受影响。继续？')) return
    setScenario(scenario)
    navigate('/jd')
  }
  async function loadTemplateResume() {
    if (loading) return
    setLoading(true)
    setError('')
    try {
      const api = getApiClient()
      const existing = await api.getResumeDraft()
      if (existing.error) throw new Error(existing.error.message)
      if ((workflow || resumeForm?.dirty || existing.data || Object.keys(reviewDrafts).length) &&
          !window.confirm('载入模板会替换当前经历库草稿和未保存的编辑。继续？')) return
      const response = await fetch(`${import.meta.env.BASE_URL}data/resume-template.example.json`)
      if (!response.ok) throw new Error('无法读取模板简历，请重试。')
      const form = normalizeResumeForm(await response.json() as EditableResumeForm)
      const saved = await api.saveResumeDraft(form, existing.data?.savedAt ?? null)
      if (saved.error || !saved.data?.saved) throw new Error(saved.error?.message ?? '模板简历保存失败。')
      setScenario('live', { restoreWorkflow: false })
      setResumeForm({ ...form, savedAt: saved.data.saved_at })
      navigate('/jobs')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '模板简历加载失败，请重试。')
    } finally {
      setLoading(false)
    }
  }
  async function openClassroomDemo() {
    if (loading) return
    if (resumeForm?.dirty || Object.keys(reviewDrafts).length) {
      setError('请先保存当前编辑。')
      return
    }
    setLoading(true)
    setError('')
    try {
      const result = await loadClassroomDemo()
      if (!result.data?.saved) throw new Error(result.error?.message ?? '无法载入课堂示例。')
      setScenario('live')
      navigate('/match')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '无法载入课堂示例。')
    } finally {
      setLoading(false)
    }
  }
  return <Card asChild><section className="demo-quick-start" aria-labelledby="demo-start-title">
    <CardTitle asChild><h3 id="demo-start-title">课堂演示</h3></CardTitle>
    <div className="btn-row">
      <Button disabledReason={'正在处理当前操作，完成后可继续。'} disabled={loading} onClick={() => void openClassroomDemo()}>载入完整示例</Button>
      <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={loading} onClick={() => void loadTemplateResume()}>{loading ? '正在载入模板…' : '载入模板简历并看岗位'}</Button>
      <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={loading} onClick={() => start('prerecorded_block')}>体验错改阻断</Button>
      <Button variant="secondary" disabledReason={'正在处理当前操作，完成后可继续。'} disabled={loading} onClick={() => start('prerecorded_fallback')}>体验超时回退</Button>
    </div>
    {error && <p className="callout warn" role="alert">{error}</p>}
    <small>错改与超时样例仅供演示。</small>
  </section></Card>
}
