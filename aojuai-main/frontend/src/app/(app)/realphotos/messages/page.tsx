'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpEmptyState, RpSkeletonRows, RpTableScroll } from '@/components/realphotos/rp-table'
import { ApiError, apiFetch } from '@/lib/api'
import { formatDateTimeShort } from '@/lib/realphotos-time'

type InboxKind = 'task' | 'recharge' | 'system'

type InboxItem = {
  id: string
  title: string
  body: string
  readAt?: string | null
  createdAt?: string | null
  eventKey?: string
  kind?: InboxKind
  taskId?: string | null
  taskNo?: number | null
  batchId?: string | null
  assetName?: string | null
}

type InboxGroup = {
  key: string
  items: InboxItem[]
  latest: string
}

const PAGE_SIZE = 10
const KIND_TABS: Array<{ value: 'all' | InboxKind; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'task', label: '处理任务' },
  { value: 'recharge', label: '充值' },
  { value: 'system', label: '系统' },
]

function taskLabel(item: InboxItem): string {
  return `处理 #${item.taskNo ?? item.taskId ?? ''}`
}

export default function RealphotosMessagesPage() {
  const [items, setItems] = useState<InboxItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyGroup, setBusyGroup] = useState<string | null>(null)

  const [scope, setScope] = useState('all')
  const [kind, setKind] = useState<'all' | InboxKind>('all')
  const [range, setRange] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  async function reload() {
    setLoading(true)
    try {
      const data = await apiFetch<{ items: InboxItem[]; unreadCount?: number; scope?: string }>(
        '/api/v1/realphotos/inbox',
      )
      setItems(data.items || [])
      setUnreadCount(Number(data.unreadCount || 0))
      setScope(data.scope || 'all')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void reload().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '消息加载失败'))
  }, [])

  async function markAll() {
    try {
      await apiFetch('/api/v1/realphotos/inbox/mark-all-read', { method: 'POST' })
      setMessage('已全部标记已读')
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '全部已读失败')
    }
  }

  async function markGroup(ids: string[], unread: boolean, key = '') {
    if (busyGroup) return
    setBusyGroup(key || ids.join(','))
    try {
      await Promise.all(
        ids.map((id) =>
          apiFetch(`/api/v1/realphotos/inbox/${id}/${unread ? 'unread' : 'read'}`, {
            method: 'POST',
          }),
        ),
      )
      await reload()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '批量标记失败')
    } finally {
      setBusyGroup(null)
    }
  }

  const filteredItems = useMemo(() => {
    const now = Date.now()
    const maxAge = range === '7d' ? 7 * 86400000 : range === '30d' ? 30 * 86400000 : 0
    return items.filter((item) => {
      if (kind !== 'all' && (item.kind || 'system') !== kind) return false
      if (maxAge > 0) {
        const stamp = item.createdAt ? new Date(item.createdAt).getTime() : 0
        if (!stamp || now - stamp > maxAge) return false
      }
      return matchSearchText(
        search,
        item.title,
        item.body,
        item.assetName,
        item.taskNo,
        item.taskId,
        taskLabel(item),
      )
    })
  }, [items, kind, range, search])

  const groups = useMemo(() => {
    const map = new Map<string, InboxGroup>()
    for (const item of filteredItems) {
      const grouped = item.kind === 'task' && item.batchId
      const key = grouped ? `batch:${item.batchId}:${item.title}` : `msg:${item.id}`
      const bucket = map.get(key)
      if (bucket) {
        bucket.items.push(item)
        if (String(item.createdAt || '') > bucket.latest) bucket.latest = String(item.createdAt || '')
      } else {
        map.set(key, { key, items: [item], latest: String(item.createdAt || '') })
      }
    }
    return Array.from(map.values()).sort((a, b) => (a.latest < b.latest ? 1 : -1))
  }, [filteredItems])

  const pageCount = Math.max(1, Math.ceil(groups.length / PAGE_SIZE))
  const visibleGroups = useMemo(
    () => groups.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [groups, page],
  )

  useEffect(() => {
    if (page > pageCount) setPage(pageCount)
  }, [page, pageCount])

  return (
    <main className="space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-medium">消息中心</h1>
        <button className="rp-btn text-sm" type="button" onClick={() => void markAll()}>
          全部已读（未读 {unreadCount}）
        </button>
      </div>
      {scope === 'recharge_only' ? (
        <p className="text-sm text-muted-foreground">订单客服视图：仅商家充值订单通知。</p>
      ) : null}
      <p className="text-sm">{message}</p>
      <section className="rp-card p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {KIND_TABS.map((tab) => (
            <button
              key={tab.value}
              className={`rp-btn rp-btn-sm ${kind === tab.value ? 'bg-muted font-medium' : ''}`}
              type="button"
              onClick={() => {
                setKind(tab.value)
                setPage(1)
              }}
            >
              {tab.label}
            </button>
          ))}
          <select
            className="rp-input"
            value={range}
            onChange={(event) => {
              setRange(event.target.value)
              setPage(1)
            }}
            aria-label="时间范围"
          >
            <option value="all">全部时间</option>
            <option value="7d">近 7 天</option>
            <option value="30d">近 30 天</option>
          </select>
          <ListSearch value={search} placeholder="标题 / 正文 / 任务号" onChange={setSearch} />
        </div>
        <RpTableScroll>
        <table className="rp-table">
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
            {loading ? (
              <RpSkeletonRows colSpan={5} />
            ) : visibleGroups.length === 0 ? (
              <RpEmptyState
                colSpan={5}
                title="暂无消息"
                description="处理任务或充值单有新进展时会在这里提醒；也可以先去看任务详情。"
                action={
                  <Link className="rp-btn rp-btn-primary rp-btn-sm" href="/realphotos/tasks">
                    去任务详情
                  </Link>
                }
              />
            ) : (
              visibleGroups.map((group) => {
                const first = group.items[0]
                const unreadItems = group.items.filter((item) => !item.readAt)
                const readItems = group.items.filter((item) => item.readAt)
                const taskItems = group.items.filter((item) => item.taskId)
                const title =
                  taskItems.length > 1 ? `本批 ${taskItems.length} 张 · ${first.title}` : first.title
                return (
                  <tr key={group.key}>
                    <td className="align-top">{title}</td>
                    <td className="align-top">
                      <div className="space-y-1">
                        {taskItems.length > 0 ? (
                          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
                            {taskItems.slice(0, 4).map((item) => (
                              <Link
                                key={item.id}
                                className="text-primary hover:underline"
                                href={`/realphotos/tasks?taskId=${item.taskId}`}
                              >
                                {taskLabel(item)}
                              </Link>
                            ))}
                            {taskItems.length > 4 ? (
                              <span className="text-muted-foreground">等 {taskItems.length} 条</span>
                            ) : null}
                          </div>
                        ) : null}
                        {first.assetName ? (
                          <div className="text-muted-foreground">{first.assetName}</div>
                        ) : null}
                        <div>{first.body}</div>
                      </div>
                    </td>
                    <td className="align-top">
                      {unreadItems.length > 0 ? `未读 ${unreadItems.length}` : '已读'}
                    </td>
                    <td className="align-top whitespace-nowrap">
                      {formatDateTimeShort(group.latest)}
                    </td>
                    <td className="align-top space-y-1 whitespace-nowrap">
                      {unreadItems.length > 0 ? (
                        <button
                          className="rp-btn rp-btn-sm"
                          type="button"
                          disabled={Boolean(busyGroup)}
                          onClick={() => void markGroup(unreadItems.map((item) => item.id), false, group.key)}
                        >
                          {busyGroup === group.key ? '处理中…' : '标为已读'}
                        </button>
                      ) : null}
                      {readItems.length > 0 ? (
                        <button
                          className="rp-btn rp-btn-sm"
                          type="button"
                          disabled={Boolean(busyGroup)}
                          onClick={() => void markGroup(readItems.map((item) => item.id), true, group.key)}
                        >
                          {busyGroup === group.key ? '处理中…' : '标为未读'}
                        </button>
                      ) : null}
                      {taskItems.length > 0 ? (
                        <Link
                          className="rp-btn rp-btn-sm"
                          href={`/realphotos/tasks?taskId=${taskItems[0].taskId}`}
                        >
                          查看任务
                        </Link>
                      ) : null}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
        </RpTableScroll>
        <div className="flex items-center gap-2 text-sm">
          <button
            className="rp-btn rp-btn-sm"
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <span>
            第 {page} / {pageCount} 页 · 共 {groups.length} 组 · 每页 {PAGE_SIZE}
          </span>
          <button
            className="rp-btn rp-btn-sm"
            type="button"
            disabled={page >= pageCount || loading}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </button>
        </div>
      </section>
      <p className="text-xs text-muted-foreground">消息保留 30 天；同批次同文案的检测结果会合并为一条。</p>
    </main>
  )
}
