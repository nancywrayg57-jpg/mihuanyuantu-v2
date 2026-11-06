'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type Template = { id: string; name: string; mode: string; scope: string; positivePrompt: string }

export default function RealphotosPromptsPage() {
  const [items, setItems] = useState<Template[]>([])
  const [name, setName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [message, setMessage] = useState('')

  async function reload() {
    const data = await apiFetch<{ items: Template[] }>('/api/v1/realphotos/prompt-templates')
    setItems(data.items || [])
  }

  useEffect(() => {
    void reload().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '模板加载失败'))
  }, [])

  async function save() {
    try {
      await apiFetch('/api/v1/realphotos/prompt-templates', {
        method: 'POST',
        body: JSON.stringify({ name, mode: 'general', positivePrompt: prompt, scope: 'tenant' }),
      })
      setMessage('已保存模板。选用不扣积分。')
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    }
  }

  async function optimize() {
    try {
      await apiFetch('/api/v1/realphotos/prompt-optimizations', {
        method: 'POST',
        body: JSON.stringify({ originalText: prompt }),
      })
      setMessage('优化完成')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '优化失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">提示词模板</h1>
      <p className="text-sm">{message}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">新建</h2>
        <label className="block text-sm">
          名称
          <input className="mt-1 block w-full max-w-md border px-2 py-1" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="block text-sm">
          正向提示词
          <input className="mt-1 block w-full max-w-md border px-2 py-1" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <div className="space-x-2">
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void save()}>
            保存模板
          </button>
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void optimize()}>
            提示词优化
          </button>
        </div>
      </section>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">名称</th>
            <th className="text-left">模式</th>
            <th className="text-left">范围</th>
            <th className="text-left">正向</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={4}>暂无模板</td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td>{item.mode}</td>
                <td>{item.scope}</td>
                <td>{item.positivePrompt}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </main>
  )
}
