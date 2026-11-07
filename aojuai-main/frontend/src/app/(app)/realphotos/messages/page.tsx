'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type InboxItem = {
  id: string
  title: string
  body: string
  readAt?: string | null
  createdAt?: string | null
}

export default function RealphotosMessagesPage() {
  const [items, setItems] = useState<InboxItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [message, setMessage] = useState('')

  const [scope, setScope] = useState('all')

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

  async function resend(id: string) {
    try {
      await apiFetch(`/api/v1/realphotos/inbox/${id}/resend`, { method: 'POST' })
      setMessage('已补发站内通知（不重跑任务、不重复扣费）')
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '补发失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-medium">消息中心</h1>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void markAll()}>
          全部已读（未读 {unreadCount}）
        </button>
      </div>
      <p className="text-sm text-muted-foreground">
        按接收账号 + 租户隔离；保留 30 天。无邮件/短信通道。
        {scope === 'recharge_only' ? ' 订单客服视图：仅商家充值订单通知。' : ''}
      </p>
      <p className="text-sm">{message}</p>
      <table className="w-full text-sm">
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
          {items.length === 0 ? (
            <tr>
              <td colSpan={5}>暂无消息</td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>{item.body}</td>
                <td>{item.readAt ? '已读' : '未读'}</td>
                <td>{item.createdAt || ''}</td>
                <td className="space-x-2">
                  {!item.readAt ? (
                    <button className="border px-2 py-0.5" type="button" onClick={() => void markRead(item.id)}>
                      标为已读
                    </button>
                  ) : null}
                  <button className="border px-2 py-0.5" type="button" onClick={() => void resend(item.id)}>
                    补发
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </main>
  )
}
