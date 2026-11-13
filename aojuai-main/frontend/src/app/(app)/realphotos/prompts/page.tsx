'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { ApiError, apiFetch } from '@/lib/api'

type Template = {
  id: string
  name: string
  mode: string
  scope: string
  positivePrompt: string
  negativePrompt?: string
}

const PAGE_SIZE = 10

export default function RealphotosPromptsPage() {
  const [items, setItems] = useState<Template[]>([])
  const [name, setName] = useState('')
  const [mode, setMode] = useState('general')
  const [prompt, setPrompt] = useState('')
  const [negative, setNegative] = useState('')
  const [scope, setScope] = useState('tenant')
  const [message, setMessage] = useState('')
  const [page, setPage] = useState(1)
  const [roleHint, setRoleHint] = useState('')
  const [search, setSearch] = useState('')

  async function reload() {
    const data = await apiFetch<{ items: Template[] }>('/api/v1/realphotos/prompt-templates')
    setItems(data.items || [])
  }

  useEffect(() => {
    void reload().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '模板加载失败'))
    void apiFetch<{ roleCodes?: string[] }>('/api/v1/realphotos/me')
      .then((data) => {
        const roles = data.roleCodes || []
        setRoleHint(roles.join(','))
        if (roles.includes('rp_admin') || roles.includes('admin')) setScope('platform')
        else setScope('tenant')
      })
      .catch(() => undefined)
  }, [])

  const filteredItems = useMemo(
    () => items.filter((item) => matchSearchText(search, item.name, item.mode, item.scope, item.positivePrompt)),
    [items, search],
  )
  const pageCount = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE))
  const pageItems = useMemo(
    () => filteredItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filteredItems, page],
  )
  const isAdmin = roleHint.includes('rp_admin') || roleHint.includes('admin')

  async function save() {
    try {
      await apiFetch('/api/v1/realphotos/prompt-templates', {
        method: 'POST',
        body: JSON.stringify({
          name,
          mode,
          positivePrompt: prompt,
          negativePrompt: negative,
          scope: isAdmin ? scope : 'tenant',
        }),
      })
      setMessage('已保存模板。选用不扣积分。优化主路径在生图表单。')
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">AI 提示词模板</h1>
      <p className="text-sm">{message}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">新建</h2>
        <label className="block text-sm">
          名称
          <input className="mt-1 block w-full max-w-md border px-2 py-1" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="block text-sm">
          适用模式
          <select className="mt-1 block border px-2 py-1" value={mode} onChange={(event) => setMode(event.target.value)}>
            <option value="general">通用</option>
            <option value="text_to_image">文生图</option>
            <option value="image_to_image">图生图</option>
          </select>
        </label>
        {isAdmin ? (
          <label className="block text-sm">
            范围
            <select className="mt-1 block border px-2 py-1" value={scope} onChange={(event) => setScope(event.target.value)}>
              <option value="tenant">租户</option>
              <option value="platform">平台</option>
            </select>
          </label>
        ) : null}
        <label className="block text-sm">
          正向提示词
          <textarea className="mt-1 block w-full max-w-md border px-2 py-1" rows={2} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        </label>
        <label className="block text-sm">
          负向提示词
          <textarea className="mt-1 block w-full max-w-md border px-2 py-1" rows={2} value={negative} onChange={(event) => setNegative(event.target.value)} />
        </label>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void save()}>
          保存模板
        </button>
      </section>
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <ListSearch
            value={search}
            placeholder="名称 / 模式 / 提示词"
            onChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
          />
          <span>
            第 {page} / {pageCount} 页 · 共 {filteredItems.length}
          </span>
          <button className="border px-2 py-1" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            上一页
          </button>
          <button className="border px-2 py-1" type="button" disabled={page >= pageCount} onClick={() => setPage((p) => p + 1)}>
            下一页
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left">名称</th>
              <th className="text-left">适用模式</th>
              <th className="text-left">正向</th>
              <th className="text-left">负向</th>
              <th className="text-left">范围</th>
            </tr>
          </thead>
          <tbody>
            {pageItems.length === 0 ? (
              <tr>
                <td colSpan={5}>暂无模板</td>
              </tr>
            ) : (
              pageItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{item.mode}</td>
                  <td className="max-w-xs truncate">{item.positivePrompt}</td>
                  <td className="max-w-xs truncate">{item.negativePrompt || ''}</td>
                  <td>{item.scope}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  )
}
