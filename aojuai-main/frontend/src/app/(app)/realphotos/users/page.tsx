'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type Account = { id: number; username: string; status: number }

export default function RealphotosUsersPage() {
  const [items, setItems] = useState<Account[]>([])
  const [pageSize, setPageSize] = useState(10)
  const [message, setMessage] = useState('')

  useEffect(() => {
    void apiFetch<{ items: Account[]; pageSize: number }>('/api/v1/realphotos/managed-users')
      .then((data) => {
        setItems(data.items)
        setPageSize(data.pageSize)
      })
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '用户读取失败'))
  }, [])

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">用户管理</h1>
      <p className="text-sm text-muted-foreground">每页 {pageSize} 条。密码只保存散列，不出现在本页。</p>
      <p className="text-sm">{message}</p>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="border px-2 py-1 text-left">编号</th>
            <th className="border px-2 py-1 text-left">登录名</th>
            <th className="border px-2 py-1 text-left">状态</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="border px-2 py-1">{item.id}</td>
              <td className="border px-2 py-1">{item.username}</td>
              <td className="border px-2 py-1">{item.status === 1 ? '启用' : '停用'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}
