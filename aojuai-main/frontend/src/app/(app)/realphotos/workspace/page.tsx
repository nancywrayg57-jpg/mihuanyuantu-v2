'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import { inspectLocalFile } from '@/lib/realphotos-s1'

type Preset = { code: string; model: string; deviceType: string }
type TaskView = {
  id: string
  status: string
  pipelineVersion?: string
  presetCode?: string
  presetSnapshot?: Record<string, string>
  outputObjectKey?: string | null
  creditDisposition?: string | null
  detection?: {
    accepted?: boolean
    passed?: boolean
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

export default function RealphotosWorkspacePage() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [presetCode, setPresetCode] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [notice, setNotice] = useState('')
  const [assetId, setAssetId] = useState('')
  const [task, setTask] = useState<TaskView | null>(null)
  const [inbox, setInbox] = useState<InboxItem[]>([])
  const [downloadNote, setDownloadNote] = useState('')
  const [redoEnabled, setRedoEnabled] = useState(false)
  const [redoThreshold, setRedoThreshold] = useState(70)
  const [redoRounds, setRedoRounds] = useState(1)

  useEffect(() => {
    const saved = window.sessionStorage.getItem('realphotos.s1.taskId')
    if (saved) {
      void apiFetch<TaskView>(`/api/v1/realphotos/processing-tasks/${saved}`)
        .then((data) => setTask(data))
        .catch(() => undefined)
    }
    void apiFetch<{ enabled: boolean; scoreThreshold: number; extraRounds: number }>(
      '/api/v1/realphotos/redo-settings',
    )
      .then((data) => {
        setRedoEnabled(Boolean(data.enabled))
        setRedoThreshold(Number(data.scoreThreshold))
        setRedoRounds(Number(data.extraRounds))
      })
      .catch(() => undefined)
    void apiFetch<{ items: Preset[] }>('/api/v1/realphotos/presets')
      .then((data) => {
        setPresets(data.items || [])
        setPresetCode((data.items || [])[0]?.code || '')
      })
      .catch((error: unknown) => setNotice(error instanceof ApiError ? error.message : '预设加载失败'))
  }, [])

  async function onFile(next: File | null) {
    setFile(null)
    setAssetId('')
    setDownloadNote('')
    if (!next) return
    const inspected = await inspectLocalFile(next)
    if (!inspected.ok) {
      setNotice(`前端拒绝：${inspected.message}。未上传，不会建立资产。`)
      return
    }
    setFile(next)
    setNotice(`前端通过：${inspected.width}×${inspected.height} ${inspected.kind}`)
  }

  async function upload() {
    if (!file) {
      setNotice('请先选择通过校验的图片')
      return
    }
    const body = new FormData()
    body.set('file', file)
    try {
      const data = await apiFetch<{ id: string }>('/api/v1/realphotos/assets', { method: 'POST', body })
      setAssetId(data.id)
      setNotice(`已建立资产 ${data.id}`)
    } catch (error: unknown) {
      setAssetId('')
      setNotice(error instanceof ApiError ? `后端拒绝：${error.message}` : '上传失败')
    }
  }

  async function submitTask() {
    if (!assetId || !presetCode) {
      setNotice('需要资产和预设')
      return
    }
    const data = await apiFetch<TaskView>('/api/v1/realphotos/processing-tasks', {
      method: 'POST',
      body: JSON.stringify({
        assetId,
        presetCode,
        idempotencyKey: `ui-${assetId}-${Date.now()}`,
      }),
    })
    setTask(data)
    window.sessionStorage.setItem('realphotos.s1.taskId', data.id)
    setNotice(`请求已返回，状态 ${data.status}。可以离开本页，worker 会继续执行。`)
  }

  async function refreshTask() {
    if (!task) return
    const data = await apiFetch<TaskView>(`/api/v1/realphotos/processing-tasks/${task.id}`)
    setTask(data)
    window.sessionStorage.setItem('realphotos.s1.taskId', data.id)
    const messages = await apiFetch<{ items: InboxItem[] }>('/api/v1/realphotos/inbox')
    setInbox(messages.items || [])
  }

  async function download() {
    if (!task?.outputObjectKey) return
    const blob = await apiFetchBlob(
      `/api/v1/realphotos/gateway/objects/${task.outputObjectKey}`,
    )
    const bytes = new Uint8Array(await blob.arrayBuffer())
    const jpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
    setDownloadNote(jpeg ? `下载 ${bytes.length} 字节，JPEG 头通过` : '下载内容不是 JPEG')
  }

  async function removeAsset() {
    if (!assetId) return
    try {
      await apiFetch(`/api/v1/realphotos/assets/${assetId}`, { method: 'DELETE' })
      setNotice('资产已软删')
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '删除失败')
    }
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">蜜獾原图 · 单张处理</h1>
      <form
        className="flex flex-wrap items-end gap-3 text-sm"
        onSubmit={(event) => {
          event.preventDefault()
          void apiFetch('/api/v1/realphotos/redo-settings', {
            method: 'PUT',
            body: JSON.stringify({
              enabled: redoEnabled,
              scoreThreshold: redoThreshold,
              extraRounds: redoRounds,
            }),
          })
            .then(() => setNotice('自动重做设置已保存，只影响之后提交的任务'))
            .catch((error: unknown) => setNotice(error instanceof ApiError ? error.message : '设置保存失败'))
        }}
      >
        <label>
          <input
            type="checkbox"
            checked={redoEnabled}
            onChange={(event) => setRedoEnabled(event.target.checked)}
          />{' '}
          自动重做
        </label>
        <label>
          阈值
          <input
            className="ml-1 w-16 border px-1"
            type="number"
            min={0}
            max={100}
            value={redoThreshold}
            onChange={(event) => setRedoThreshold(Number(event.target.value))}
          />
        </label>
        <label>
          追加次数
          <input
            className="ml-1 w-16 border px-1"
            type="number"
            min={1}
            max={5}
            value={redoRounds}
            onChange={(event) => setRedoRounds(Number(event.target.value))}
          />
        </label>
        <button className="border px-3 py-1" type="submit">
          保存设置
        </button>
      </form>
      <p className="text-sm text-muted-foreground">{notice}</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          本地图片
          <input
            className="mt-1 block text-sm"
            type="file"
            accept="image/jpeg,image/png,.jpg,.jpeg,.png"
            onChange={(event) => void onFile(event.target.files?.[0] || null)}
          />
        </label>
        <label className="text-sm">
          预设
          <select
            className="mt-1 block border px-2 py-1 text-sm"
            value={presetCode}
            onChange={(event) => setPresetCode(event.target.value)}
          >
            {presets.map((item) => (
              <option key={item.code} value={item.code}>
                {item.model}（{item.code}）
              </option>
            ))}
          </select>
        </label>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void upload()}>
          上传
        </button>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void submitTask()}>
          提交单张
        </button>
        <a className="border px-3 py-1 text-sm" href="/realphotos/wallet">
          离开本页
        </a>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void refreshTask()}>
          刷新任务
        </button>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void download()}>
          下载结果
        </button>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void removeAsset()}>
          删除资产
        </button>
      </div>
      <p className="text-sm">启用预设 {presets.length} 个（上限 3）</p>
      {task ? (
        <table className="w-full text-sm">
          <tbody>
            <tr>
              <th className="text-left">任务</th>
              <td>{task.id}</td>
            </tr>
            <tr>
              <th className="text-left">流水线</th>
              <td>{task.pipelineVersion || ''}</td>
            </tr>
            <tr>
              <th className="text-left">预设快照</th>
              <td>{task.presetSnapshot?.model || task.presetCode}</td>
            </tr>
            <tr>
              <th className="text-left">积分处置</th>
              <td>{task.creditDisposition || '处理中'}</td>
            </tr>
            <tr>
              <th className="text-left">检测报告</th>
              <td>
                {task.detection
                  ? `detector=${task.detection.detector || ''} total_score=${task.detection.total_score} passed=${String(task.detection.passed)} accepted=${String(task.detection.accepted)} noise=${task.detection.noise} depthOfField=${task.detection.depthOfField} lighting=${task.detection.lighting} colorRealism=${task.detection.colorRealism} overallRealism=${task.detection.overallRealism}`
                  : '尚无报告'}
              </td>
            </tr>
          </tbody>
        </table>
      ) : null}
      <p className="text-sm">{downloadNote}</p>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">站内消息</th>
            <th className="text-left">内容</th>
          </tr>
        </thead>
        <tbody>
          {inbox.map((item) => (
            <tr key={item.id}>
              <td>{item.title}</td>
              <td>{item.body}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}
