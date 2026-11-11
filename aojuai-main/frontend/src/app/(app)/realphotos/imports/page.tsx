'use client'

import { useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type ImportResult = {
  imported?: number
  failed?: Array<{ index: number; code: string; message: string }>
  formalSupplier?: boolean
  stagingAllowed?: boolean
  strategy?: string
  creditsCharged?: number
}

export default function RealphotosImportsPage() {
  const [payload, setPayload] = useState('')
  const [message, setMessage] = useState('')
  const [fileName, setFileName] = useState('')

  async function submitText() {
    try {
      const data = await apiFetch<ImportResult>('/api/v1/realphotos/resource-imports', {
        method: 'POST',
        body: JSON.stringify({ payload }),
      })
      setMessage(summarize(data))
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '导入失败')
    }
  }

  async function submitFile(file: File | null) {
    if (!file) {
      setMessage('请选择 JSON 文件')
      return
    }
    try {
      const body = new FormData()
      body.append('file', file)
      const data = await apiFetch<ImportResult>('/api/v1/realphotos/resource-imports/files', {
        method: 'POST',
        body,
      })
      setMessage(summarize(data))
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '导入失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">URL 导入</h1>
      <p className="text-sm text-muted-foreground">
        联调图床可导入；正式供应商未齐。仅允许已授权临时图床主机上的 /images/ 地址；不合格逐条拒绝，合格继续；不扣处理积分、不创建处理任务。
      </p>
      <p className="text-sm">{message}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">粘贴文本（每行 URL 或 JSON 数组）</h2>
        <textarea
          className="block w-full max-w-xl border px-2 py-1 text-sm"
          rows={6}
          value={payload}
          onChange={(event) => setPayload(event.target.value)}
        />
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void submitText()}>
          提交导入
        </button>
      </section>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">上传 JSON 文件</h2>
        <input
          className="block text-sm"
          type="file"
          accept="application/json,.json"
          onChange={(event) => {
            const file = event.target.files?.[0] ?? null
            setFileName(file?.name || '')
            void submitFile(file)
          }}
        />
        {fileName ? <p className="text-xs text-muted-foreground">{fileName}</p> : null}
      </section>
    </main>
  )
}

function summarize(data: ImportResult | null | undefined) {
  if (!data) {
    return '导入失败'
  }
  const imported = Number(data.imported || 0)
  const failed = Array.isArray(data.failed) ? data.failed : []
  if (imported <= 0 && failed.length === 0) {
    return '未导入'
  }
  if (imported <= 0) {
    const reasons = failed
      .slice(0, 5)
      .map((row) => `#${row.index + 1} ${row.code}:${row.message}`)
      .join('；')
    return `未导入（失败 ${failed.length}）：${reasons}`
  }
  if (failed.length === 0) {
    return `已入库 ${imported} 条（联调；正式供应商未齐）`
  }
  const reasons = failed
    .slice(0, 5)
    .map((row) => `#${row.index + 1} ${row.code}:${row.message}`)
    .join('；')
  return `已入库 ${imported} 条；失败 ${failed.length}：${reasons}`
}
