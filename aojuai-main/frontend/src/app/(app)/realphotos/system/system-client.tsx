'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { ApiError, apiFetch } from '@/lib/api'

type Contract = {
  duty: string
  purpose?: string
  provider: string
  modelId: string
  configVersion: string
  region: string
  credentialRef: string
  baseUrl?: string
  enabled: boolean
  gapNote: string
  keyPrefix?: string
  masked?: string
  hasSecret?: boolean
  updatedAt?: string | null
  capabilities?: Record<string, unknown>
}

const PURPOSES: { duty: string; label: string }[] = [
  { duty: 'pre_review', label: '图片预审' },
  { duty: 'generation', label: '生图渠道' },
  { duty: 'prompt_opt', label: '提示词优化' },
  { duty: 'final_detection', label: '最终检测' },
]

const PROVIDERS = [
  'Gemini',
  'DeepSeek',
  '阿里千问',
  'ChatGPT Image 2',
  'aoju',
  'google-gemini',
  'deepseek',
  'dashscope',
  '其他',
]

const DUTY_DEFAULT_BASE: Record<string, string> = {
  pre_review: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
  generation: 'https://apis.aoju.ai/v1',
  prompt_opt: 'https://api.deepseek.com/chat/completions',
  final_detection: 'https://generativelanguage.googleapis.com/v1beta',
}

/**
 * F7 role matrix (ticket default + PRD PG-011 / §7):
 * - merchant / admin: may write auto-redo for tenant
 * - tech_support: entrance visible, content read-only
 * - model API: admin only
 */
