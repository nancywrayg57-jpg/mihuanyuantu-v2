'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'

type TaskView = {
  id: string
  status: string
  presetCode?: string
  outputObjectKey?: string | null
  creditDisposition?: string | null
  failureClass?: string | null
  detection?: {
    accepted?: boolean
    passed?: boolean
    reason?: string
    total_score?: number
    noise?: number
    depthOfField?: number
    lighting?: number
    colorRealism?: number
    overallRealism?: number
    detector?: string
  } | null
}
type InboxItem = { id: string; title: string; body: string }

const RETRYABLE = new Set([
  'technical',
  'gemini_technical',
  'GEMINI_TECHNICAL',
  'GEMINI_NOT_CONFIGURED',
  'OUTPUT_CONSTRAINT_UNSATISFIED',
  'EXIF_WRITE_FAILED',
])

function canRetry(task: TaskView): boolean {
  return Boolean(task.failureClass && RETRYABLE.has(task.failureClass))
}

function canReprocess(task: TaskView): boolean {
  return Boolean(
    task.outputObjectKey &&
      task.detection &&
      task.detection.detector &&
      task.detection.detector !== 'fixture' &&
      task.detection.accepted === false,
  )
}

function reportText(task: TaskView): string {
  const detection = task.detection
  if (!detection) return '尚无报告'
  return `reason=${detection.reason || ''} noise=${detection.noise} depthOfField=${detection.depthOfField} lighting=${detection.lighting} colorRealism=${detection.colorRealism} overallRealism=${detection.overallRealism} total_score=${detection.total_score} passed=${String(detection.passed)}`
}

