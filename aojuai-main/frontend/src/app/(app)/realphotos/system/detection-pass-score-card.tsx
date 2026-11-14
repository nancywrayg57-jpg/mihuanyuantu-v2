'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type PassScoreView = {
  passScore: number
  defaultPassScore: number
  writable: boolean
  promptLine: string
}

/** Admin card for the Gemini detection pass line. Kept out of system-client so model-key edits stay separate. */
export function DetectionPassScoreCard() {
  const [view, setView] = useState<PassScoreView | null>(null)
  const [draft, setDraft] = useState('75')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void apiFetch<PassScoreView>('/api/v1/realphotos/detection-pass-score')
      .then((data) => {
        setView(data)
        setDraft(String(data.passScore))
      })
      .catch((error: unknown) => {
        setMessage(error instanceof ApiError ? error.message : '及格线读取失败')
      })
  }, [])

  async function save() {
    if (!view?.writable) {
      setMessage('只有平台管理员可以修改检测及格线')
      return
    }
    const next = Number(draft)
    if (!Number.isInteger(next) || next < 0 || next > 100) {
      setMessage('检测及格线须为 0 到 100 的整数')
      return
    }
    setSaving(true)
    try {
      const data = await apiFetch<PassScoreView>('/api/v1/realphotos/detection-pass-score', {
        method: 'PUT',
        body: JSON.stringify({ passScore: next }),
      })
      setView(data)
      setDraft(String(data.passScore))
      setMessage('检测及格线已保存，只影响之后的新检测')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const writable = Boolean(view?.writable)
  const shown = view ? view.passScore : null

  return (
    <section className="rp-card rounded-xl bg-card shadow-sm space-y-3 border p-3 text-sm" data-detection-pass-score>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-medium">检测基线</h2>
        <span className="text-muted-foreground">平台范围</span>
      </div>
      <p className="text-muted-foreground">
        通过标准为总分 ≥ {shown ?? '…'} 且模型 passed=true。代码默认 {view?.defaultPassScore ?? 75}。
        新检测任务使用保存后的及格线；已出报告保留当时的通过线。
      </p>
      {view?.promptLine ? <p className="text-muted-foreground">{view.promptLine}</p> : null}
      {view && !writable ? <p>仅平台管理员可修改。</p> : null}
      <label className="block">
        及格线
        <input
          className="ml-2 w-20 border px-1"
          type="number"
          min={0}
          max={100}
          step={1}
          value={draft}
          disabled={!writable}
          onChange={(event) => setDraft(event.target.value)}
        />
      </label>
      {writable ? (
        <button
          className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 disabled:opacity-50"
          type="button"
          disabled={saving || !view}
          onClick={() => void save()}
        >
          保存及格线
        </button>
      ) : null}
      {message ? <p>{message}</p> : null}
    </section>
  )
}