export function RealphotosSystemClient() {
  const searchParams = useSearchParams()
  const initialTab = searchParams.get('tab') === 'models' ? 'models' : 'redo'
  const [tab, setTab] = useState<'redo' | 'models'>(initialTab)
  const [message, setMessage] = useState('')
  const [roles, setRoles] = useState<string[]>([])
  const [redoEnabled, setRedoEnabled] = useState(false)
  const [redoThreshold, setRedoThreshold] = useState(70)
  const [redoRounds, setRedoRounds] = useState(1)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [passHint, setPassHint] = useState('total_score≥75 且 passed=true（不因换 model id 改变）')

  const [duty, setDuty] = useState('pre_review')
  const [providerChoice, setProviderChoice] = useState('阿里千问')
  const [providerCustom, setProviderCustom] = useState('')
  const [modelId, setModelId] = useState('')
  const [baseUrl, setBaseUrl] = useState(DUTY_DEFAULT_BASE.pre_review)
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)

  const isAdmin = useMemo(
    () => roles.includes('rp_admin') || roles.includes('admin'),
    [roles],
  )
  const isTechOnly = useMemo(() => {
    const tech = roles.includes('rp_tech_support')
    const merchant = roles.includes('rp_merchant') || roles.some((r) => r.startsWith('rp_merchant'))
    return tech && !isAdmin && !merchant
  }, [isAdmin, roles])
  const canEditRedo = !isTechOnly

  const editableContracts = useMemo(
    () => contracts.filter((item) => PURPOSES.some((p) => p.duty === item.duty)),
    [contracts],
  )

  function purposeLabel(code: string) {
    return PURPOSES.find((item) => item.duty === code)?.label || code
  }

  function resolvedProvider() {
    if (providerChoice === '其他') return providerCustom.trim() || '其他'
    return providerChoice
  }

  async function loadContracts() {
    try {
      const data = await apiFetch<{ items: Contract[]; passScoreHint?: string }>(
        '/api/v1/realphotos/provider-contracts',
      )
      setContracts(data.items || [])
      if (data.passScoreHint) setPassHint(data.passScoreHint)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '合同读取失败')
    }
  }

  useEffect(() => {
    void apiFetch<{ roleCodes: string[] }>('/api/v1/realphotos/me')
      .then((data) => setRoles(data.roleCodes || []))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '身份读取失败'))
    void apiFetch<{ enabled: boolean; scoreThreshold: number; extraRounds: number }>(
      '/api/v1/realphotos/redo-settings',
    )
      .then((data) => {
        setRedoEnabled(Boolean(data.enabled))
        setRedoThreshold(Number(data.scoreThreshold))
        setRedoRounds(Number(data.extraRounds))
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError) setMessage(error.message)
      })
  }, [])

  useEffect(() => {
    if (tab !== 'models' || !isAdmin) return
    void loadContracts()
  }, [tab, isAdmin])

  useEffect(() => {
    const existing = contracts.find((item) => item.duty === duty)
    if (existing) {
      setModelId(existing.modelId || '')
      setBaseUrl(existing.baseUrl || DUTY_DEFAULT_BASE[duty] || '')
      const match = PROVIDERS.find((name) => name === existing.provider)
      if (match) {
        setProviderChoice(match)
        setProviderCustom('')
      } else {
        setProviderChoice('其他')
        setProviderCustom(existing.provider || '')
      }
    } else {
      setModelId('')
      setBaseUrl(DUTY_DEFAULT_BASE[duty] || '')
    }
    setApiKey('')
  }, [duty, contracts])

  async function saveRedo() {
    if (!canEditRedo) {
      setMessage('技术客服只能查看自动重做设置，不能保存')
      return
    }
    try {
      await apiFetch('/api/v1/realphotos/redo-settings', {
        method: 'PUT',
        body: JSON.stringify({
          enabled: redoEnabled,
          scoreThreshold: redoThreshold,
          extraRounds: redoRounds,
        }),
      })
      setMessage('自动重做已保存，只影响之后提交的任务')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    }
  }

  async function saveModel() {
    if (!isAdmin) {
      setMessage('只有平台管理员可以登记模型合同')
      return
    }
    const provider = resolvedProvider()
    if (!provider) {
      setMessage('请填写提供商')
      return
    }
    if (!modelId.trim()) {
      setMessage('请填写模型版本')
      return
    }
    if (!baseUrl.trim()) {
      setMessage('请填写 Base URL')
      return
    }
    setSaving(true)
    try {
      await apiFetch('/api/v1/realphotos/provider-contracts', {
        method: 'POST',
        body: JSON.stringify({
          duty,
          provider,
          modelId: modelId.trim(),
          baseUrl: baseUrl.trim(),
          apiKey: apiKey.trim() || undefined,
          enabled: true,
        }),
      })
      setApiKey('')
      setMessage('模型配置已保存；列表仅显示掩码。第一版不轮询。')
      await loadContracts()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function toggleEnabled(item: Contract) {
    try {
      await apiFetch('/api/v1/realphotos/provider-contracts/enabled', {
        method: 'POST',
        body: JSON.stringify({ duty: item.duty, enabled: !item.enabled }),
      })
      setMessage(item.enabled ? '已停用' : '已启用')
      await loadContracts()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '启停失败')
    }
  }

  async function deleteContract(item: Contract) {
    if (!window.confirm(`确认删除「${purposeLabel(item.duty)}」渠道？删除后运行时将不可用直至重新登记。`)) {
      return
    }
    try {
      await apiFetch(`/api/v1/realphotos/provider-contracts/${encodeURIComponent(item.duty)}`, {
        method: 'DELETE',
      })
      setMessage('渠道已删除（软删）')
      await loadContracts()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '删除失败')
    }
  }

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">系统管理</h1>
      <p className="text-sm text-muted-foreground">入口对授权角色可见；内容按角色裁剪。运营指标在工作台，不在本页。</p>
      <p className="text-sm">{message}</p>
      <div className="flex gap-2 text-sm">
        <button className={`border px-3 py-1 ${tab === 'redo' ? 'bg-muted' : ''}`} type="button" onClick={() => setTab('redo')}>
          自动重做
        </button>
        <button
          className={`border px-3 py-1 ${tab === 'models' ? 'bg-muted' : ''}`}
          type="button"
          onClick={() => setTab('models')}
          disabled={!isAdmin}
        >
          模型 API
        </button>
      </div>

      {tab === 'redo' ? (
        <section className="space-y-3 text-sm">
          <p>默认关；阈值 70；追加 1。越界由后端拒绝。</p>
          {isTechOnly ? (
            <p className="text-muted-foreground">技术客服只读：可查看本租户快照，不可改写。</p>
          ) : null}
          <label className="block">
            <input
              type="checkbox"
              checked={redoEnabled}
              disabled={!canEditRedo}
              onChange={(event) => setRedoEnabled(event.target.checked)}
            />{' '}
            启用自动重做
          </label>
          <label className="block">
            阈值
            <input
              className="ml-2 w-20 border px-1"
              type="number"
              min={0}
              max={100}
              value={redoThreshold}
              disabled={!canEditRedo}
              onChange={(event) => setRedoThreshold(Number(event.target.value))}
            />
          </label>
          <label className="block">
            追加次数
            <input
              className="ml-2 w-20 border px-1"
              type="number"
              min={1}
              max={5}
              value={redoRounds}
              disabled={!canEditRedo}
              onChange={(event) => setRedoRounds(Number(event.target.value))}
            />
          </label>
          <button
            className="border px-3 py-1 disabled:opacity-50"
            type="button"
            disabled={!canEditRedo}
            onClick={() => void saveRedo()}
          >
            保存
          </button>
        </section>
      ) : null}

      {tab === 'models' ? (
        <section className="space-y-5 text-sm">
          {!isAdmin ? (
            <p>只有平台管理员可以查看和登记模型合同。列表不显示上游 Key。</p>
          ) : (
            <>
              <div className="space-y-1 border p-3">
                <h2 className="font-medium">检测基线 · Gemini Vision</h2>
                <p className="text-muted-foreground">{passHint}</p>
              </div>

              <div className="space-y-3 border p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="font-medium">大模型 API Key 配置与管理</h2>
                  <span className="text-xs text-muted-foreground">平台范围 · 第一版不轮询</span>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="block">
                    提供商
                    <select
                      className="mt-1 w-full border px-2 py-1"
                      value={providerChoice}
                      onChange={(event) => setProviderChoice(event.target.value)}
                    >
                      {PROVIDERS.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {providerChoice === '其他' ? (
                    <label className="block">
                      自定义提供商
                      <input
                        className="mt-1 w-full border px-2 py-1"
                        value={providerCustom}
                        onChange={(event) => setProviderCustom(event.target.value)}
                      />
                    </label>
                  ) : null}
                  <label className="block">
                    模型版本
                    <input
                      className="mt-1 w-full border px-2 py-1"
                      value={modelId}
                      onChange={(event) => setModelId(event.target.value)}
                      placeholder="例如 qwen3-vl-plus"
                    />
                  </label>
                  <label className="block">
                    用途
                    <select
                      className="mt-1 w-full border px-2 py-1"
                      value={duty}
                      onChange={(event) => setDuty(event.target.value)}
                    >
                      {PURPOSES.map((item) => (
                        <option key={item.duty} value={item.duty}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block md:col-span-2">
                    Base URL
                    <input
                      className="mt-1 w-full border px-2 py-1"
                      value={baseUrl}
                      onChange={(event) => setBaseUrl(event.target.value)}
                    />
                  </label>
                  <label className="block md:col-span-2">
                    API Key（单槽；保存后清空；列表仅掩码）
                    <input
                      className="mt-1 w-full border px-2 py-1"
                      type="password"
                      autoComplete="off"
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
                      placeholder="留空则保留原密钥"
                    />
                  </label>
                </div>
                <p className="text-xs text-muted-foreground">
                  原型多 Key 权重轮询按 PRD 第一版不做。也可打开
                  <Link className="mx-1 underline" href="/realphotos/provider-contracts">
                    模型合同
                  </Link>
                  只读明细。
                </p>
                <button
                  className="border px-3 py-1 disabled:opacity-50"
                  type="button"
                  disabled={saving}
                  onClick={() => void saveModel()}
                >
                  保存模型配置
                </button>
              </div>

              <div className="space-y-2">
                <h2 className="font-medium">已登记渠道</h2>
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="border px-2 py-1 text-left">渠道 / 模型 / Base URL</th>
                      <th className="border px-2 py-1 text-left">用途</th>
                      <th className="border px-2 py-1 text-left">Keys</th>
                      <th className="border px-2 py-1 text-left">状态</th>
                      <th className="border px-2 py-1 text-left">范围</th>
                      <th className="border px-2 py-1 text-left">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {editableContracts.map((item) => (
                      <tr key={item.duty}>
                        <td className="border px-2 py-1">
                          <div className="font-medium">{item.provider}</div>
                          <div className="text-muted-foreground">{item.modelId || '空'}</div>
                          <div className="break-all text-muted-foreground">{item.baseUrl || '—'}</div>
                        </td>
                        <td className="border px-2 py-1">{item.purpose || purposeLabel(item.duty)}</td>
                        <td className="border px-2 py-1 font-mono text-xs">
                          {item.keyPrefix || item.masked || (item.hasSecret ? '已配置' : '未配置')}
                        </td>
                        <td className="border px-2 py-1">{item.enabled ? '已启用' : '已停用'}</td>
                        <td className="border px-2 py-1">平台</td>
                        <td className="border px-2 py-1">
                          <button className="mr-2 border px-2 py-0.5" type="button" onClick={() => void toggleEnabled(item)}>
                            {item.enabled ? '停用' : '启用'}
                          </button>
                          <button className="border px-2 py-0.5" type="button" onClick={() => void deleteContract(item)}>
                            删除
                          </button>
                        </td>
                      </tr>
                    ))}
                    {editableContracts.length === 0 ? (
                      <tr>
                        <td className="border px-2 py-2 text-muted-foreground" colSpan={6}>
                          暂无渠道，请先保存配置。
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      ) : null}
    </main>
  )
}
