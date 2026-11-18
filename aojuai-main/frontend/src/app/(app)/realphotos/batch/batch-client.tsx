'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpButton } from '@/components/realphotos/rp-button'
import { RpDialog } from '@/components/realphotos/rp-table'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import { gpsSubmitGuard } from '@/lib/realphotos-gps-submit'
import { deviceTypeLabel, gpsModeLabel } from '@/lib/realphotos-labels'
import { PRESET_FIELD_DEFS, type PresetFieldDef } from '@/lib/realphotos-preset-fields'
import { inspectLocalFile } from '@/lib/realphotos-s1'

type Preset = {
  code: string
  name?: string | null
  model: string
  deviceType: string
  brand: string
  gpsWritable?: boolean
  gpsWillSkip?: boolean
  gpsWritableReason?: string
  gpsMode?: string
  [key: string]: unknown
}


/** 2026-11-17: 预设参数取值，规则与「设备预设」页一致（列字段优先，其次 legacyParameters）。 */
function presetFieldText(preset: Record<string, unknown>, field: PresetFieldDef): string {
  const legacy = (preset.legacyParameters as Record<string, unknown> | undefined) || {}
  if (field.column) {
    const direct = preset[field.column]
    if (direct !== undefined && direct !== null && String(direct).trim() !== '') return String(direct)
  }
  const raw = legacy[field.key]
  return raw === undefined || raw === null ? '' : String(raw)
}

/** 展开时展示除两份提示词、以及首屏摘要已展示字段外的其余设备参数。 */
const PRESET_DETAIL_FIELDS = PRESET_FIELD_DEFS.filter(
  (field) =>
    field.column !== 'aiPositivePrompt' &&
    field.column !== 'aiNegativePrompt' &&
    !['deviceType', 'brand', 'model', 'iso', 'shutter', 'aperture', 'focalLength', 'gpsMode'].includes(
      String(field.column || ''),
    ),
)

const PROCESS_UNIT_CREDITS = 10

function presetColumnText(preset: Record<string, unknown>, column: string): string {
  const field = PRESET_FIELD_DEFS.find((item) => item.column === column)
  return field ? presetFieldText(preset, field) : ''
}

type PendingAsset = { id: string; previewUrl: string; name?: string }

