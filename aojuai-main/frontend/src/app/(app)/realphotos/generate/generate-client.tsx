'use client'

import { useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'

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
  const [lastSizes, setLastSizes] = useState('')

  useEffect(() => {
    setMode(initialMode)
  }, [initialMode])

  useEffect(() => {
    void apiFetch<{ items: Template[] }>('/api/v1/realphotos/prompt-templates')
      .then((data) => setTemplates(data.items || []))
      .catch(() => undefined)
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
      setMessage('图生图需要一张参考图')
      return
    }
    if (optId && optimizedText && !confirmed && prompt === optimizedText) {
      setMessage('优化文尚未确认，请先确认或改回原文后再提交')
      return
    }
    const fields = {
      mode,
      positivePrompt: prompt,
      negativePrompt: negative,
      width,
      height,
      quantity: '1',
      idempotencyKey: `ui-gen-${Date.now()}`,
      ...(seed.trim() ? { seed: seed.trim() } : {}),
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
            ...(seed.trim() ? { seed: seed.trim() } : {}),
          }),
        })
      }
      const stored = (data.items || []).find((item) => item.status === 'stored')
      const sizeNote = stored
        ? `请求 ${data.requestedWidth || width}×${data.requestedHeight || height}；实际 ${stored.actualWidth}×${stored.actualHeight}`
        : `请求 ${width}×${height}`
      setLastSizes(sizeNote)
      const seedNote =
        data.supplier?.seedSent === true
          ? '种子已发送'
          : seed.trim()
            ? data.supplier?.seedNote || '种子未发送'
            : '未填写种子（未发送）'
      setMessage(`已入库。生图不会自动进入处理。${sizeNote}。${seedNote}`)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '提交失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">生图入库</h1>
      <p className="text-sm text-muted-foreground">
        成功结果只写入图片资源，不创建处理任务。未配置时不外呼。客户文案固定「提示词优化」。
      </p>
      <p className="text-sm">{message}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">选用 AI 提示词模板</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          <select className="border px-2 py-1" value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
            <option value="">选择模板</option>
            {templates
              .filter((item) => item.mode === 'general' || item.mode === mode)
              .map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}（{item.scope}/{item.mode}）
                </option>
              ))}
          </select>
          <button className="border px-3 py-1" type="button" onClick={applyTemplate}>
            选用
          </button>
        </div>
      </section>
      <section className="space-y-3">
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
          <label>
            可选种子
            <input
              className="ml-1 border px-2 py-1 w-40"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="留空则不传"
            />
          </label>
          <p className="w-full text-xs text-muted-foreground">
            当前渠道不支持种子：填写后会返回明确拒绝，不会假装已发送。
          </p>
        </div>
        {lastSizes ? <p className="text-xs text-muted-foreground">{lastSizes}</p> : null}
        <div className="space-y-2 text-sm">
          <div className="flex flex-wrap gap-2">
            <button className="border px-3 py-1" type="button" onClick={() => void optimize()}>
              提示词优化
            </button>
            <button
              className="border px-3 py-1 disabled:opacity-40"
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
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void submit()}>
          提交生图
        </button>
      </section>
    </main>
  )
}
