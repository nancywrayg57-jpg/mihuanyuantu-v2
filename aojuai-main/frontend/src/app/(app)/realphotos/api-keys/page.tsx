'use client'

import { useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

export default function RealphotosApiKeysPage() {
  const [name, setName] = useState('ERP')
  const [plaintext, setPlaintext] = useState('')
  const [message, setMessage] = useState('')

  async function createKey() {
    try {
      const data = await apiFetch<{ apiKey: string; keyPrefix: string }>('/api/v1/realphotos/business-api-keys', {
        method: 'POST',
        body: JSON.stringify({ name, scopes: ['image_processing'] }),
      })
      setPlaintext(data.apiKey)
      setMessage(`已创建，前缀 ${data.keyPrefix}。明文只显示这一次。此 Key 不能调用生图、提示词优化或 URL 导入。`)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '创建失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">业务 API</h1>
      <p className="text-sm text-muted-foreground">能力名固定为 image_processing。不能用这把 Key 再创建 Key。</p>
      <p className="text-sm">{message}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">签发</h2>
        <label className="block text-sm">
          名称
          <input className="mt-1 block w-full max-w-md border px-2 py-1" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void createKey()}>
          创建凭证
        </button>
        {plaintext ? <p className="break-all text-sm">明文：{plaintext}</p> : null}
      </section>
    </main>
  )
}