export function RealphotosBatchClient() {
  const searchParams = useSearchParams()
  const [presets, setPresets] = useState<Preset[]>([])
  const [deviceType, setDeviceType] = useState('')
  const [brand, setBrand] = useState('')
  const [presetCode, setPresetCode] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [notice, setNotice] = useState('')
  const [frozen, setFrozen] = useState(false)
  const [library, setLibrary] = useState<PendingAsset[]>([])
  const [presetSearch, setPresetSearch] = useState('')
  const [presetDetailOpen, setPresetDetailOpen] = useState(false)
  const [presetDetail, setPresetDetail] = useState<Preset | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const gatewayPreviewUrls = useRef<Set<string>>(new Set())

  useEffect(() => {
    void apiFetch<{ preReviewFrozen: boolean }>('/api/v1/realphotos/me')
      .then((data) => setFrozen(Boolean(data.preReviewFrozen)))
      .catch(() => undefined)
    void apiFetch<{ items: Preset[] }>('/api/v1/realphotos/presets')
      .then((data) => {
        const items = data.items || []
        setPresets(items)
        const first = items[0]
        if (first) {
          setDeviceType(first.deviceType)
          setBrand(first.brand)
          setPresetCode(first.code)
        }
      })
      .catch((error: unknown) => setNotice(error instanceof ApiError ? error.message : '预设加载失败'))
  }, [])

  useEffect(() => {
    const raw = searchParams.get('assetIds') || ''
    const ids = raw
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, 10)
    if (!ids.length) return

    let cancelled = false
    const created: string[] = []

    setLibrary(ids.map((id) => ({ id, previewUrl: '' })))
    setNotice(`已从图片资源带入 ${ids.length} 张`)

    async function loadLibraryThumbs() {
      let assets: { id: string; objectKey?: string; displayName?: string }[] = []
      try {
        // Resolve selected ids directly — default assets pageSize=20 would miss older picks.
        const data = await apiFetch<{ items: { id: string; objectKey?: string; displayName?: string }[] }>(
          `/api/v1/realphotos/assets?ids=${encodeURIComponent(ids.join(','))}`,
        )
        assets = data.items || []
      } catch {
        if (!cancelled) setNotice((prev) => `${prev}；资源列表加载失败，缩略图暂不可用`)
        return
      }
      const byId = new Map(assets.map((item) => [String(item.id), item]))
      if (!cancelled) {
        setLibrary((prev) =>
          prev.map((row) => ({
            ...row,
            name: byId.get(String(row.id))?.displayName || row.name,
          })),
        )
      }
      let missing = 0
      let thumbFail = 0
      for (const id of ids) {
        if (cancelled) return
        const objectKey = byId.get(String(id))?.objectKey
        if (!objectKey) {
          missing += 1
          continue
        }
        try {
          const blob = await apiFetchBlob(
            `/api/v1/realphotos/gateway/objects/${objectKey.split('/').map(encodeURIComponent).join('/')}`,
          )
          if (cancelled) return
          const url = URL.createObjectURL(blob)
          created.push(url)
          gatewayPreviewUrls.current.add(url)
          setLibrary((prev) =>
            prev.map((row) => (row.id === id && !row.previewUrl ? { ...row, previewUrl: url } : row)),
          )
        } catch {
          thumbFail += 1
        }
      }
      if (!cancelled && (missing > 0 || thumbFail > 0)) {
        const parts = [
          missing > 0 ? `未找到资源 ${missing} 张` : '',
          thumbFail > 0 ? `缩略图加载失败 ${thumbFail} 张` : '',
        ].filter(Boolean)
        setNotice((prev) => `${prev}；${parts.join('，')}（文件缺失时提交也会失败）`)
      }
    }

    void loadLibraryThumbs()
    return () => {
      cancelled = true
      for (const url of created) {
        URL.revokeObjectURL(url)
        gatewayPreviewUrls.current.delete(url)
      }
    }
  }, [searchParams])

  useEffect(() => {
    return () => {
      for (const url of gatewayPreviewUrls.current) URL.revokeObjectURL(url)
      gatewayPreviewUrls.current.clear()
    }
  }, [])

  const deviceTypes = useMemo(
    () => Array.from(new Set(presets.map((item) => item.deviceType).filter(Boolean))),
    [presets],
  )
  const brands = useMemo(
    () =>
      Array.from(
        new Set(
          presets
            .filter((item) => !deviceType || item.deviceType === deviceType)
            .map((item) => item.brand)
            .filter(Boolean),
        ),
      ),
    [presets, deviceType],
  )
  const models = useMemo(
    () =>
      presets.filter(
        (item) =>
          (!deviceType || item.deviceType === deviceType) &&
          (!brand || item.brand === brand) &&
          matchSearchText(presetSearch, item.code, item.model, item.brand, item.deviceType),
      ),
    [presets, deviceType, brand, presetSearch],
  )

  useEffect(() => {
    if (!models.some((item) => item.code === presetCode)) {
      setPresetCode(models[0]?.code || '')
    }
  }, [models, presetCode])

  const selectedPreset = useMemo(
    () => presets.find((item) => item.code === presetCode) || null,
    [presets, presetCode],
  )
  const gpsGuard = useMemo(() => gpsSubmitGuard(selectedPreset), [selectedPreset])

  // 2026-11-17: 选中预设后拉取全量设备参数（列表接口只给精简字段）。
  useEffect(() => {
    if (!presetCode) {
      setPresetDetail(null)
      return
    }
    let cancelled = false
    void apiFetch<Preset>(
      `/api/v1/realphotos/presets/${encodeURIComponent(presetCode)}`,
    )
      .then((data) => {
        if (!cancelled) setPresetDetail(data)
      })
      .catch(() => {
        if (!cancelled) setPresetDetail(null)
      })
    return () => {
      cancelled = true
    }
  }, [presetCode])

  const detailPreset = presetDetail && presetDetail.code === presetCode ? presetDetail : selectedPreset
  const gpsSubmitBlocked = gpsGuard.blocked
  const gpsSkipHint = gpsGuard.skipHint
  async function onFile(next: File | null) {
    setFile(null)
    if (!next) return
    const inspected = await inspectLocalFile(next)
    if (!inspected.ok) {
      setNotice(`前端拒绝：${inspected.message}。未上传。`)
      return
    }
    setFile(next)
    setNotice(`前端通过：${inspected.width}×${inspected.height}。上传后须再勾选加入批次。`)
  }

  async function uploadToLibrary() {
    if (frozen) {
      setNotice('账号已因预审冻结，不能新建任务或上传入库')
      return
    }
    if (!file) {
      setNotice('请先选择通过校验的图片')
      return
    }
    const body = new FormData()
    body.set('file', file)
    body.set('name', file.name)
    try {
      const data = await apiFetch<{ id: string }>('/api/v1/realphotos/assets', { method: 'POST', body })
      const previewUrl = URL.createObjectURL(file)
      setLibrary((prev) => {
        if (prev.length >= 10) return prev
        if (prev.some((item) => item.id === data.id)) return prev
        return [...prev, { id: data.id, previewUrl, name: file.name }]
      })
      setNotice(`已入库资源 ${data.id}，并加入本批待处理`)
      setFile(null)
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '上传失败')
    }
  }

  function requestSubmit() {
    if (frozen) {
      const text = '账号已因预审冻结，不能提交处理'
      setNotice(text)
      toastTask(text, false)
      return
    }
    if (!presetCode || library.length < 1 || library.length > 10) {
      const text = '须先选择库内资源 1–10 张，并完成类型→品牌→型号'
      setNotice(text)
      toastTask(text, false)
      return
    }
    if (gpsSubmitBlocked) {
      const text = `所选预设 GPS 不可用，已拦截提交：${gpsGuard.blockReason}`
      setNotice(text)
      toastTask(text, false)
      return
    }
    setConfirmOpen(true)
  }

  async function submitBatch() {
    if (submitting) return
    if (frozen || !presetCode || library.length < 1) return
    setSubmitting(true)
    try {
      const data = await apiFetch<{ batchId: string; tasks: { id: string }[] }>(
        '/api/v1/realphotos/processing-batches',
        {
          method: 'POST',
          body: JSON.stringify({
            assetIds: library.map((item) => Number(item.id)),
            presetCode,
            idempotencyKey: `ui-batch-${library.map((item) => item.id).join('-')}-${Date.now()}`,
          }),
        },
      )
      window.sessionStorage.setItem('realphotos.s4.batchId', data.batchId)
      if (data.tasks[0]) window.sessionStorage.setItem('realphotos.s1.taskId', data.tasks[0].id)
      const text = `批次 ${data.batchId} 已提交，共 ${data.tasks.length} 张。到任务详情查看。`
      setNotice(text)
      toastTask(text, true)
      setConfirmOpen(false)
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '批次提交失败'
      setNotice(text)
      toastTask(text, false)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <RpPageHeader title="批量原图" />
      {frozen ? (
        <p className="text-sm text-destructive">账号已冻结：可查看历史，不能提交新处理。</p>
      ) : null}
      <p className="text-sm">{notice}</p>
      <section className="rp-card space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">设备预设（类型 → 品牌 → 型号）</h2>
          <ListSearch value={presetSearch} placeholder="型号 / 品牌 / 编码" onChange={setPresetSearch} />
        </div>
        <div className="rp-filter flex flex-wrap gap-3 text-sm">
          <label>
            类型
            <select
              className="rp-input mt-1 block"
              value={deviceType}
              onChange={(event) => {
                setDeviceType(event.target.value)
                setBrand('')
              }}
            >
              {deviceTypes.map((item) => (
                <option key={item} value={item}>
                  {deviceTypeLabel(item)}
                </option>
              ))}
            </select>
          </label>
          <label>
            品牌
            <select
              className="rp-input mt-1 block"
              value={brand}
              onChange={(event) => setBrand(event.target.value)}
            >
              {brands.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            型号
            <select
              className="rp-input mt-1 block"
              value={presetCode}
              onChange={(event) => setPresetCode(event.target.value)}
            >
              {models.map((item) => (
                <option key={item.code} value={item.code}>
                  {String(item.name || item.model)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {gpsSubmitBlocked ? (
          <p className="text-sm text-destructive">GPS 不可用，已禁止提交：{gpsGuard.blockReason}</p>
        ) : null}
        {!gpsSubmitBlocked && gpsSkipHint ? (
          <p className="text-sm text-amber-700 dark:text-amber-400">
            {gpsSkipHint.includes('不写入') || gpsSkipHint.includes('跳过')
              ? gpsSkipHint
              : `将跳过 GPS 写入：${gpsSkipHint}`}
          </p>
        ) : null}
        {detailPreset ? (
          <div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 md:grid-cols-4">
              <div>
                <dt className="text-muted-foreground">类型</dt>
                <dd>{deviceTypeLabel(String(detailPreset.deviceType || ''))}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">品牌</dt>
                <dd>{String(detailPreset.brand || '—')}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">型号</dt>
                <dd>{String(detailPreset.model || '—')}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">GPS</dt>
                <dd>
                  {gpsModeLabel(String(detailPreset.gpsMode || 'none'))}
                  {detailPreset.gpsWillSkip ? '（跳过写入）' : ''}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">ISO</dt>
                <dd>{presetColumnText(detailPreset, 'iso') || '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">快门</dt>
                <dd>{presetColumnText(detailPreset, 'shutter') || '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">光圈</dt>
                <dd>{presetColumnText(detailPreset, 'aperture') || '—'}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">焦距</dt>
                <dd>{presetColumnText(detailPreset, 'focalLength') || '—'}</dd>
              </div>
            </dl>
            {presetDetailOpen ? (
              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-border/50 pt-2 md:grid-cols-4">
                {PRESET_DETAIL_FIELDS.map((field) => {
                  const text = presetFieldText(detailPreset, field)
                  if (!text.trim()) return null
                  return (
                    <div key={field.key}>
                      <dt className="text-muted-foreground">{field.label}</dt>
                      <dd className="break-all">{text}</dd>
                    </div>
                  )
                })}
              </dl>
            ) : null}
            <button
              className="rp-btn border mt-2 px-2 py-0.5 text-xs"
              type="button"
              onClick={() => setPresetDetailOpen((prev) => !prev)}
            >
              {presetDetailOpen ? '收起其余参数' : '展开其余参数'}
            </button>
          </div>
        ) : null}
      </section>
      <section className="rp-card space-y-3 p-4">
        <h2 className="text-sm font-medium">待处理图片</h2>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Link className="rp-btn" href="/realphotos/library">
            勾选图片
          </Link>
          {/* 2026-11-17：原生 file 控件改为统一按钮样式 */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">本地辅助入库</span>
            <label className="rp-btn cursor-pointer">
              选择文件
              <input
                className="sr-only"
                type="file"
                accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                onChange={(event) => void onFile(event.target.files?.[0] || null)}
              />
            </label>
            <span className="max-w-[12rem] truncate text-xs text-muted-foreground">
              {file?.name || '未选择文件'}
            </span>
          </div>
          <button className="rp-btn" type="button" disabled={frozen} onClick={() => void uploadToLibrary()}>
            上传并加入本批
          </button>
          <button
            className="rp-btn"
            type="button"
            onClick={() =>
              setLibrary((prev) => {
                const last = prev[prev.length - 1]
                if (last?.previewUrl) {
                  URL.revokeObjectURL(last.previewUrl)
                  gatewayPreviewUrls.current.delete(last.previewUrl)
                }
                return prev.slice(0, -1)
              })
            }
          >
            移除最后一张
          </button>
          <button
            className="rp-btn rp-btn-primary"
            type="button"
            disabled={frozen || gpsSubmitBlocked || submitting || library.length === 0}
            onClick={requestSubmit}
          >
            开始处理
          </button>
        </div>
        <table className="rp-table">
          <thead>
            <tr>
              <th className="text-left">缩略图</th>
              <th className="text-left">文件名</th>
              <th className="text-left">张数</th>
            </tr>
          </thead>
          <tbody>
            {library.length === 0 ? (
              <tr>
                <td className="rp-empty" colSpan={3}>
                  <div className="space-y-1">
                    <div className="font-medium text-foreground">还没有待处理图片</div>
                    <div className="text-xs text-muted-foreground">
                      先从「图片资源」勾选图片，或使用上方本地上传加入本批。
                    </div>
                    <Link className="rp-btn rp-btn-primary rp-btn-sm" href="/realphotos/library">
                      去图片资源选图
                    </Link>
                  </div>
                </td>
              </tr>
            ) : (
              library.map((item, index) => (
                <tr key={`${item.id}-${index}`}>
                  <td>
                    {item.previewUrl ? (
                      <img src={item.previewUrl} alt="" className="h-12 w-12 object-cover" />
                    ) : (
                      <span className="inline-block h-12 w-12 border" />
                    )}
                  </td>
                  <td className="max-w-[18rem] truncate" title={item.name || `资源 #${item.id}`}>
                    {item.name || `资源 #${item.id}`}
                  </td>
                  <td>{index === 0 ? `${library.length} / 10` : ''}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      {confirmOpen && detailPreset ? (
        <RpDialog title="确认提交处理" onClose={() => setConfirmOpen(false)}>
          <p className="text-sm">
            本次提交 <strong>{library.length}</strong> 张，单价 <strong>{PROCESS_UNIT_CREDITS} 积分/张</strong>，
            预计冻结 <strong>{library.length * PROCESS_UNIT_CREDITS} 积分</strong>。
          </p>
          <dl className="rp-kv text-sm">
            <dt>预设</dt>
            <dd>{presetColumnText(detailPreset, 'brand')} {presetColumnText(detailPreset, 'model')}</dd>
            <dt>曝光</dt>
            <dd>
              ISO {presetColumnText(detailPreset, 'iso') || '—'} · 快门{' '}
              {presetColumnText(detailPreset, 'shutter') || '—'} · 光圈{' '}
              {presetColumnText(detailPreset, 'aperture') || '—'} · 焦距{' '}
              {presetColumnText(detailPreset, 'focalLength') || '—'}
            </dd>
            <dt>GPS</dt>
            <dd>
              {gpsModeLabel(String(detailPreset.gpsMode || 'none'))}
              {detailPreset.gpsWillSkip ? '（跳过写入）' : ''}
            </dd>
          </dl>
          <p className="text-xs text-muted-foreground">
            提交后按张冻结；检测未通过或处理失败时按规则释放或走申诉，具体以任务详情与积分流水为准。
          </p>
          <div className="flex flex-wrap gap-2">
            <RpButton variant="primary" type="button" disabled={submitting} onClick={() => void submitBatch()}>
              {submitting ? '提交中…' : '确认提交'}
            </RpButton>
            <RpButton type="button" onClick={() => setConfirmOpen(false)}>
              再检查一下
            </RpButton>
          </div>
        </RpDialog>
      ) : null}
    </main>
  )
}