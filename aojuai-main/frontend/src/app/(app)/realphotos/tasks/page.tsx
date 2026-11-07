'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'

import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'

type Detection = {
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
}

type ProcessingTask = {
  id: string
  status: string
  presetCode?: string
  outputObjectKey?: string | null
  creditDisposition?: string | null
  failureClass?: string | null
  createdAt?: string | null
  detection?: Detection | null
  copiedFrom?: string | null
  billingMode?: string | null
  gpsWrite?: {
    written?: boolean
    reason?: string
    actualGps?: { latitude?: number; longitude?: number; altitude?: number } | null
  } | null
}

type GenerationItem = {
  index: number
  status: string
  assetId: string | null
  creditsConsumed: number
}

type GenerationTask = {
  id: string
  mode: string
  provider: string
  quantity: number
  width: number
  height: number
  positivePrompt: string
  negativePrompt: string
  createdAt?: string | null
  items: GenerationItem[]
}

const PAGE_SIZE = 10

const RETRYABLE = new Set([
  'technical',
  'gemini_technical',
  'GEMINI_TECHNICAL',
  'GEMINI_NOT_CONFIGURED',
  'OUTPUT_CONSTRAINT_UNSATISFIED',
  'EXIF_WRITE_FAILED',
])

function canRetry(task: ProcessingTask): boolean {
  return Boolean(task.failureClass && RETRYABLE.has(task.failureClass))
}

function canReprocess(task: ProcessingTask): boolean {
  return Boolean(
    task.outputObjectKey &&
      task.detection &&
      task.detection.detector &&
      task.detection.detector !== 'fixture' &&
      task.detection.accepted === false,
  )
}

function reportText(task: ProcessingTask): string {
  const detection = task.detection
  if (!detection) return '尚无报告'
  return `reason=${detection.reason || ''} noise=${detection.noise} depthOfField=${detection.depthOfField} lighting=${detection.lighting} colorRealism=${detection.colorRealism} overallRealism=${detection.overallRealism} total_score=${detection.total_score} passed=${String(detection.passed)}`
}

