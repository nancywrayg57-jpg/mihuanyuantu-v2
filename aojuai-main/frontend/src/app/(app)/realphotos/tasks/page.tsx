'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import {
  DETECTION_PASS_SCORE,
  boolPassLabel,
  creditDispositionLabel,
  detectionDimensionLabel,
  detectionFailureGuidance,
  detectionNotPassedExplanation,
  failureClassLabelForTask,
  generationModeLabel,
  gpsModeLabel,
  presetDisplayName,
  taskStatusLabel,
} from '@/lib/realphotos-labels'

type Detection = {
  accepted?: boolean
  passed?: boolean
  reason?: string
  total_score?: number
  passScoreThreshold?: number
  platformGateExplanation?: string | null
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
  presetSnapshot?: Record<string, unknown> | null
  outputObjectKey?: string | null
  creditDisposition?: string | null
  failureClass?: string | null
  failureMessage?: string | null
  failureTitle?: string | null
  detectionMode?: string | null
  createdAt?: string | null
  detection?: Detection | null
  copiedFrom?: string | null
  billingMode?: string | null
  gpsWrite?: {
    written?: boolean
    reason?: string
    gpsMode?: string | null
    actualGps?: { latitude?: number; longitude?: number; altitude?: number } | null
    failedTags?: Array<{ tag?: string; reason?: string; verificationStatus?: string }>
  } | null
  detectionBrief?: {
    totalScore?: number
    passScoreThreshold?: number
    accepted?: boolean
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
  'MAKERNOTE_WRITE_FAILED',
  'pre_review_failed',
])

