'use client'

import { useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'
import { inspectLocalFile } from '@/lib/realphotos-s1'

export default function RealphotosGeneratePage() {
  const [mode, setMode] = useState('text_to_image')
  const [prompt, setPrompt] = useState('')
  const [reference, setReference] = useState<File | null>(null)
  const [message, setMessage] = useState('')

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

  async function submit() {
    if (mode === 'image_to_image' && !reference) {
      setMessage('图生图需要一张参考图')
      return
    }
    const fields = {
      mode,
      positivePrompt: prompt,
      width: '1024',
      height: '768',
      quantity: '1',
      idempotencyKey: `ui-gen-${Date.now()}`,
    }
    try {
      if (mode === 'image_to_image' && reference) {
        const body = new FormData()
        for (const [key, value] of Object.entries(fields)) body.set(key, value)
        body.set('reference', reference)
        await apiFetch('/api/v1/realphotos/generation-tasks', { method: 'POST', body })
      } else {
        await apiFetch('/api/v1/realphotos/generation-tasks', {
          method: 'POST',
          body: JSON.stringify({
            ...fields,
            width: 1024,
            height: 768,
            quantity: 1,
          }),
        })
      }
      setMessage('已入库。生图不会自动进入处理。')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '提交失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">生图入库</h1>
      <p className="text-sm text-muted-foreground">
        成功结果只写入图片资源。没有供应商证据时不外呼，也不创建处理任务。
      </p>
      <p className="text-sm">{message}</p>
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
          <input className="mt-1 block w-full max-w-md border px-2 py-1" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void submit()}>
          提交生图
        </button>
      </section>
    </main>
  )
}