export default function RealphotosTasksPage() {
  const [tab, setTab] = useState<'processing' | 'generation'>('processing')
  const [procPage, setProcPage] = useState(1)
  const [procStatus, setProcStatus] = useState('all')
  const [procTotal, setProcTotal] = useState(0)
  const [procItems, setProcItems] = useState<ProcessingTask[]>([])
  const [genPage, setGenPage] = useState(1)
  const [genMode, setGenMode] = useState('all')
  const [genTotal, setGenTotal] = useState(0)
  const [genItems, setGenItems] = useState<GenerationTask[]>([])
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [detail, setDetail] = useState<ProcessingTask | null>(null)
  const [genDetail, setGenDetail] = useState<GenerationTask | null>(null)
  const [notice, setNotice] = useState('')
  const [downloadNote, setDownloadNote] = useState('')
  const [unreadHint, setUnreadHint] = useState(0)

  const loadProcessing = useCallback(async () => {
    const qs = new URLSearchParams({
      page: String(procPage),
      page_size: String(PAGE_SIZE),
    })
    if (procStatus !== 'all') qs.set('status', procStatus)
    const data = await apiFetch<{ items: ProcessingTask[]; total: number }>(
      `/api/v1/realphotos/processing-tasks?${qs.toString()}`,
    )
    setProcItems(data.items || [])
    setProcTotal(data.total || 0)
  }, [procPage, procStatus])

  const loadGeneration = useCallback(async () => {
    const qs = new URLSearchParams({
      page: String(genPage),
      page_size: String(PAGE_SIZE),
    })
    if (genMode !== 'all') qs.set('mode', genMode)
    const data = await apiFetch<{ items: GenerationTask[]; total: number }>(
      `/api/v1/realphotos/generation-tasks?${qs.toString()}`,
    )
    setGenItems(data.items || [])
    setGenTotal(data.total || 0)
  }, [genPage, genMode])

  useEffect(() => {
    void apiFetch<{ unreadCount?: number }>('/api/v1/realphotos/inbox')
      .then((data) => setUnreadHint(Number(data.unreadCount || 0)))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (tab !== 'processing') return
    void loadProcessing().catch((error: unknown) =>
      setNotice(error instanceof ApiError ? error.message : '处理任务加载失败'),
    )
  }, [tab, loadProcessing])

  useEffect(() => {
    if (tab !== 'generation') return
    void loadGeneration().catch((error: unknown) =>
      setNotice(error instanceof ApiError ? error.message : '生图任务加载失败'),
    )
  }, [tab, loadGeneration])

  const selected = procItems.filter((item) => checked[item.id])
  const procPageCount = Math.max(1, Math.ceil(procTotal / PAGE_SIZE))
  const genPageCount = Math.max(1, Math.ceil(genTotal / PAGE_SIZE))

  async function downloadChecked() {
    const ids = selected.filter((item) => item.outputObjectKey).map((item) => Number(item.id))
    if (ids.length < 1) {
      setDownloadNote('没有勾选可下载的结果；未勾选时不会默认下载全部')
      return
    }
    try {
      const listed = await apiFetch<{ items: { taskId: string; objectKey: string; pack: string }[] }>(
        '/api/v1/realphotos/processing-tasks/selected-downloads',
        { method: 'POST', body: JSON.stringify({ taskIds: ids, pack: 'files' }) },
      )
      const files = listed.items.filter((item) => item.pack === 'file')
      if (files.length < 1) {
        setDownloadNote('勾选的任务还没有可下载结果')
        return
      }

      type DirHandle = {
        getFileHandle: (
          name: string,
          opts?: { create?: boolean },
        ) => Promise<{ createWritable: () => Promise<{ write: (data: Blob) => Promise<void>; close: () => Promise<void> }> }>
      }
      const picker = (
        window as Window & {
          showDirectoryPicker?: (opts?: { mode?: string }) => Promise<DirHandle>
        }
      ).showDirectoryPicker

      let dir: DirHandle | null = null
      let mode: 'directory' | 'fallback' = 'fallback'
      let fallbackReason = ''
      if (typeof picker === 'function') {
        try {
          dir = await picker({ mode: 'readwrite' })
          mode = 'directory'
        } catch (error: unknown) {
          const name = error instanceof DOMException ? error.name : ''
          fallbackReason =
            name === 'AbortError'
              ? '用户取消了目录授权'
              : '当前浏览器无法使用目录选择器'
          dir = null
          mode = 'fallback'
        }
      } else {
        fallbackReason = '浏览器不支持 showDirectoryPicker'
      }

      const usedNames = new Map<string, number>()
      const notes: string[] = []
      for (const item of files) {
        const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${item.objectKey}`)
        const bytes = new Uint8Array(await blob.arrayBuffer())
        const jpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
        const base = `${item.taskId}.jpg`
        const seen = usedNames.get(base) || 0
        usedNames.set(base, seen + 1)
        const fileName = seen === 0 ? base : `${item.taskId}-${seen}.jpg`
        if (dir) {
          const handle = await dir.getFileHandle(fileName, { create: true })
          const writable = await handle.createWritable()
          await writable.write(blob)
          await writable.close()
          notes.push(`${fileName}:${bytes.length}${jpeg ? '' : ':非JPEG'}`)
        } else {
          const url = URL.createObjectURL(blob)
          const anchor = document.createElement('a')
          anchor.href = url
          anchor.download = fileName
          anchor.rel = 'noopener'
          document.body.appendChild(anchor)
          anchor.click()
          anchor.remove()
          URL.revokeObjectURL(url)
          notes.push(`${fileName}:${bytes.length}${jpeg ? '' : ':非JPEG'}`)
        }
      }
      if (mode === 'directory') {
        setDownloadNote(`已写入选定目录 ${notes.join(' ')}`)
      } else {
        setDownloadNote(
          `已降级为逐文件下载（${fallbackReason || '目录选择器不可用'}；不生成 ZIP）${notes.join(' ')}`,
        )
      }
    } catch (error: unknown) {
      setDownloadNote(error instanceof ApiError ? error.message : '下载失败')
    }
  }

  async function retryTechnical() {
    const targets = selected.filter(canRetry)
    if (targets.length < 1) return
    try {
      for (const current of targets) {
        await apiFetch(`/api/v1/realphotos/processing-tasks/${current.id}/retry`, { method: 'POST' })
      }
      setNotice('技术重试已提交')
      await loadProcessing()
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '技术重试失败')
    }
  }

  async function reprocessTask() {
    const targets = selected.filter(canReprocess)
    if (targets.length < 1) return
    try {
      for (const current of targets) {
        await apiFetch(`/api/v1/realphotos/processing-tasks/${current.id}/reprocess`, {
          method: 'POST',
          body: JSON.stringify({
            presetCode: current.presetCode,
            idempotencyKey: `reprocess-${current.id}-${Date.now()}`,
          }),
        })
      }
      setNotice('已建立重处理任务，原任务报告仍保留')
      await loadProcessing()
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '主动重处理失败')
    }
  }

  async function copyProcessing() {
    const current = selected[0]
    if (!current) {
      setNotice('请先勾选一条处理任务再复制')
      return
    }
    try {
      const data = await apiFetch<{ id: string; copiedFrom?: string; billingMode?: string }>(
        `/api/v1/realphotos/processing-tasks/${current.id}/copy`,
        {
          method: 'POST',
          body: JSON.stringify({
            idempotencyKey: `copy-${current.id}-${Date.now()}`,
            detectionMode: 'pass',
          }),
        },
      )
      setNotice(`已复制为任务 ${data.id}（copiedFrom=${data.copiedFrom || current.id}，免冻）`)
      await loadProcessing()
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '复制失败')
    }
  }

  async function downloadGenAssets(task: GenerationTask) {
    const notes: string[] = []
    for (const item of task.items) {
      if (!item.assetId) continue
      try {
        const assets = await apiFetch<{ items: { id: string; objectKey?: string }[] }>(
          '/api/v1/realphotos/assets',
        )
        const match = (assets.items || []).find((row) => row.id === item.assetId)
        if (!match?.objectKey) {
          notes.push(`${item.assetId}:无对象`)
          continue
        }
        const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${match.objectKey}`)
        notes.push(`${item.assetId}:${blob.size}`)
      } catch {
        notes.push(`${item.assetId}:失败`)
      }
    }
    setDownloadNote(notes.length ? `生图逐张 ${notes.join(' ')}` : '无可下载资产')
  }

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-medium">任务详情</h1>
        <Link className="border px-2 py-1 text-sm" href="/realphotos/messages">
          消息中心{unreadHint > 0 ? `（未读 ${unreadHint}）` : ''}
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">{notice}</p>
      <div className="flex gap-2 text-sm">
        <button
          className={`border px-3 py-1 ${tab === 'processing' ? 'bg-muted' : ''}`}
          type="button"
          onClick={() => setTab('processing')}
        >
          图片处理任务
        </button>
        <button
          className={`border px-3 py-1 ${tab === 'generation' ? 'bg-muted' : ''}`}
          type="button"
          onClick={() => setTab('generation')}
        >
          生图任务
        </button>
      </div>

      {tab === 'processing' ? (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>
              状态
              <select
                className="ml-2 border px-2 py-1"
                value={procStatus}
                onChange={(event) => {
                  setProcStatus(event.target.value)
                  setProcPage(1)
                }}
              >
                <option value="all">全部</option>
                <option value="DELIVERED">DELIVERED</option>
                <option value="FAILED">FAILED</option>
                <option value="SUBMITTED">SUBMITTED</option>
              </select>
            </label>
            <span>
              第 {procPage} / {procPageCount} 页 · 共 {procTotal} · 默认 10 条
            </span>
            <button className="border px-2 py-1" type="button" disabled={procPage <= 1} onClick={() => setProcPage((p) => p - 1)}>
              上一页
            </button>
            <button
              className="border px-2 py-1"
              type="button"
              disabled={procPage >= procPageCount}
              onClick={() => setProcPage((p) => p + 1)}
            >
              下一页
            </button>
            <button className="border px-2 py-1" type="button" onClick={() => void downloadChecked()}>
              下载勾选
            </button>
            <button
              className="border px-2 py-1 disabled:opacity-40"
              type="button"
              disabled={!selected.some(canRetry)}
              onClick={() => void retryTechnical()}
            >
              技术重试
            </button>
            <button
              className="border px-2 py-1 disabled:opacity-40"
              type="button"
              disabled={!selected.some(canReprocess)}
              onClick={() => void reprocessTask()}
            >
              主动重处理
            </button>
            <button
              className="border px-2 py-1 disabled:opacity-40"
              type="button"
              disabled={selected.length !== 1}
              onClick={() => void copyProcessing()}
            >
              复制（免冻）
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
                <th className="text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {procItems.length === 0 ? (
                <tr>
                  <td colSpan={6}>暂无处理任务</td>
                </tr>
              ) : (
                procItems.map((item) => (
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
                    <td>
                      <button className="border px-2 py-0.5" type="button" onClick={() => setDetail(item)}>
                        详情
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <p className="text-sm">{downloadNote}</p>
          {detail ? (
            <div className="space-y-2 border p-3 text-sm">
              <div className="flex justify-between">
                <strong>处理任务 {detail.id}</strong>
                <button type="button" className="border px-2 py-0.5" onClick={() => setDetail(null)}>
                  关闭
                </button>
              </div>
              <p>预设：{detail.presetCode}</p>
              <p>检测报告：{reportText(detail)}</p>
              <p>积分：{detail.creditDisposition || '处理中'}</p>
              <p className="text-xs text-muted-foreground">报告仅在详情内展示，无独立检测结果页。</p>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>
              模式
              <select
                className="ml-2 border px-2 py-1"
                value={genMode}
                onChange={(event) => {
                  setGenMode(event.target.value)
                  setGenPage(1)
                }}
              >
                <option value="all">全部</option>
                <option value="text_to_image">文生图</option>
                <option value="image_to_image">图生图</option>
              </select>
            </label>
            <span>
              第 {genPage} / {genPageCount} 页 · 共 {genTotal} · 默认 10 条
            </span>
            <button className="border px-2 py-1" type="button" disabled={genPage <= 1} onClick={() => setGenPage((p) => p - 1)}>
              上一页
            </button>
            <button
              className="border px-2 py-1"
              type="button"
              disabled={genPage >= genPageCount}
              onClick={() => setGenPage((p) => p + 1)}
            >
              下一页
            </button>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">任务</th>
                <th className="text-left">模式</th>
                <th className="text-left">数量</th>
                <th className="text-left">尺寸</th>
                <th className="text-left">时间</th>
                <th className="text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {genItems.length === 0 ? (
                <tr>
                  <td colSpan={6}>暂无生图任务</td>
                </tr>
              ) : (
                genItems.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.mode}</td>
                    <td>{item.quantity}</td>
                    <td>
                      {item.width}×{item.height}
                    </td>
                    <td>{item.createdAt || ''}</td>
                    <td className="space-x-2">
                      <button className="border px-2 py-0.5" type="button" onClick={() => setGenDetail(item)}>
                        查看
                      </button>
                      <button className="border px-2 py-0.5" type="button" onClick={() => void downloadGenAssets(item)}>
                        批量下载
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <p className="text-sm">{downloadNote}</p>
          {genDetail ? (
            <div className="space-y-2 border p-3 text-sm">
              <div className="flex justify-between">
                <strong>生图任务 {genDetail.id}</strong>
                <button type="button" className="border px-2 py-0.5" onClick={() => setGenDetail(null)}>
                  关闭
                </button>
              </div>
              <p>正向：{genDetail.positivePrompt}</p>
              <p>负向：{genDetail.negativePrompt || '（空）'}</p>
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="text-left">张</th>
                    <th className="text-left">状态</th>
                    <th className="text-left">资产</th>
                    <th className="text-left">计费</th>
                  </tr>
                </thead>
                <tbody>
                  {genDetail.items.map((row) => (
                    <tr key={row.index}>
                      <td>{row.index}</td>
                      <td>{row.status}</td>
                      <td>{row.assetId || ''}</td>
                      <td>{row.creditsConsumed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-muted-foreground">生图详情无复制、主动重处理、四卡或任务链时间线。</p>
            </div>
          ) : null}
        </section>
      )}
    </main>
  )
}