function canRetry(task: ProcessingTask): boolean {
  // C1: historical fixture technical is retired — do not present as formal tech-retry guidance
  if (String(task.detectionMode || '').trim() === 'technical') return false
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

function DetectionReport({ detection }: { detection: Detection | null | undefined }) {
  if (!detection) return <p>暂无报告</p>
  const dims: Array<[string, number | undefined]> = [
    ['noise', detection.noise],
    ['depth', detection.depthOfField],
    ['lighting', detection.lighting],
    ['color_realism', detection.colorRealism],
    ['overall_realism', detection.overallRealism],
  ]
  const threshold = detection.passScoreThreshold ?? DETECTION_PASS_SCORE
  const gate =
    detection.platformGateExplanation ||
    (detection.accepted === false ? detectionNotPassedExplanation(detection) : null)
  const guidance = detection.accepted === false ? detectionFailureGuidance(detection) : null
  return (
    <div className="space-y-1">
      <p>
        模型结果：{boolPassLabel(detection.passed)}
        {detection.accepted !== undefined ? ` · 平台接受：${boolPassLabel(detection.accepted)}` : ''}
      </p>
      <p>
        总分：{detection.total_score ?? '—'} / 100（需达到 {threshold} 分）
      </p>
      {gate ? <p className="text-destructive">{gate}</p> : null}
      <p>检测器：{detection.detector || '—'}</p>
      <p>
        原因：
        {guidance?.reason || detection.reason || '—'}
      </p>
      {guidance && guidance.tips.length > 0 ? (
        <div>
          <p>优化方向：</p>
          <ul className="list-inside list-disc">
            {guidance.tips.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <ul className="list-inside list-disc">
        {dims.map(([key, value]) => (
          <li key={key}>
            {detectionDimensionLabel(key)}：{value ?? '—'}
          </li>
        ))}
      </ul>
    </div>
  )
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
  const [procSearch, setProcSearch] = useState('')
  const [genSearch, setGenSearch] = useState('')

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

  const visibleProcItems = useMemo(
    () =>
      procItems.filter((item) =>
        matchSearchText(
          procSearch,
          item.id,
          item.status,
          taskStatusLabel(item.status),
          item.presetCode,
          presetDisplayName(item),
          item.failureClass,
          item.failureMessage,
          item.failureTitle,
        ),
      ),
    [procItems, procSearch],
  )
  const visibleGenItems = useMemo(
    () =>
      genItems.filter((item) =>
        matchSearchText(genSearch, item.id, item.mode, generationModeLabel(item.mode), item.provider, item.positivePrompt),
      ),
    [genItems, genSearch],
  )
  const selected = visibleProcItems.filter((item) => checked[item.id])
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
            detectionMode: 'gemini',
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
        <Link className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1 text-sm" href="/realphotos/messages">
          消息中心{unreadHint > 0 ? `（未读 ${unreadHint}）` : ''}
        </Link>
      </div>
      <p className="text-sm text-muted-foreground">{notice}</p>
      <div className="flex gap-2 text-sm">
        <button
          className={`rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 ${tab === 'processing' ? 'bg-muted' : ''}`}
          type="button"
          onClick={() => setTab('processing')}
        >
          图片处理任务
        </button>
        <button
          className={`rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 ${tab === 'generation' ? 'bg-muted' : ''}`}
          type="button"
          onClick={() => setTab('generation')}
        >
          生图任务
        </button>
      </div>

      {tab === 'processing' ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
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
                <option value="DELIVERED">已交付</option>
                <option value="FAILED">失败</option>
                <option value="SUBMITTED">已提交</option>
                <option value="PRE_REVIEW">预审中</option>
                <option value="PRE_REVIEW_FAILED">预审失败</option>
                <option value="FULL_PROCESSING">处理中</option>
                <option value="DETECTION">检测中</option>
              </select>
            </label>
            <ListSearch value={procSearch} placeholder="任务 ID / 预设 / 状态" onChange={setProcSearch} />
            <span>
              第 {procPage} / {procPageCount} 页 · 共 {procTotal} · 默认 10 条
            </span>
            <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1" type="button" disabled={procPage <= 1} onClick={() => setProcPage((p) => p - 1)}>
              上一页
            </button>
            <button
              className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1"
              type="button"
              disabled={procPage >= procPageCount}
              onClick={() => setProcPage((p) => p + 1)}
            >
              下一页
            </button>
            <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1" type="button" onClick={() => void downloadChecked()}>
              下载勾选
            </button>
            <button
              className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1 disabled:opacity-40"
              type="button"
              disabled={!selected.some(canRetry)}
              onClick={() => void retryTechnical()}
            >
              技术重试
            </button>
            <button
              className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1 disabled:opacity-40"
              type="button"
              disabled={!selected.some(canReprocess)}
              onClick={() => void reprocessTask()}
            >
              主动重处理
            </button>
            <button
              className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1 disabled:opacity-40"
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
                <th className="text-left">失败原因</th>
                <th className="text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {visibleProcItems.length === 0 ? (
                <tr>
                  <td colSpan={6}>暂无处理任务</td>
                </tr>
              ) : (
                visibleProcItems.map((item) => (
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
                    <td>{taskStatusLabel(item.status)}</td>
                    <td>{creditDispositionLabel(item.creditDisposition)}</td>
                    <td>
                      {failureClassLabelForTask(item.failureClass, item.detectionMode)}
                      {item.detectionBrief && item.failureClass === 'detection_not_passed' ? (
                        <span className="ml-1 text-muted-foreground">
                          （总分 {item.detectionBrief.totalScore}/100）
                        </span>
                      ) : null}
                    </td>
                    <td>
                      <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5" type="button" onClick={() => setDetail(item)}>
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
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
              onClick={() => setDetail(null)}
              role="dialog"
              aria-modal="true"
              aria-label={`处理任务 ${detail.id} 详情`}
            >
              <div
                className="max-h-[90vh] w-full max-w-lg space-y-3 overflow-y-auto rp-card rounded-xl border border-border bg-card p-4 text-sm shadow"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="flex justify-between gap-2">
                  <strong>处理任务 {detail.id}</strong>
                  <button type="button" className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5" onClick={() => setDetail(null)}>
                    关闭
                  </button>
                </div>
                <section className="space-y-1">
                  <h3 className="font-medium">基本</h3>
                  <p>状态：{taskStatusLabel(detail.status)}</p>
                  <p>预设名称：{presetDisplayName(detail)}</p>
                  <p>创建时间：{detail.createdAt || '—'}</p>
                  {detail.copiedFrom ? <p>复制自：{detail.copiedFrom}</p> : null}
                </section>
                <section className="space-y-1">
                  <h3 className="font-medium">积分</h3>
                  <p>处置：{creditDispositionLabel(detail.creditDisposition)}</p>
                  {detail.billingMode ? <p>计费模式：{detail.billingMode}</p> : null}
                </section>
                <section className="space-y-1">
                  <h3 className="font-medium">失败</h3>
                  <p>
                    失败原因：
                    {failureClassLabelForTask(detail.failureClass, detail.detectionMode)}
                  </p>
                  {detail.detectionMode ? (
                    <p>
                      检测模式：
                      {detail.detectionMode === 'technical'
                        ? '历史联调替身（已停用）'
                        : detail.detectionMode}
                    </p>
                  ) : null}
                  {detail.failureMessage ? (
                    <p>
                      详情：{detail.failureTitle ? `${detail.failureTitle} — ` : ''}
                      {detail.failureMessage}
                    </p>
                  ) : null}
                </section>
                {detail.gpsWrite ? (
                  <section className="space-y-1">
                    <h3 className="font-medium">EXIF / GPS</h3>
                    <p>
                      GPS 模式：
                      {detail.gpsWrite.gpsMode
                        ? gpsModeLabel(String(detail.gpsWrite.gpsMode))
                        : '—'}
                    </p>
                    <p>是否写入 GPS：{detail.gpsWrite.written ? '是' : '否'}</p>
                    <p>GPS 原因：{detail.gpsWrite.reason || '—'}</p>
                    {detail.gpsWrite.actualGps ? (
                      <p>
                        实际坐标：{detail.gpsWrite.actualGps.latitude ?? '—'},{' '}
                        {detail.gpsWrite.actualGps.longitude ?? '—'}, 海拔{' '}
                        {detail.gpsWrite.actualGps.altitude ?? '—'}
                      </p>
                    ) : null}
                    {detail.gpsWrite.failedTags && detail.gpsWrite.failedTags.length > 0 ? (
                      <ul className="list-inside list-disc">
                        {detail.gpsWrite.failedTags.map((row) => (
                          <li key={`${row.tag}-${row.reason}`}>
                            失败标签 {row.tag || '—'}: {row.reason || '回读失败'}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </section>
                ) : null}
                <section className="space-y-1">
                  <h3 className="font-medium">检测报告</h3>
                  <DetectionReport detection={detail.detection} />
                </section>
              </div>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
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
            <ListSearch value={genSearch} placeholder="任务 ID / 模式 / 提示词" onChange={setGenSearch} />
            <span>
              第 {genPage} / {genPageCount} 页 · 共 {genTotal} · 默认 10 条
            </span>
            <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1" type="button" disabled={genPage <= 1} onClick={() => setGenPage((p) => p - 1)}>
              上一页
            </button>
            <button
              className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-1"
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
              {visibleGenItems.length === 0 ? (
                <tr>
                  <td colSpan={6}>暂无生图任务</td>
                </tr>
              ) : (
                visibleGenItems.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{generationModeLabel(item.mode)}</td>
                    <td>{item.quantity}</td>
                    <td>
                      {item.width}×{item.height}
                    </td>
                    <td>{item.createdAt || ''}</td>
                    <td className="space-x-2">
                      <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5" type="button" onClick={() => setGenDetail(item)}>
                        查看
                      </button>
                      <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5" type="button" onClick={() => void downloadGenAssets(item)}>
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
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
              onClick={() => setGenDetail(null)}
              role="dialog"
              aria-modal="true"
              aria-label={`生图任务 ${genDetail.id} 详情`}
            >
              <div
                className="max-h-[90vh] w-full max-w-lg space-y-2 overflow-y-auto rp-card rounded-xl border border-border bg-card p-4 text-sm shadow"
                onClick={(event) => event.stopPropagation()}
              >
                <div className="flex justify-between">
                  <strong>生图任务 {genDetail.id}</strong>
                  <button type="button" className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-2 py-0.5" onClick={() => setGenDetail(null)}>
                    关闭
                  </button>
                </div>
                <p>模式：{generationModeLabel(genDetail.mode)}</p>
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
                        <td>{taskStatusLabel(row.status)}</td>
                        <td>{row.assetId || ''}</td>
                        <td>{row.creditsConsumed}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-muted-foreground">生图详情无复制、主动重处理、四卡或任务链时间线。</p>
              </div>
            </div>
          ) : null}
        </section>
      )}
    </main>
  )
}
