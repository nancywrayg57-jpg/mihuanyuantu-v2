'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { ApiError, apiFetch } from '@/lib/api'
import { formatDateTimeShort } from '@/lib/realphotos-time'

type InboxItem = {
  id: string
  title: string
  body: string
  readAt?: string | null
  createdAt?: string | null
}

const PAGE_SIZE = 10

export default function RealphotosMessagesPage() {
  const [items, setItems] = useState<InboxItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [message, setMessage] = useState('')

  const [scope, setScope] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  async function reload() {
    const data = await apiFetch<{ items: InboxItem[]; unreadCount?: number; scope?: string }>(
      '/api/v1/realphotos/inbox',
    )
    setItems(data.items || [])
    setUnreadCount(Number(data.unreadCount || 0))
    setScope(data.scope || 'all')
  }

  useEffect(() => {
    void reload().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '消息加载失败'))
  }, [])

  async function markRead(id: string) {
    try {
      await apiFetch(`/api/v1/realphotos/inbox/${id}/read`, { method: 'POST' })
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '标记已读失败')
    }
  }

  async function markAll() {
    try {
      await apiFetch('/api/v1/realphotos/inbox/mark-all-read', { method: 'POST' })
      setMessage('已全部标记已读')
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '全部已读失败')
    }
  }

  async function markUnread(id: string) {
    try {
      await apiFetch(`/api/v1/realphotos/inbox/${id}/unread`, { method: 'POST' })
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '标为未读失败')
    }
  }

  const filteredItems = useMemo(
    () => items.filter((item) => matchSearchText(search, item.id, item.title, item.body)),
    [items, search],
  )
  const pageCount = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE))
  const visibleItems = useMemo(
    () => filteredItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filteredItems, page],
  )

  useEffect(() => {
    if (page > pageCount) setPage(pageCount)
  }, [page, pageCount])

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-medium">消息中心</h1>
        <button className="rp-btn border px-3 py-1 text-sm" type="button" onClick={() => void markAll()}>
          全部已读（未读 {unreadCount}）
        </button>
      </div>
      <p className="text-sm text-muted-foreground">
        消息保留30天
        {scope === 'recharge_only' ? ' 订单客服视图：仅商家充值订单通知。' : ''}
      </p>
      <p className="text-sm">{message}</p>
      <section className="rp-card rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
      <ListSearch value={search} placeholder="标题 / 正文" onChange={setSearch} />
      <table className="rp-table w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">标题</th>
            <th className="text-left">内容</th>
            <th className="text-left">状态</th>
            <th className="text-left">时间</th>
            <th className="text-left">操作</th>
          </tr>
        </thead>
        <tbody>
          {visibleItems.length === 0 ? (
            <tr>
              <td colSpan={5}>暂无消息</td>
            </tr>
          ) : (
            visibleItems.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>{item.body}</td>
                <td>{item.readAt ? '已读' : '未读'}</td>
                <td>{formatDateTimeShort(item.createdAt)}</td>
                <td className="space-x-2">
                  {!item.readAt ? (
                    <button className="rp-btn border px-2 py-0.5" type="button" onClick={() => void markRead(item.id)}>
                      标为已读
                    </button>
                  ) : null}
                  <button className="rp-btn border px-2 py-0.5" type="button" onClick={() => void markUnread(item.id)}>
                    标为未读
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      <div className="flex items-center gap-2 text-sm">
        <button
          className="rp-btn border px-2 py-1"
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          上一页
        </button>
        <span>
          第 {page} / {pageCount} 页 · 共 {filteredItems.length} 条 · 每页 {PAGE_SIZE}
        </span>
        <button
          className="rp-btn border px-2 py-1"
          type="button"
          disabled={page >= pageCount}
          onClick={() => setPage((p) => p + 1)}
        >
          下一页
        </button>
      </div>
      </section>
    </main>
  )
}
