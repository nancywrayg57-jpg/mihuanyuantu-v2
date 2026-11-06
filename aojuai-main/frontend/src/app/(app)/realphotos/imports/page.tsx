'use client'

import { useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

export default function RealphotosImportsPage() {
  const [payload, setPayload] = useState('')
  const [message, setMessage] = useState('')

  async function submit() {
    try {
      await apiFetch('/api/v1/realphotos/resource-imports', {
        method: 'POST',
        body: JSON.stringify({ payload }),
      })
      setMessage('已导入')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '导入失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">URL 导入</h1>
      <p className="text-sm text-muted-foreground">缺少供应商合同与接口证据时不外呼，也不写入资源。</p>
      <p className="text-sm">{message}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">导入内容</h2>
        <textarea className="block w-full max-w-xl border px-2 py-1 text-sm" rows={6} value={payload} onChange={(event) => setPayload(event.target.value)} />
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void submit()}>
          提交导入
        </button>
      </section>
    </main>
  )
}