export default function RealphotosTasksPage() {
  const [task, setTask] = useState<TaskView | null>(null)
  const [batchId, setBatchId] = useState('')
  const [batchTasks, setBatchTasks] = useState<TaskView[]>([])
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [inbox, setInbox] = useState<InboxItem[]>([])
  const [notice, setNotice] = useState('')
  const [downloadNote, setDownloadNote] = useState('')

  async function loadInbox() {
    const messages = await apiFetch<{ items: InboxItem[] }>('/api/v1/realphotos/inbox')
    setInbox(messages.items || [])
  }

  async function loadSaved() {
    const saved = window.sessionStorage.getItem('realphotos.s1.taskId')
    const savedBatch = window.sessionStorage.getItem('realphotos.s4.batchId')
    if (saved) {
      const data = await apiFetch<TaskView>(`/api/v1/realphotos/processing-tasks/${saved}`)
      setTask(data)
    }
    if (savedBatch) {
      setBatchId(savedBatch)
      const data = await apiFetch<{ tasks: TaskView[] }>(
        `/api/v1/realphotos/processing-batches/${savedBatch}`,
      )
      setBatchTasks(data.tasks || [])
    }
    await loadInbox()
  }

  useEffect(() => {
    void loadSaved().catch((error: unknown) =>
      setNotice(error instanceof ApiError ? error.message : '任务加载失败'),
    )
  }, [])

  const rows = new Map<string, TaskView>()
  if (task) rows.set(task.id, task)
  for (const item of batchTasks) rows.set(item.id, item)
  const tableRows = [...rows.values()]
  const selected = tableRows.filter((item) => checked[item.id])

  async function refreshAll() {
    await loadSaved()
    setNotice('已刷新')
  }

  async function downloadChecked() {
    const ids = selected.filter((item) => item.outputObjectKey).map((item) => Number(item.id))
    if (ids.length < 1) {
      setDownloadNote('没有勾选可下载的结果')
      return
    }
    const listed = await apiFetch<{ items: { taskId: string; objectKey: string; pack: string }[] }>(
      '/api/v1/realphotos/processing-tasks/selected-downloads',
      { method: 'POST', body: JSON.stringify({ taskIds: ids, pack: 'files' }) },
    )
    const notes: string[] = []
    for (const item of listed.items) {
      if (item.pack !== 'file') continue
      const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${item.objectKey}`)
      const bytes = new Uint8Array(await blob.arrayBuffer())
      const jpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
      notes.push(`${item.taskId}:${bytes.length}${jpeg ? '' : ':非JPEG'}`)
    }
    setDownloadNote(notes.length ? `逐张下载 ${notes.join(' ')}` : '勾选的任务还没有可下载结果')
  }

  async function retryTechnical() {
    const targets = selected.filter(canRetry)
    if (targets.length < 1) return
    try {
      for (const current of targets) {
        const data = await apiFetch<TaskView>(`/api/v1/realphotos/processing-tasks/${current.id}/retry`, {
          method: 'POST',
        })
        const refreshed = await apiFetch<TaskView>(`/api/v1/realphotos/processing-tasks/${data.id}`)
        setTask(refreshed)
        window.sessionStorage.setItem('realphotos.s1.taskId', refreshed.id)
      }
      await refreshAll()
      setNotice('技术重试已提交')
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '技术重试失败')
    }
  }

  async function reprocessTask() {
    const targets = selected.filter(canReprocess)
    if (targets.length < 1) return
    try {
      for (const current of targets) {
        const data = await apiFetch<TaskView>(`/api/v1/realphotos/processing-tasks/${current.id}/reprocess`, {
          method: 'POST',
          body: JSON.stringify({
            presetCode: current.presetCode,
            idempotencyKey: `reprocess-${current.id}-${Date.now()}`,
          }),
        })
        setTask(data)
        window.sessionStorage.setItem('realphotos.s1.taskId', data.id)
      }
      setNotice('已建立重处理任务，原任务报告仍保留')
      await refreshAll()
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '主动重处理失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">任务详情</h1>
      <p className="text-sm text-muted-foreground">{notice}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">处理任务{batchId ? ` · 批次 ${batchId}` : ''}</h2>
        <div className="flex flex-wrap gap-3">
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void downloadChecked()}>
            下载勾选
          </button>
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void refreshAll()}>
            刷新
          </button>
          <button
            className="border px-3 py-1 text-sm disabled:opacity-40"
            type="button"
            disabled={!selected.some(canRetry)}
            onClick={() => void retryTechnical()}
          >
            技术重试
          </button>
          <button
            className="border px-3 py-1 text-sm disabled:opacity-40"
            type="button"
            disabled={!selected.some(canReprocess)}
            onClick={() => void reprocessTask()}
          >
            主动重处理
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left">勾选</th>
              <th className="text-left">任务</th>
              <th className="text-left">状态</th>
              <th className="text-left">积分处置</th>
              <th className="text-left">失败</th>
              <th className="text-left">检测报告</th>
            </tr>
          </thead>
          <tbody>
            {tableRows.length === 0 ? (
              <tr>
                <td colSpan={6}>暂无任务</td>
              </tr>
            ) : (
              tableRows.map((item) => (
                <tr key={item.id}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`勾选任务 ${item.id}`}
                      disabled={!item.outputObjectKey}
                      checked={Boolean(checked[item.id])}
                      onChange={(event) =>
                        setChecked((prev) => ({ ...prev, [item.id]: event.target.checked }))
                      }
                    />
                  </td>
                  <td>{item.id}</td>
                  <td>{item.status}</td>
                  <td>{item.creditDisposition || '处理中'}</td>
                  <td>{item.failureClass || ''}</td>
                  <td>{reportText(item)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <p className="text-sm">{downloadNote}</p>
      </section>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">消息</h2>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left">站内消息</th>
              <th className="text-left">内容</th>
            </tr>
          </thead>
          <tbody>
            {inbox.length === 0 ? (
              <tr>
                <td colSpan={2}>暂无消息</td>
              </tr>
            ) : (
              inbox.map((item) => (
                <tr key={item.id}>
                  <td>{item.title}</td>
                  <td>{item.body}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  )
}
