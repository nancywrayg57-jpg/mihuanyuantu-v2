'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { toast } from 'sonner'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch, apiFetchBlob } from '@/lib/api'
import { formatDateTimeShort } from '@/lib/realphotos-time'
import { inspectLocalFile } from '@/lib/realphotos-s1'

type Template = {
  id: string
  name: string
  mode: string
  scope: string
  positivePrompt: string
  negativePrompt?: string
}

type GenerationSeedCapability = {
  modelId?: string
  seed?: string
  seedSupported?: boolean
  seedNote?: string
}

type RecentGeneration = {
  id: string
  taskNo?: number | null
  mode: string
  width: number
  height: number
  quantity: number
  createdAt?: string | null
  items: Array<{ index: number; status: string; assetId?: string | null; actualWidth?: number | null; actualHeight?: number | null }>
}

type RecentAsset = { id: string; objectKey?: string | null; displayName?: string | null }

export function RealphotosGenerateClient() {
  const searchParams = useSearchParams()
  const initialMode = searchParams.get('mode') === 'image_to_image' ? 'image_to_image' : 'text_to_image'
  const [mode, setMode] = useState(initialMode)
  const [prompt, setPrompt] = useState('')
  const [negative, setNegative] = useState('')
  const [reference, setReference] = useState<File | null>(null)
  const [message, setMessage] = useState('')
  // 2026-11-17：提交生图立即给出反馈（生图耗时较长，不能让用户以为没点到）
  const [submitting, setSubmitting] = useState(false)
  const [templates, setTemplates] = useState<Template[]>([])
  const [templateId, setTemplateId] = useState('')
  const [optId, setOptId] = useState<string | null>(null)
  const [originalText, setOriginalText] = useState('')
  const [optimizedText, setOptimizedText] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [width, setWidth] = useState('1024')
  const [height, setHeight] = useState('768')
  const [seed, setSeed] = useState('')
  const [seedSupported, setSeedSupported] = useState(false)
  const [seedNote, setSeedNote] = useState('正在读取模型种子能力')
  const [lastSizes, setLastSizes] = useState('')
  const [templateSearch, setTemplateSearch] = useState('')
  const [recent, setRecent] = useState<RecentGeneration[]>([])
  const [recentAssets, setRecentAssets] = useState<Record<string, RecentAsset>>({})
  const [recentThumbs, setRecentThumbs] = useState<Record<string, string>>({})

  async function loadRecent() {
    const data = await apiFetch<{ items: RecentGeneration[] }>(
      '/api/v1/realphotos/generation-tasks?page=1&page_size=6',
    )
    const rows = data.items || []
    setRecent(rows)
    const assetIds = Array.from(
      new Set(
        rows
          .flatMap((row) => row.items.map((item) => item.assetId))
          .filter((id): id is string => Boolean(id)),
      ),
    )
    if (!assetIds.length) {
      setRecentAssets({})
      return
    }
    const assets = await apiFetch<{ items: RecentAsset[] }>(
      `/api/v1/realphotos/assets?ids=${encodeURIComponent(assetIds.join(','))}`,
    )
    setRecentAssets(
      Object.fromEntries((assets.items || []).map((asset) => [String(asset.id), asset])),
    )
  }

  useEffect(() => {
    void loadRecent().catch(() => undefined)
  }, [])

  useEffect(() => {
    let cancelled = false
    const created: string[] = []
    setRecentThumbs({})
    void (async () => {
      for (const row of recent) {
        const assetId = row.items.find((item) => item.assetId)?.assetId
        const asset = assetId ? recentAssets[String(assetId)] : null
        if (!asset?.objectKey) continue
        try {
          const path = String(asset.objectKey).split('/').map(encodeURIComponent).join('/')
          const blob = await apiFetchBlob(
            `/api/v1/realphotos/gateway/objects/${path}?thumb=160`,
          )
          if (cancelled) return
          const url = URL.createObjectURL(blob)
          created.push(url)
          setRecentThumbs((prev) => ({ ...prev, [row.id]: url }))
        } catch {
          // 缩略图失败时保留占位
        }
      }
    })()
    return () => {
      cancelled = true
      for (const url of created) URL.revokeObjectURL(url)
    }
  }, [recent, recentAssets])

  useEffect(() => {
    setMode(initialMode)
  }, [initialMode])

  const filteredTemplates = useMemo(
    () =>
      templates.filter(
        (item) =>
          (item.mode === 'general' || item.mode === mode) &&
          matchSearchText(templateSearch, item.name, item.mode, item.scope, item.positivePrompt),
      ),
    [templates, mode, templateSearch],
  )

  useEffect(() => {
    void apiFetch<{ items: Template[] }>('/api/v1/realphotos/prompt-templates')
      .then((data) => setTemplates(data.items || []))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    void apiFetch<GenerationSeedCapability>('/api/v1/realphotos/generation-capabilities')
      .then((data) => {
        const supported = data.seedSupported === true
        setSeedSupported(supported)
        setSeedNote(
          data.seedNote || (supported ? '当前模型支持种子，可以填写' : '当前模型不支持种子，不可填写'),
        )
        if (!supported) setSeed('')
      })
      .catch(() => {
        setSeedSupported(false)
        setSeed('')
        setSeedNote('未能读取种子能力，已禁止填写')
      })
  }, [])

  async function onReference(file: File | null) {
    setReference(null)
    if (!file) return
    const inspected = await inspectLocalFile(file)
    if (!inspected.ok) {
      setMessage(inspected.message)
      return
    }
    setReference(file)
    setMessage(`参考图 ${inspected.width}×${inspected.height}，尚未入库`)
  }

  function applyTemplate() {
    const row = templates.find((item) => item.id === templateId)
    if (!row) {
      setMessage('请先选择模板')
      return
    }
    setPrompt(row.positivePrompt || '')
    setNegative(row.negativePrompt || '')
    setConfirmed(false)
    setOptId(null)
    setOriginalText('')
    setOptimizedText('')
    setMessage('已选用模板填入正/负向提示词（不扣积分），可继续改写')
  }

  async function optimize() {
    if (!prompt.trim()) {
      setMessage('请先输入正向提示词再优化')
      return
    }
    try {
      const data = await apiFetch<{
        id: string
        status: string
        originalText: string
        optimizedText: string
      }>('/api/v1/realphotos/prompt-optimizations', {
        method: 'POST',
        body: JSON.stringify({ originalText: prompt }),
      })
      setOptId(data.id)
      setOriginalText(data.originalText)
      setOptimizedText(data.optimizedText)
      setConfirmed(false)
      setMessage(
        data.status === 'succeeded'
          ? '提示词优化完成，请确认后才可用于提交'
          : '提示词优化失败，未扣积分',
      )
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '优化失败')
    }
  }

  async function confirmOpt() {
    if (!optId) {
      setMessage('请先执行提示词优化')
      return
    }
    try {
      await apiFetch(`/api/v1/realphotos/prompt-optimizations/${optId}/confirm`, { method: 'POST' })
      setPrompt(optimizedText)
      setConfirmed(true)
      setMessage('已确认优化文并填入正向提示词')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '确认失败')
    }
  }

  async function submit() {
    if (mode === 'image_to_image' && !reference) {
      const text = '图生图需要一张参考图'
      setMessage(text)
      toastTask(text, false)
      return
    }
    if (optId && optimizedText && !confirmed && prompt === optimizedText) {
      const text = '优化文尚未确认，请先确认或改回原文后再提交'
      setMessage(text)
      toastTask(text, false)
      return
    }
    setSubmitting(true)
    const loadingToast = toast.loading('正在提交生图，请稍候…')
    const seedField = seedSupported && seed.trim() ? seed.trim() : ''
    const fields = {
      mode,
      positivePrompt: prompt,
      negativePrompt: negative,
      width,
      height,
      quantity: '1',
      idempotencyKey: `ui-gen-${Date.now()}`,
      ...(seedField ? { seed: seedField } : {}),
    }
    try {
      let data: {
        requestedWidth?: number
        requestedHeight?: number
        items?: Array<{ actualWidth?: number | null; actualHeight?: number | null; status?: string }>
        supplier?: { seedSent?: boolean; seedNote?: string; requestedSize?: string }
      }
      if (mode === 'image_to_image' && reference) {
        const body = new FormData()
        for (const [key, value] of Object.entries(fields)) body.set(key, value)
        body.set('reference', reference)
        data = await apiFetch('/api/v1/realphotos/generation-tasks', { method: 'POST', body })
      } else {
        data = await apiFetch('/api/v1/realphotos/generation-tasks', {
          method: 'POST',
          body: JSON.stringify({
            ...fields,
            width: Number(width),
            height: Number(height),
            quantity: 1,
          }),
        })
      }
      const stored = (data.items || []).find((item) => item.status === 'stored')
      const sizeNote = stored
        ? `请求 ${data.requestedWidth || width}×${data.requestedHeight || height}；实际 ${stored.actualWidth}×${stored.actualHeight}`
        : `请求 ${width}×${height}`
      setLastSizes(sizeNote)
      const submittedSeedNote = !seedSupported
        ? '当前模型不支持种子，未发送'
        : data.supplier?.seedSent === true
          ? '种子已发送'
          : seedField
            ? data.supplier?.seedNote || '种子未发送'
            : '未填写种子（未发送）'
      const text = `已入库。生图不会自动进入处理。${sizeNote}。${submittedSeedNote}`
      setMessage(text)
      toast.success('生图成功', { id: loadingToast })
      await loadRecent()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '提交失败'
      setMessage(text)
      toast.error(text, { id: loadingToast })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">生图入库</h1>
      <p className="text-sm">{message}</p>
      <section className="rp-card space-y-3 p-4">
        <h2 className="text-sm font-medium">选用 AI 提示词模板</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          <ListSearch value={templateSearch} placeholder="模板名称 / 提示词" onChange={setTemplateSearch} />
          <select className="rp-input" value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
            <option value="">选择模板</option>
            {filteredTemplates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}（{item.scope}/{item.mode}）
              </option>
            ))}
          </select>
          <button className="rp-btn" type="button" onClick={applyTemplate}>
            选用
          </button>
        </div>
      </section>
      <section className="rp-card space-y-3 p-4">
        <h2 className="text-sm font-medium">提交</h2>
        <label className="block text-sm">
          模式
          <select className="rp-input mt-1 block" value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="text_to_image">文生图</option>
            <option value="image_to_image">图生图</option>
          </select>
        </label>
        {mode === 'image_to_image' ? (
          <div className="block text-sm">
            <span className="mb-1 block">参考图</span>
            <div className="flex items-center gap-2">
              <label className="rp-btn rp-btn-sm cursor-pointer">
                选择文件
                <input
                  className="sr-only"
                  type="file"
                  accept="image/jpeg,image/png,.jpg,.jpeg,.png"
                  onChange={(event) => void onReference(event.target.files?.[0] || null)}
                />
              </label>
              <span className="max-w-[14rem] truncate text-xs text-muted-foreground">
                {reference?.name || '未选择文件'}
              </span>
            </div>
          </div>
        ) : null}
        <label className="block text-sm">
          正向提示词
          <textarea
            className="rp-input mt-1 block w-full max-w-xl"
            rows={3}
            value={prompt}
            onChange={(event) => {
              setPrompt(event.target.value)
              if (confirmed) setConfirmed(false)
            }}
          />
        </label>
        <label className="block text-sm">
          负向提示词
          <textarea
            className="rp-input mt-1 block w-full max-w-xl"
            rows={2}
            value={negative}
            onChange={(event) => setNegative(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap gap-3 text-sm">
          <label>
            宽
            <input className="rp-input ml-1 w-24" value={width} onChange={(e) => setWidth(e.target.value)} />
          </label>
          <label>
            高
            <input className="rp-input ml-1 w-24" value={height} onChange={(e) => setHeight(e.target.value)} />
          </label>
          {seedSupported ? (
            <label data-testid="generation-seed">
              可选种子
              <input
                className="rp-input ml-1 w-40"
                value={seed}
                data-seed-supported="true"
                onChange={(e) => setSeed(e.target.value)}
                placeholder="留空则不传"
                title={seedNote}
              />
            </label>
          ) : null}
        </div>
        {lastSizes ? <p className="text-xs text-muted-foreground">{lastSizes}</p> : null}
        <div className="space-y-2 text-sm">
          <div className="flex flex-wrap gap-2">
            <button className="rp-btn" type="button" onClick={() => void optimize()}>
              提示词优化
            </button>
            <button
              className="rp-btn disabled:opacity-40"
              type="button"
              disabled={!optId || !optimizedText}
              onClick={() => void confirmOpt()}
            >
              确认优化文
            </button>
          </div>
          {originalText || optimizedText ? (
            <div className="space-y-1 border p-2">
              <p>原文：{originalText}</p>
              <p>优化文：{optimizedText}</p>
              <p className="text-xs text-muted-foreground">
                {confirmed ? '已确认，可用于提交' : '未确认前不得把优化文当作最终提交稿（可手改原文）'}
              </p>
            </div>
          ) : null}
        </div>
        <div className="flex justify-end border-t pt-3">
          <button
            className="rp-btn rp-btn-primary rp-btn-lg"
            type="button"
            disabled={submitting}
            onClick={() => void submit()}
          >
            {submitting ? '提交中…' : '提交生图'}
          </button>
        </div>
      </section>

      <section className="rp-card space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-medium">最近生成</h2>
          <button className="rp-btn rp-btn-sm" type="button" onClick={() => void loadRecent()}>
            刷新
          </button>
        </div>
        <table className="rp-table">
          <thead>
            <tr>
              <th className="text-left">缩略图</th>
              <th className="text-left">任务</th>
              <th className="text-left">尺寸</th>
              <th className="text-left">时间</th>
              <th className="text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {recent.length === 0 ? (
              <tr>
                <td className="rp-empty" colSpan={5}>
                  还没有生成记录。提交后会在这里显示最近 6 条结果。
                </td>
              </tr>
            ) : (
              recent.map((row) => {
                const assetId = row.items.find((item) => item.assetId)?.assetId || null
                const asset = assetId ? recentAssets[String(assetId)] : null
                return (
                  <tr key={row.id}>
                    <td>
                      {recentThumbs[row.id] ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={recentThumbs[row.id]}
                          alt=""
                          className="h-14 w-14 rounded border object-cover"
                        />
                      ) : (
                        <span className="inline-block h-14 w-14 border text-center leading-[3.5rem] text-xs">图</span>
                      )}
                    </td>
                    <td>
                      <div>{`生图 #${row.taskNo ?? row.id}`}</div>
                      <div className="max-w-[16rem] truncate text-xs text-muted-foreground" title={asset?.displayName || ''}>
                        {asset?.displayName || '—'}
                      </div>
                    </td>
                    <td>
                      {row.width}×{row.height}
                    </td>
                    <td className="whitespace-nowrap">{formatDateTimeShort(row.createdAt) || '—'}</td>
                    <td>
                      {assetId ? (
                        <Link className="rp-btn rp-btn-sm" href={`/realphotos/batch?assetIds=${assetId}`}>
                          去处理
                        </Link>
                      ) : (
                        <span className="text-xs text-muted-foreground">无可处理资源</span>
                      )}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </section>
    </main>
  )
}
