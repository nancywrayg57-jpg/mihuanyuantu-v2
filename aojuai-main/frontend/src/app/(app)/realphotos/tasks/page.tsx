'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpButton } from '@/components/realphotos/rp-button'
import { RpField } from '@/components/realphotos/rp-field'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { RpSection } from '@/components/realphotos/rp-section'
import { RpDialog, RpEmpty, RpFilterBar, RpPagination, RpStatus, RpTable, RpTh } from '@/components/realphotos/rp-table'
import { rpSelectClass, toastTask } from '@/components/realphotos/surface'
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

function statusTone(status: string): 'ok' | 'bad' | 'warn' | 'neutral' {
  if (status === 'DELIVERED') return 'ok'
  if (status === 'FAILED' || status === 'PRE_REVIEW_FAILED' || status === 'IMAGE_LOCKED') return 'bad'
  if (status === 'DETECTION' || status === 'FULL_PROCESSING' || status === 'PRE_REVIEW' || status === 'SUBMITTED') {
    return 'warn'
  }
  return 'neutral'
}

function DetectionReport({ detection }: { detection: Detection | null | undefined }) {
  if (!detection) return <p className="text-muted-foreground">暂无报告</p>
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
    <div className="space-y-2">
      <div className="rp-score-grid">
        <div className="rp-score-cell">
          <span>总分</span>
          <strong>{detection.total_score ?? '—'}</strong>
          <span>需达到 {threshold} / 100</span>
        </div>
        {dims.map(([key, value]) => (
          <div key={key} className="rp-score-cell">
            <span>{detectionDimensionLabel(key)}</span>
            <strong>{value ?? '—'}</strong>
          </div>
        ))}
      </div>
      <dl className="rp-kv">
        <dt>模型结果</dt>
        <dd>{boolPassLabel(detection.passed)}</dd>
        {detection.accepted !== undefined ? (
          <>
            <dt>平台接受</dt>
            <dd>{boolPassLabel(detection.accepted)}</dd>
          </>
        ) : null}
        <dt>检测器</dt>
        <dd>{detection.detector || '—'}</dd>
        <dt>原因</dt>
        <dd>{guidance?.reason || detection.reason || '—'}</dd>
      </dl>
      {gate ? <p className="text-destructive">{gate}</p> : null}
      {guidance && guidance.tips.length > 0 ? (
        <div>
          <p className="font-medium">优化方向</p>
          <ul className="list-inside list-disc">
            {guidance.tips.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        </div>
      ) : null}
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

  const PROC_TERMINAL = useMemo(
    () => new Set(['DELIVERED', 'FAILED', 'PRE_REVIEW_FAILED', 'IMAGE_LOCKED']),
    [],
  )

  // Live refresh while any processing task is non-terminal (no manual page reload).
  useEffect(() => {
    if (tab !== 'processing') return
    const hasInFlight = procItems.some((item) => !PROC_TERMINAL.has(String(item.status || '')))
    if (!hasInFlight) return
    const timer = window.setInterval(() => {
      void loadProcessing().catch(() => undefined)
    }, 3000)
    return () => window.clearInterval(timer)
  }, [tab, procItems, loadProcessing, PROC_TERMINAL])

  // Mirror latest list row into open detail dialog.
  useEffect(() => {
    if (!detail) return
    const next = procItems.find((item) => item.id === detail.id)
    if (!next) return
    if (
      next.status !== detail.status ||
      next.creditDisposition !== detail.creditDisposition ||
      next.outputObjectKey !== detail.outputObjectKey
    ) {
      setDetail(next)
    }
  }, [procItems, detail])

  // Extra detail poll while dialog shows an in-flight task.
  useEffect(() => {
    if (!detail) return
    if (PROC_TERMINAL.has(String(detail.status || ''))) return
    const timer = window.setInterval(() => {
      void apiFetch<ProcessingTask>(`/api/v1/realphotos/processing-tasks/${detail.id}`)
        .then((row) => {
          setDetail(row)
          setProcItems((prev) => prev.map((item) => (item.id === row.id ? { ...item, ...row } : item)))
        })
        .catch(() => undefined)
    }, 2500)
    return () => window.clearInterval(timer)
  }, [detail, PROC_TERMINAL])

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
      toastTask('没有勾选可下载的结果；未勾选时不会默认下载全部', false)
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
        toastTask('勾选的任务还没有可下载结果', false)
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
        const text = `已写入选定目录 ${notes.join(' ')}`
        setDownloadNote(text)
        toastTask(text, true)
      } else {
        const text = `已降级为逐文件下载（${fallbackReason || '目录选择器不可用'}；不生成 ZIP）${notes.join(' ')}`
        setDownloadNote(text)
        toastTask(text, true)
      }
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '下载失败'
      setDownloadNote(text)
      toastTask(text, false)
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
      toastTask('技术重试已提交', true)
      await loadProcessing()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '技术重试失败'
      setNotice(text)
      toastTask(text, false)
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
      toastTask('已建立重处理任务，原任务报告仍保留', true)
      await loadProcessing()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '主动重处理失败'
      setNotice(text)
      toastTask(text, false)
    }
  }

  async function copyProcessing() {
    const current = selected[0]
    if (!current) {
      setNotice('请先勾选一条处理任务再复制')
      toastTask('请先勾选一条处理任务再复制', false)
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
      const text = `已复制为任务 ${data.id}（copiedFrom=${data.copiedFrom || current.id}，免冻）`
      setNotice(text)
      toastTask(text, true)
      await loadProcessing()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '复制失败'
      setNotice(text)
      toastTask(text, false)
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
    const text = notes.length ? `生图逐张 ${notes.join(' ')}` : '无可下载资产'
    setDownloadNote(text)
    toastTask(text, notes.length > 0 && !notes.some((row) => row.endsWith(':失败')))
  }


  return (
    <main className="space-y-6 p-6">
      <RpPageHeader
        title="任务详情"
        actions={
          <Link className="rp-btn" href="/realphotos/messages">
            消息中心{unreadHint > 0 ? `（未读 ${unreadHint}）` : ''}
          </Link>
        }
      />
      {notice ? <p className="text-sm text-muted-foreground">{notice}</p> : null}
      <div className="flex gap-2 text-sm">
        <RpButton pressed={tab === 'processing'} type="button" onClick={() => setTab('processing')}>
          图片处理任务
        </RpButton>
        <RpButton pressed={tab === 'generation'} type="button" onClick={() => setTab('generation')}>
          生图任务
        </RpButton>
      </div>

      {tab === 'processing' ? (
        <section className="rp-card space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm">
          <RpFilterBar>
            <RpField label="状态">
              <select
                className={rpSelectClass}
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
            </RpField>
            <ListSearch value={procSearch} placeholder="任务 ID / 预设 / 状态" onChange={setProcSearch} />
            <RpPagination
              page={procPage}
              pageCount={procPageCount}
              total={procTotal}
              extra="默认 10 条"
              onPrev={() => setProcPage((p) => p - 1)}
              onNext={() => setProcPage((p) => p + 1)}
            />
            <RpButton variant="primary" type="button" onClick={() => void downloadChecked()}>
              下载勾选
            </RpButton>
            <RpButton type="button" disabled={!selected.some(canRetry)} onClick={() => void retryTechnical()}>
              技术重试
            </RpButton>
            <RpButton type="button" disabled={!selected.some(canReprocess)} onClick={() => void reprocessTask()}>
              主动重处理
            </RpButton>
            <RpButton type="button" disabled={selected.length !== 1} onClick={() => void copyProcessing()}>
              复制（免冻）
            </RpButton>
          </RpFilterBar>
          <RpTable>
            <thead>
              <tr>
                <RpTh>勾选</RpTh>
                <RpTh>任务</RpTh>
                <RpTh>状态</RpTh>
                <RpTh>积分处置</RpTh>
                <RpTh>失败原因</RpTh>
                <RpTh>操作</RpTh>
              </tr>
            </thead>
            <tbody>
              {visibleProcItems.length === 0 ? (
                <RpEmpty colSpan={6}>暂无处理任务</RpEmpty>
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
                    <td>
                      <RpStatus tone={statusTone(item.status)}>{taskStatusLabel(item.status)}</RpStatus>
                    </td>
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
                      <RpButton size="sm" type="button" onClick={() => setDetail(item)}>
                        详情
                      </RpButton>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </RpTable>
          {downloadNote ? <p className="text-sm">{downloadNote}</p> : null}
          {detail ? (
            <RpDialog
              title={`处理任务 ${detail.id}`}
              label={`处理任务 ${detail.id} 详情`}
              onClose={() => setDetail(null)}
            >
              <RpSection title="基本" tone="basic">
                <dl className="rp-kv">
                  <dt>状态</dt>
                  <dd>{taskStatusLabel(detail.status)}</dd>
                  <dt>预设名称</dt>
                  <dd>{presetDisplayName(detail)}</dd>
                  <dt>创建时间</dt>
                  <dd>{detail.createdAt || '—'}</dd>
                  {detail.copiedFrom ? (
                    <>
                      <dt>复制自</dt>
                      <dd>{detail.copiedFrom}</dd>
                    </>
                  ) : null}
                </dl>
              </RpSection>
              <RpSection title="积分" tone="credit">
                <dl className="rp-kv">
                  <dt>处置</dt>
                  <dd>{creditDispositionLabel(detail.creditDisposition)}</dd>
                  {detail.billingMode ? (
                    <>
                      <dt>计费模式</dt>
                      <dd>{detail.billingMode}</dd>
                    </>
                  ) : null}
                </dl>
              </RpSection>
              <RpSection title="失败" tone="failure">
                <dl className="rp-kv">
                  <dt>失败原因</dt>
                  <dd>{failureClassLabelForTask(detail.failureClass, detail.detectionMode)}</dd>
                  {detail.detectionMode ? (
                    <>
                      <dt>检测模式</dt>
                      <dd>
                        {detail.detectionMode === 'technical' ? '历史联调替身（已停用）' : detail.detectionMode}
                      </dd>
                    </>
                  ) : null}
                  {detail.failureMessage ? (
                    <>
                      <dt>详情</dt>
                      <dd>
                        {detail.failureTitle ? `${detail.failureTitle} — ` : ''}
                        {detail.failureMessage}
                      </dd>
                    </>
                  ) : null}
                </dl>
              </RpSection>
              {detail.gpsWrite ? (
                <RpSection title="EXIF / GPS" tone="gps">
                  <dl className="rp-kv">
                    <dt>GPS 模式</dt>
                    <dd>
                      {detail.gpsWrite.gpsMode ? gpsModeLabel(String(detail.gpsWrite.gpsMode)) : '—'}
                    </dd>
                    <dt>是否写入</dt>
                    <dd>{detail.gpsWrite.written ? '是' : '否'}</dd>
                    <dt>GPS 原因</dt>
                    <dd>{detail.gpsWrite.reason || '—'}</dd>
                    {detail.gpsWrite.actualGps ? (
                      <>
                        <dt>实际坐标</dt>
                        <dd>
                          {detail.gpsWrite.actualGps.latitude ?? '—'}, {detail.gpsWrite.actualGps.longitude ?? '—'}
                          ，海拔 {detail.gpsWrite.actualGps.altitude ?? '—'}
                        </dd>
                      </>
                    ) : null}
                  </dl>
                  {detail.gpsWrite.failedTags && detail.gpsWrite.failedTags.length > 0 ? (
                    <ul className="list-inside list-disc">
                      {detail.gpsWrite.failedTags.map((row) => (
                        <li key={`${row.tag}-${row.reason}`}>
                          失败标签 {row.tag || '—'}: {row.reason || '回读失败'}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </RpSection>
              ) : null}
              <RpSection title="检测报告" tone="report">
                <DetectionReport detection={detail.detection} />
              </RpSection>
            </RpDialog>
          ) : null}
        </section>
      ) : (
        <section className="rp-card space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm">
          <RpFilterBar>
            <RpField label="模式">
              <select
                className={rpSelectClass}
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
            </RpField>
            <ListSearch value={genSearch} placeholder="任务 ID / 模式 / 提示词" onChange={setGenSearch} />
            <RpPagination
              page={genPage}
              pageCount={genPageCount}
              total={genTotal}
              extra="默认 10 条"
              onPrev={() => setGenPage((p) => p - 1)}
              onNext={() => setGenPage((p) => p + 1)}
            />
          </RpFilterBar>
          <RpTable>
            <thead>
              <tr>
                <RpTh>任务</RpTh>
                <RpTh>模式</RpTh>
                <RpTh>数量</RpTh>
                <RpTh>尺寸</RpTh>
                <RpTh>时间</RpTh>
                <RpTh>操作</RpTh>
              </tr>
            </thead>
            <tbody>
              {visibleGenItems.length === 0 ? (
                <RpEmpty colSpan={6}>暂无生图任务</RpEmpty>
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
                      <RpButton size="sm" type="button" onClick={() => setGenDetail(item)}>
                        查看
                      </RpButton>
                      <RpButton size="sm" type="button" onClick={() => void downloadGenAssets(item)}>
                        批量下载
                      </RpButton>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </RpTable>
          {downloadNote ? <p className="text-sm">{downloadNote}</p> : null}
          {genDetail ? (
            <RpDialog
              title={`生图任务 ${genDetail.id}`}
              label={`生图任务 ${genDetail.id} 详情`}
              onClose={() => setGenDetail(null)}
            >
              <RpSection title="预览" tone="preview">
                <dl className="rp-kv">
                  <dt>模式</dt>
                  <dd>{generationModeLabel(genDetail.mode)}</dd>
                  <dt>尺寸</dt>
                  <dd>
                    {genDetail.width}×{genDetail.height}
                  </dd>
                  <dt>数量</dt>
                  <dd>{genDetail.quantity}</dd>
                  <dt>正向</dt>
                  <dd>{genDetail.positivePrompt}</dd>
                  <dt>负向</dt>
                  <dd>{genDetail.negativePrompt || '（空）'}</dd>
                </dl>
              </RpSection>
              <RpSection title="逐张状态" tone="items">
                <RpTable>
                  <thead>
                    <tr>
                      <RpTh>张</RpTh>
                      <RpTh>状态</RpTh>
                      <RpTh>资产</RpTh>
                    </tr>
                  </thead>
                  <tbody>
                    {genDetail.items.map((row) => (
                      <tr key={row.index}>
                        <td>{row.index}</td>
                        <td>{taskStatusLabel(row.status)}</td>
                        <td>{row.assetId || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </RpTable>
              </RpSection>
              <RpSection title="计费" tone="billing">
                <dl className="rp-kv">
                  <dt>合计消耗</dt>
                  <dd>{genDetail.items.reduce((sum, row) => sum + Number(row.creditsConsumed || 0), 0)}</dd>
                </dl>
                <RpTable>
                  <thead>
                    <tr>
                      <RpTh>张</RpTh>
                      <RpTh>计费</RpTh>
                    </tr>
                  </thead>
                  <tbody>
                    {genDetail.items.map((row) => (
                      <tr key={`bill-${row.index}`}>
                        <td>{row.index}</td>
                        <td>{row.creditsConsumed}</td>
                      </tr>
                    ))}
                  </tbody>
                </RpTable>
              </RpSection>
              <p className="text-xs text-muted-foreground">生图详情无复制、主动重处理、四卡或任务链时间线。</p>
            </RpDialog>
          ) : null}
        </section>
      )}
    </main>
  )
}
