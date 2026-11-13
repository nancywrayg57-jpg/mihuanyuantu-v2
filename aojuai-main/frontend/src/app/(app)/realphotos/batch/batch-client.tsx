'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import { gpsSubmitGuard } from '@/lib/realphotos-gps-submit'
import { deviceTypeLabel } from '@/lib/realphotos-labels'
import { inspectLocalFile } from '@/lib/realphotos-s1'

type Preset = {
  code: string
  model: string
  deviceType: string
  brand: string
  gpsWritable?: boolean
  gpsWillSkip?: boolean
  gpsWritableReason?: string
  gpsMode?: string
}

type PendingAsset = { id: string; previewUrl: string }

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
      let assets: { id: string; objectKey?: string }[] = []
      try {
        const data = await apiFetch<{ items: { id: string; objectKey?: string }[] }>(
          '/api/v1/realphotos/assets',
        )
        assets = data.items || []
      } catch {
        if (!cancelled) setNotice((prev) => `${prev}；资源列表加载失败，缩略图暂不可用`)
        return
      }
      const byId = new Map(assets.map((item) => [item.id, item]))
      let thumbFail = 0
      for (const id of ids) {
        if (cancelled) return
        const objectKey = byId.get(id)?.objectKey
        if (!objectKey) {
          thumbFail += 1
          continue
        }
        try {
          const blob = await apiFetchBlob(`/api/v1/realphotos/gateway/objects/${objectKey}`)
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
      if (!cancelled && thumbFail > 0) {
        setNotice((prev) => `${prev}；缩略图加载失败 ${thumbFail} 张（不阻断提交）`)
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
    try {
      const data = await apiFetch<{ id: string }>('/api/v1/realphotos/assets', { method: 'POST', body })
      const previewUrl = URL.createObjectURL(file)
      setLibrary((prev) => {
        if (prev.length >= 10) return prev
        if (prev.some((item) => item.id === data.id)) return prev
        return [...prev, { id: data.id, previewUrl }]
      })
      setNotice(`已入库资源 ${data.id}，并加入本批待处理`)
      setFile(null)
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '上传失败')
    }
  }

  async function submitBatch() {
    if (frozen) {
      setNotice('账号已因预审冻结，不能提交处理')
      return
    }
    if (!presetCode || library.length < 1 || library.length > 10) {
      setNotice('须先选择库内资源 1–10 张，并完成类型→品牌→型号')
      return
    }
    if (gpsSubmitBlocked) {
      setNotice(`所选预设 GPS 不可用，已拦截提交：${gpsGuard.blockReason}`)
      return
    }
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
      setNotice(`批次 ${data.batchId} 已提交，共 ${data.tasks.length} 张。到任务详情查看。`)
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '批次提交失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">批量原图</h1>
      {frozen ? (
        <p className="text-sm text-destructive">账号已冻结：可查看历史，不能提交新处理。</p>
      ) : null}
      <p className="text-sm">{notice}</p>
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">设备预设（类型 → 品牌 → 型号）</h2>
          <ListSearch value={presetSearch} placeholder="型号 / 品牌 / 编码" onChange={setPresetSearch} />
        </div>
        <div className="flex flex-wrap gap-3 text-sm">
          <label>
            类型
            <select
              className="mt-1 block border px-2 py-1"
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
              className="mt-1 block border px-2 py-1"
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
              className="mt-1 block border px-2 py-1"
              value={presetCode}
              onChange={(event) => setPresetCode(event.target.value)}
            >
              {models.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.model}（{item.code}）
                </option>
              ))}
            </select>
          </label>
        </div>
        {gpsSubmitBlocked ? (
          <p className="text-sm text-destructive">GPS 不可用，已禁止提交：{gpsGuard.blockReason}</p>
        ) : null}
        {!gpsSubmitBlocked && gpsSkipHint ? (
          <p className="text-sm text-amber-700 dark:text-amber-400">将跳过 GPS：{gpsSkipHint}</p>
        ) : null}
      </section>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">待处理图片（库内资源）</h2>
        <p className="text-sm text-muted-foreground">
          <Link className="underline" href="/realphotos/library">
            打开图片资源勾选
          </Link>
        </p>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label>
            本地辅助入库
            <input
              className="mt-1 block"
              type="file"
              accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              onChange={(event) => void onFile(event.target.files?.[0] || null)}
            />
          </label>
          <button className="border px-3 py-1" type="button" disabled={frozen} onClick={() => void uploadToLibrary()}>
            上传并加入本批
          </button>
          <button
            className="border px-3 py-1"
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
            className="border px-3 py-1"
            type="button"
            disabled={frozen || gpsSubmitBlocked}
            onClick={() => void submitBatch()}
          >
            开始处理
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left">缩略图</th>
              <th className="text-left">资源 id</th>
              <th className="text-left">张数</th>
            </tr>
          </thead>
          <tbody>
            {library.length === 0 ? (
              <tr>
                <td colSpan={3}>还没有库内资源。不能提交空批。</td>
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
                  <td>{item.id}</td>
                  <td>{index === 0 ? `${library.length} / 10` : ''}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  )
}
