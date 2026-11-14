'use client'

import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch } from '@/lib/api'
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

export function RealphotosGenerateClient() {
  const searchParams = useSearchParams()
  const initialMode = searchParams.get('mode') === 'image_to_image' ? 'image_to_image' : 'text_to_image'
  const [mode, setMode] = useState(initialMode)
  const [prompt, setPrompt] = useState('')
  const [negative, setNegative] = useState('')
  const [reference, setReference] = useState<File | null>(null)
  const [message, setMessage] = useState('')
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
      toastTask(text, true)
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '提交失败'
      setMessage(text)
      toastTask(text, false)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">生图入库</h1>
      <p className="text-sm">{message}</p>
      <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
        <h2 className="text-sm font-medium">选用 AI 提示词模板</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          <ListSearch value={templateSearch} placeholder="模板名称 / 提示词" onChange={setTemplateSearch} />
          <select className="border px-2 py-1" value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
            <option value="">选择模板</option>
            {filteredTemplates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}（{item.scope}/{item.mode}）
              </option>
            ))}
          </select>
          <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1" type="button" onClick={applyTemplate}>
            选用
          </button>
        </div>
      </section>
      <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-3">
        <h2 className="text-sm font-medium">提交</h2>
        <label className="block text-sm">
          模式
          <select className="mt-1 block border px-2 py-1" value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="text_to_image">文生图</option>
            <option value="image_to_image">图生图</option>
          </select>
        </label>
        {mode === 'image_to_image' ? (
          <label className="block text-sm">
            参考图
            <input
              className="mt-1 block text-sm"
              type="file"
              accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              onChange={(event) => void onReference(event.target.files?.[0] || null)}
            />
          </label>
        ) : null}
        <label className="block text-sm">
          正向提示词
          <textarea
            className="mt-1 block w-full max-w-xl border px-2 py-1"
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
            className="mt-1 block w-full max-w-xl border px-2 py-1"
            rows={2}
            value={negative}
            onChange={(event) => setNegative(event.target.value)}
          />
        </label>
        <div className="flex flex-wrap gap-3 text-sm">
          <label>
            宽
            <input className="ml-1 border px-2 py-1 w-24" value={width} onChange={(e) => setWidth(e.target.value)} />
          </label>
          <label>
            高
            <input className="ml-1 border px-2 py-1 w-24" value={height} onChange={(e) => setHeight(e.target.value)} />
          </label>
          <label className={seedSupported ? '' : 'text-neutral-500'} data-testid="generation-seed">
            {seedSupported ? '可选种子' : '可选种子（当前模型不支持）'}
            <input
              className="ml-1 w-40 border px-2 py-1 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral-500 disabled:opacity-70"
              value={seedSupported ? seed : ''}
              disabled={!seedSupported}
              aria-disabled={!seedSupported}
              data-seed-supported={seedSupported ? 'true' : 'false'}
              onChange={(e) => {
                if (seedSupported) setSeed(e.target.value)
              }}
              placeholder={seedSupported ? '留空则不传' : '不可填写'}
              title={seedNote}
            />
          </label>
          {!seedSupported ? <span className="text-xs text-neutral-500">{seedNote}</span> : null}
        </div>
        {lastSizes ? <p className="text-xs text-muted-foreground">{lastSizes}</p> : null}
        <div className="space-y-2 text-sm">
          <div className="flex flex-wrap gap-2">
            <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1" type="button" onClick={() => void optimize()}>
              提示词优化
            </button>
            <button
              className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 disabled:opacity-40"
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
        <button className="rp-btn rounded-[10px] transition duration-150 hover:-translate-y-px hover:bg-accent hover:shadow-sm disabled:hover:translate-y-0 disabled:hover:shadow-none border px-3 py-1 text-sm" type="button" onClick={() => void submit()}>
          提交生图
        </button>
      </section>
    </main>
  )
}
