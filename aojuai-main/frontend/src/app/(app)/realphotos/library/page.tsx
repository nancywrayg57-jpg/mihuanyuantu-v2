'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type Asset = { id: string; originKind: string; width: number; height: number; byteSize: number }

export default function RealphotosLibraryPage() {
  const [items, setItems] = useState<Asset[]>([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    void apiFetch<{ items: Asset[] }>('/api/v1/realphotos/assets')
      .then((data) => setItems(data.items || []))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '资源加载失败'))
  }, [])

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">图片资源</h1>
      <p className="text-sm text-muted-foreground">{message}</p>
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className="text-left">资产</th>
            <th className="text-left">来源</th>
            <th className="text-left">尺寸</th>
            <th className="text-left">字节</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={4}>暂无资源</td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.originKind}</td>
                <td>
                  {item.width}×{item.height}
                </td>
                <td>{item.byteSize}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </main>
  )
}
