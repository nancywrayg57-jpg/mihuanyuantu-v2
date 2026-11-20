'use client'

import { useEffect, useState } from 'react'

import { ListSearch } from '@/components/realphotos/list-search'
import { ApiError, apiFetch } from '@/lib/api'
import {
  IMPORT_JSON_EXAMPLE,
  type ImportFailedRow,
  type ImportResult,
  precheckImportPayload,
  summarizeImportResult,
} from '@/lib/realphotos-import'

export default function RealphotosImportsPage() {
  const [payload, setPayload] = useState('')
  const [message, setMessage] = useState('')
  const [failedRows, setFailedRows] = useState<ImportFailedRow[]>([])
  const [fileName, setFileName] = useState('')
  const [frozen, setFrozen] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    void apiFetch<{ preReviewFrozen?: boolean }>('/api/v1/realphotos/me')
      .then((data) => setFrozen(Boolean(data.preReviewFrozen)))
      .catch(() => setFrozen(false))
  }, [])

  function applyResult(data: ImportResult) {
    setFailedRows(Array.isArray(data.failed) ? data.failed : [])
    setMessage(summarizeImportResult(data))
  }

  function applyError(error: unknown) {
    setFailedRows([])
    if (error instanceof ApiError) {
      const code = String(error.code || '')
      if (code === 'SERVICE_NOT_CONFIGURED') {
        setMessage(`导入服务未配置或未启用：${error.message}`)
        return
      }
      if (code === 'INPUT_INVALID') {
        setMessage(`条目不合法：${error.message}`)
        return
      }
      setMessage(error.message || '导入失败')
      return
    }
    setMessage('导入失败')
  }

  async function submitText() {
    if (frozen) {
      setMessage('账号已因预审冻结，不能导入新资源')
      setFailedRows([])
      return
    }
    const issues = precheckImportPayload(payload)
    if (issues.length > 0) {
      setFailedRows(
        issues.map((row) => ({
          index: row.index < 0 ? 0 : row.index,
          code: 'INPUT_INVALID',
          message: row.message,
        })),
      )
      setMessage(
        issues[0]?.index != null && issues[0].index >= 0
          ? `提交前检查未通过（${issues.length}）：${issues
              .slice(0, 5)
              .map((row) => `#${row.index + 1} ${row.message}`)
              .join('；')}`
          : issues[0]?.message || '提交前检查未通过',
      )
      return
    }
    try {
      const data = await apiFetch<ImportResult>('/api/v1/realphotos/resource-imports', {
        method: 'POST',
        body: JSON.stringify({ payload }),
      })
      applyResult(data)
    } catch (error: unknown) {
      applyError(error)
    }
  }

  async function submitFile(file: File | null) {
    if (frozen) {
      setMessage('账号已因预审冻结，不能导入新资源')
      setFailedRows([])
      return
    }
    if (!file) {
      setMessage('请选择 JSON 文件')
      setFailedRows([])
      return
    }
    try {
      const text = await file.text()
      const issues = precheckImportPayload(text)
      if (issues.length > 0) {
        setFailedRows(
          issues.map((row) => ({
            index: row.index < 0 ? 0 : row.index,
            code: 'INPUT_INVALID',
            message: row.message,
          })),
        )
        setMessage(
          issues[0]?.index != null && issues[0].index >= 0
            ? `提交前检查未通过（${issues.length}）：${issues
                .slice(0, 5)
                .map((row) => `#${row.index + 1} ${row.message}`)
                .join('；')}`
            : issues[0]?.message || '提交前检查未通过',
        )
        return
      }
      const body = new FormData()
      body.append('file', file)
      const data = await apiFetch<ImportResult>('/api/v1/realphotos/resource-imports/files', {
        method: 'POST',
        body,
      })
      applyResult(data)
    } catch (error: unknown) {
      applyError(error)
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">URL 导入</h1>
      {frozen ? (
        <p className="text-sm text-amber-800">账号已因预审冻结：导入入口已禁用。</p>
      ) : null}
      <p className="text-sm text-muted-foreground">
        URL/JSON 导入已正式可用。失败时请区分：
        <code className="font-mono">SERVICE_NOT_CONFIGURED</code>（未配置/未启用）、供应商拉取错误、条目非法（如缺少{' '}
        <code className="font-mono">name</code>）。仍受供应商可用性约束。
      </p>
      {message ? <p className="text-sm">{message}</p> : null}
      {failedRows.length > 0 ? (
        <section className="rp-card space-y-2 p-4" data-testid="import-failed-list">
          <h2 className="text-sm font-medium">失败明细（failed[]）</h2>
          <ul className="space-y-1 text-sm text-muted-foreground">
            {failedRows.map((row) => (
              <li key={`${row.index}-${row.code}-${row.message}`}>
                第 {Number(row.index) + 1} 条 · <code className="font-mono">{row.code}</code> · {row.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <section className="rp-card space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">粘贴文本（每行 URL 或 JSON 数组）</h2>
          <ListSearch value={search} placeholder="在已粘贴内容中定位" onChange={setSearch} />
        </div>
        <p className="text-xs text-muted-foreground" data-testid="import-name-hint">
          JSON 数组/对象：每条必须含 <code className="font-mono">name</code> 与 URL 字段（与后端校验一致）；缺{' '}
          <code className="font-mono">name</code> 会返回 <code className="font-mono">INPUT_INVALID / 缺少 name</code>
          。纯 URL 每行一条时不要求 JSON 的 name。
        </p>
        {search.trim() ? (
          <p className="text-xs text-muted-foreground">
            命中{' '}
            {
              payload.split(/\r?\n/).filter((line) => line.toLowerCase().includes(search.trim().toLowerCase()))
                .length
            }{' '}
            行
          </p>
        ) : null}
        <textarea
          className="rp-input block w-full max-w-xl"
          rows={6}
          value={payload}
          disabled={frozen}
          placeholder={IMPORT_JSON_EXAMPLE}
          onChange={(event) => setPayload(event.target.value)}
        />
        <div className="flex flex-wrap gap-2">
          <button
            className="rp-btn text-sm disabled:opacity-50"
            type="button"
            disabled={frozen}
            onClick={() => void submitText()}
          >
            提交导入
          </button>
          <button
            className="rp-btn rp-btn-sm text-sm disabled:opacity-50"
            type="button"
            disabled={frozen}
            onClick={() => setPayload(IMPORT_JSON_EXAMPLE)}
          >
            填入合法 JSON 示例
          </button>
        </div>
        <pre className="max-w-xl overflow-x-auto rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
          {IMPORT_JSON_EXAMPLE}
        </pre>
      </section>
      <section className="rp-card space-y-3 p-4">
        <h2 className="text-sm font-medium">上传 JSON 文件</h2>
        <p className="text-xs text-muted-foreground">
          文件内容须为 UTF-8 JSON 数组；每条对象同样必须含 <code className="font-mono">name</code> 与 URL。
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className={`rp-btn rp-btn-sm ${frozen ? 'pointer-events-none opacity-50' : 'cursor-pointer'}`}>
            选择 JSON 文件
            <input
              className="sr-only"
              type="file"
              accept="application/json,.json"
              disabled={frozen}
              onChange={(event) => {
                const file = event.target.files?.[0] ?? null
                setFileName(file?.name || '')
                void submitFile(file)
              }}
            />
          </label>
          <span className="text-xs text-muted-foreground">{fileName || '未选择文件'}</span>
        </div>
      </section>
    </main>
  )
}
