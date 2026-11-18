'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { RpButton } from '@/components/realphotos/rp-button'
import { RpDialog, RpEmpty, RpTable, RpTh } from '@/components/realphotos/rp-table'
import { toastTask } from '@/components/realphotos/surface'
import { ApiError, apiFetch } from '@/lib/api'
import { formatDateTimeShort } from '@/lib/realphotos-time'

type ContractMeta = {
  title?: string
  version?: string
  description?: string
  authHeader?: string
  scope?: string
  downloadPath?: string
  artifactRelativePath?: string
}

type BusinessKey = {
  id: string
  name: string
  keyPrefix: string
  maskedKey: string
  scopes: string[]
  status: 'active' | 'expired'
  createdAt?: string | null
  lastUsedAt?: string | null
  expiresAt?: string | null
}

type PlaintextKey = {
  value: string
  name: string
  rotatedFrom?: string
}

const EXAMPLE_BATCH = `curl -X POST "$BASE/api/v1/realphotos/processing-batches" \\
  -H "X-API-Key: $KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"assetIds":[123],"presetCode":"iphone-15-pro","idempotencyKey":"erp-20261118-001"}'`

export default function RealphotosApiKeysPage() {
  const [name, setName] = useState('ERP')
  const [keys, setKeys] = useState<BusinessKey[]>([])
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [plaintext, setPlaintext] = useState<PlaintextKey | null>(null)
  const [message, setMessage] = useState('')
  const [contract, setContract] = useState<ContractMeta | null>(null)
  const [search, setSearch] = useState('')
  const [confirm, setConfirm] = useState<{ type: 'revoke' | 'rotate'; key: BusinessKey } | null>(null)

  async function load() {
    setLoading(true)
    try {
      const data = await apiFetch<{ items: BusinessKey[] }>('/api/v1/realphotos/business-api-keys')
      setKeys(data.items || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void apiFetch<ContractMeta>('/api/v1/realphotos/contracts/image-processing')
      .then((data) => setContract(data))
      .catch(() => setContract(null))
    void load().catch((error: unknown) =>
      setMessage(error instanceof ApiError ? error.message : '凭证列表加载失败'),
    )
  }, [])

  const visibleKeys = useMemo(
    () =>
      keys.filter((key) =>
        matchSearchText(search, key.name, key.keyPrefix, key.status === 'active' ? '正常' : '已过期'),
      ),
    [keys, search],
  )

  async function createKey() {
    if (busy) return
    if (!name.trim()) {
      setMessage('请先填写凭证名称，例如「ERP 对接」。')
      return
    }
    setBusy(true)
    try {
      const data = await apiFetch<BusinessKey & { apiKey: string }>(
        '/api/v1/realphotos/business-api-keys',
        {
          method: 'POST',
          body: JSON.stringify({ name: name.trim(), scopes: ['image_processing'] }),
        },
      )
      setPlaintext({ value: data.apiKey, name: data.name })
      setMessage(`已创建「${data.name}」。明文只显示这一次，请立即复制并保存到安全位置。`)
      toastTask('业务凭证已创建，请复制明文', true)
      await load()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '创建失败'
      setMessage(text)
      toastTask(text, false)
    } finally {
      setBusy(false)
    }
  }

  async function confirmAction() {
    if (!confirm || busy) return
    setBusy(true)
    const target = confirm.key
    try {
      if (confirm.type === 'revoke') {
        await apiFetch(`/api/v1/realphotos/business-api-keys/${target.id}`, { method: 'DELETE' })
        setMessage(`已吊销「${target.name}」。使用该凭证的系统会立即收到 401。`)
        toastTask('凭证已吊销', true)
      } else {
        const data = await apiFetch<BusinessKey & { apiKey: string }>(
          `/api/v1/realphotos/business-api-keys/${target.id}/rotate`,
          { method: 'POST' },
        )
        setPlaintext({ value: data.apiKey, name: data.name, rotatedFrom: target.id })
        setMessage(`已重新生成「${data.name}」，旧凭证已吊销。新明文只显示这一次。`)
        toastTask('凭证已重新生成，请复制新明文', true)
      }
      setConfirm(null)
      await load()
    } catch (error: unknown) {
      const text = error instanceof ApiError ? error.message : '操作失败'
      setMessage(text)
      toastTask(text, false)
    } finally {
      setBusy(false)
    }
  }

  async function copyPlaintext() {
    if (!plaintext) return
    try {
      await navigator.clipboard.writeText(plaintext.value)
      setMessage('明文已复制到剪贴板。关闭弹窗后无法再次查看。')
    } catch {
      setMessage('浏览器拒绝了剪贴板写入，请手动选中明文复制。')
    }
  }

  const origin =
    typeof window === 'undefined' ? '' : window.location.origin
  const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || '').replace(/\/+$/, '') || origin
  const example = EXAMPLE_BATCH.replace('$BASE', apiBase)

  return (
    <main className="space-y-6 p-6">
      <RpPageHeader
        title="业务 API"
        description="给 ERP / 自建系统签发业务 API 凭证；明文只在创建或重新生成时显示一次，之后不可再查看。"
      />
      <p className="text-sm text-muted-foreground">{message}</p>

      <section className="rp-card space-y-3 p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium">我的凭证</h2>
            <p className="text-xs text-muted-foreground">
              共 {keys.length} 个 · 同一账号最多 20 个；吊销后立即失效，无法恢复。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ListSearch value={search} placeholder="名称 / 前缀" onChange={setSearch} />
            <RpButton size="sm" type="button" disabled={loading} onClick={() => void load()}>
              {loading ? '刷新中…' : '刷新'}
            </RpButton>
          </div>
        </div>
        <RpTable>
          <thead>
            <tr>
              <RpTh>名称</RpTh>
              <RpTh>凭证前缀</RpTh>
              <RpTh>创建时间</RpTh>
              <RpTh>最近调用</RpTh>
              <RpTh>状态</RpTh>
              <RpTh>操作</RpTh>
            </tr>
          </thead>
          <tbody>
            {visibleKeys.length === 0 ? (
              <RpEmpty colSpan={6}>
                {keys.length === 0
                  ? '还没有业务凭证。在下方填写名称后创建，把明文交给 ERP 配置即可。'
                  : '没有匹配的凭证，换个名称或前缀再试。'}
              </RpEmpty>
            ) : (
              visibleKeys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td className="font-mono text-xs">{key.maskedKey}</td>
                  <td>{formatDateTimeShort(key.createdAt) || '—'}</td>
                  <td>{key.lastUsedAt ? formatDateTimeShort(key.lastUsedAt) : '尚未调用'}</td>
                  <td>
                    {key.status === 'active' ? (
                      <span className="text-emerald-600">正常</span>
                    ) : (
                      <span className="text-destructive">已过期</span>
                    )}
                  </td>
                  <td className="space-x-2">
                    <RpButton
                      size="sm"
                      type="button"
                      disabled={busy}
                      onClick={() => setConfirm({ type: 'rotate', key })}
                    >
                      重新生成
                    </RpButton>
                    <RpButton
                      size="sm"
                      type="button"
                      disabled={busy}
                      onClick={() => setConfirm({ type: 'revoke', key })}
                    >
                      吊销
                    </RpButton>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </RpTable>
      </section>

      <section className="rp-card space-y-3 p-4">
        <h2 className="text-sm font-medium">创建凭证</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block text-sm">
            名称
            <input
              className="rp-input mt-1 block w-full max-w-md"
              value={name}
              placeholder="例如：ERP 订单系统"
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <RpButton variant="primary" type="button" disabled={busy} onClick={() => void createKey()}>
            {busy ? '处理中…' : '创建凭证'}
          </RpButton>
        </div>
        <p className="text-xs text-muted-foreground">
          该凭证只能调用图片处理相关接口（上传资源、读取预设、提交处理、查询任务、下载结果）；不能签发/吊销其他凭证，也不能调用生图与提示词接口。
        </p>
      </section>

      <section className="rp-card space-y-3 p-4 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-medium">最小调用示例</h2>
          <RpButton
            type="button"
            onClick={() => {
              const path = contract?.downloadPath || '/api/v1/realphotos/contracts/image-processing.openapi.json'
              window.open(`${apiBase}${path}`, '_blank', 'noopener,noreferrer')
            }}
          >
            下载 OpenAPI
          </RpButton>
        </div>
        <ol className="list-inside list-decimal space-y-1 text-xs text-muted-foreground">
          <li>
            请求头带 <code className="font-mono">X-API-Key: &lt;创建时返回的明文&gt;</code>。
          </li>
          <li>
            先上传图片到 <code className="font-mono">POST /api/v1/realphotos/assets</code>，拿到资源 id。
          </li>
          <li>用资源 id + 预设提交批次，再轮询任务详情，直到处理完成。</li>
          <li>
            用{' '}
            <code className="font-mono">
              POST /api/v1/realphotos/processing-tasks/&#123;id&#125;/selected-downloads
            </code>{' '}
            获取下载清单。
          </li>
        </ol>
        <pre className="overflow-x-auto rounded-md border bg-muted/30 p-3 text-xs">{example}</pre>
        <p className="text-xs text-muted-foreground">
          更多字段与响应说明见 OpenAPI 工件。
        </p>
      </section>

      {plaintext ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="新凭证明文"
        >
          <div className="rp-card w-full max-w-2xl space-y-3 p-4 text-sm">
            <div className="flex items-center justify-between gap-2">
              <strong>凭证明文 · {plaintext.name}</strong>
              <RpButton size="sm" type="button" onClick={() => setPlaintext(null)}>
                我已保存
              </RpButton>
            </div>
            <p className="text-destructive">
              明文只显示这一次。关闭后无法再次查看，只能重新生成。
            </p>
            <code className="block break-all rounded-md border bg-muted/40 p-3 font-mono text-xs">
              {plaintext.value}
            </code>
            <div className="flex flex-wrap gap-2">
              <RpButton variant="primary" type="button" onClick={() => void copyPlaintext()}>
                复制明文
              </RpButton>
              <RpButton type="button" onClick={() => setPlaintext(null)}>
                我已复制，关闭
              </RpButton>
            </div>
          </div>
        </div>
      ) : null}

      {confirm ? (
        <RpDialog
          title={confirm.type === 'revoke' ? '吊销凭证' : '重新生成凭证'}
          onClose={() => setConfirm(null)}
        >
          <p>
            {confirm.type === 'revoke'
              ? `吊销「${confirm.key.name}」后，正在使用它的系统会立即收到 401，且无法恢复。`
              : `重新生成「${confirm.key.name}」会立即吊销旧凭证并签发新凭证，使用旧明文的一方需要同步更新。`}
          </p>
          <p className="text-xs text-muted-foreground">
            前缀：<span className="font-mono">{confirm.key.maskedKey}</span>
          </p>
          <div className="flex gap-2">
            <RpButton variant="primary" type="button" disabled={busy} onClick={() => void confirmAction()}>
              {busy ? '处理中…' : confirm.type === 'revoke' ? '确认吊销' : '确认重新生成'}
            </RpButton>
            <RpButton type="button" onClick={() => setConfirm(null)}>
              取消
            </RpButton>
          </div>
        </RpDialog>
      ) : null}
    </main>
  )
}
