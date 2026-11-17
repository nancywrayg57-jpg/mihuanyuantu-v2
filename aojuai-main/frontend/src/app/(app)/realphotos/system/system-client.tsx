'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { RpDialog } from '@/components/realphotos/rp-table'
import { ApiError, apiFetch } from '@/lib/api'

import { DetectionPassScoreCard } from './detection-pass-score-card'

type DutyCredential = {
  id: string
  masked: string
  provider?: string
  modelId?: string
  baseUrl?: string
  enabled: boolean
}

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
  credentials?: DutyCredential[]
  activeCredentialId?: string
  updatedAt?: string | null
  capabilities?: Record<string, unknown>
}

const PURPOSES: { duty: string; label: string }[] = [
  { duty: 'pre_review', label: '图片预审' },
  { duty: 'generation', label: '生图渠道' },
  { duty: 'prompt_opt', label: '提示词优化' },
  { duty: 'final_detection', label: '最终检测' },
  { duty: 'import', label: 'URL导入' },
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
  'api-image-host',
  '其他',
]

const DUTY_DEFAULT_BASE: Record<string, string> = {
  pre_review: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
  generation: 'https://apis.aoju.ai/v1',
  prompt_opt: 'https://api.deepseek.com/chat/completions',
  final_detection: 'https://generativelanguage.googleapis.com/v1beta',
  import: 'http://47.85.47.252',
}

/** Keep in sync with supplier_clients.PROVIDER_DEFAULT_BASE. Switching provider must not clear Base URL. */
const PROVIDER_DEFAULT_BASE: Record<string, string> = {
  Gemini: 'https://generativelanguage.googleapis.com/v1beta',
  'google-gemini': 'https://generativelanguage.googleapis.com/v1beta',
  DeepSeek: 'https://api.deepseek.com/chat/completions',
  deepseek: 'https://api.deepseek.com/chat/completions',
  '阿里千问': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
  dashscope: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
  'ChatGPT Image 2': 'https://apis.aoju.ai/v1',
  aoju: 'https://apis.aoju.ai/v1',
  'api-image-host': 'http://47.85.47.252',
}

const PROVIDER_STATIC_MODELS: Record<string, string[]> = {
  Gemini: ['gemini-3.1-pro-preview', 'gemini-2.5-pro', 'gemini-2.0-flash'],
  'google-gemini': ['gemini-3.1-pro-preview', 'gemini-2.5-pro', 'gemini-2.0-flash'],
  DeepSeek: ['deepseek-chat', 'deepseek-reasoner'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  '阿里千问': ['qwen3-vl-plus', 'qwen-vl-plus', 'qwen-plus', 'qwen-turbo', 'qwen-max'],
  dashscope: ['qwen3-vl-plus', 'qwen-vl-plus', 'qwen-plus', 'qwen-turbo', 'qwen-max'],
  'ChatGPT Image 2': ['gpt-image-2', 'gpt-image-2-vip'],
  aoju: ['gpt-image-2', 'gpt-image-2-vip'],
  'api-image-host': ['api-image-host'],
}

function nonEmptyBase(preferred: string | undefined, duty: string): string {
  const text = String(preferred || '').trim()
  if (text) return text
  return DUTY_DEFAULT_BASE[duty] || PROVIDER_DEFAULT_BASE.DeepSeek
}

/**
 * F7 role matrix (ticket default + PRD PG-011 / §7):
 * - merchant / admin: may write auto-redo for tenant
 * - tech_support: entrance visible, content read-only
 * - model API: admin only
 */
type SystemTab = 'redo' | 'models' | 'baseline'

function tabFromSearch(raw: string | null): SystemTab {
  if (raw === 'models' || raw === 'baseline') return raw
  return 'redo'
}

export function RealphotosSystemClient() {
  const searchParams = useSearchParams()
  const initialTab = tabFromSearch(searchParams.get('tab'))
  const [tab, setTab] = useState<SystemTab>(initialTab)
  const [message, setMessage] = useState('')
  const [roles, setRoles] = useState<string[]>([])
  const [redoEnabled, setRedoEnabled] = useState(false)
  const [redoThreshold, setRedoThreshold] = useState(70)
  const [redoRounds, setRedoRounds] = useState(1)
  const [contracts, setContracts] = useState<Contract[]>([])
  const [duty, setDuty] = useState('pre_review')
  const [providerChoice, setProviderChoice] = useState('阿里千问')
  const [providerCustom, setProviderCustom] = useState('')
  const [modelId, setModelId] = useState(PROVIDER_STATIC_MODELS['阿里千问'][0] || '')
  const [modelOptions, setModelOptions] = useState<string[]>(PROVIDER_STATIC_MODELS['阿里千问'])
  const [baseUrl, setBaseUrl] = useState(DUTY_DEFAULT_BASE.pre_review)
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [channelSearch, setChannelSearch] = useState('')
  // 2026-11-17: 已登记渠道「修改」弹窗
  const [editing, setEditing] = useState<Contract | null>(null)
  const [editModelId, setEditModelId] = useState('')
  const [editPurpose, setEditPurpose] = useState('')
  const [editBaseUrl, setEditBaseUrl] = useState('')
  const replaceModelRef = useRef(false)
  const modelIdRef = useRef(modelId)
  modelIdRef.current = modelId

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
  // Model API + detection baseline are admin-only; hide entry points for other roles.
  const canManageModels = isAdmin
  const canManageBaseline = isAdmin

  useEffect(() => {
    if (!roles.length) return
    if ((tab === 'models' && !canManageModels) || (tab === 'baseline' && !canManageBaseline)) {
      setTab('redo')
    }
  }, [roles, tab, canManageModels, canManageBaseline])

  const shownModels = useMemo(() => {
    if (modelId && !modelOptions.includes(modelId)) return [modelId, ...modelOptions]
    return modelOptions
  }, [modelId, modelOptions])

  const editableContracts = useMemo(
    () =>
      contracts
        .filter((item) => PURPOSES.some((p) => p.duty === item.duty))
        .filter((item) =>
          matchSearchText(
            channelSearch,
            item.duty,
            item.purpose,
            purposeLabel(item.duty),
            item.provider,
            item.modelId,
            item.baseUrl,
            item.keyPrefix,
            item.masked,
            ...(item.credentials || []).flatMap((cred) => [cred.masked, cred.provider, cred.modelId]),
          ),
        ),
    [contracts, channelSearch],
  )

  function purposeLabel(code: string) {
    return PURPOSES.find((item) => item.duty === code)?.label || code
  }

  function resolvedProvider() {
    if (providerChoice === '其他') return providerCustom.trim() || '其他'
    return providerChoice
  }

  function onProviderChange(next: string) {
    setProviderChoice(next)
    const preferred = PROVIDER_DEFAULT_BASE[next]
    setBaseUrl(nonEmptyBase(preferred, duty))
    replaceModelRef.current = true
    const fallbackModels = PROVIDER_STATIC_MODELS[next] || []
    setModelOptions(fallbackModels)
    setModelId(fallbackModels[0] || '')
  }

  async function loadContracts() {
    try {
      const data = await apiFetch<{ items: Contract[]; passScoreHint?: string }>(
        '/api/v1/realphotos/provider-contracts',
      )
      setContracts(data.items || [])
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
      const nextModel = existing.modelId || ''
      setModelId(nextModel)
      setModelOptions((current) => (nextModel && !current.includes(nextModel) ? [nextModel, ...current] : current))
      setBaseUrl(nonEmptyBase(existing.baseUrl || DUTY_DEFAULT_BASE[duty], duty))
      const match = PROVIDERS.find((name) => name === existing.provider)
      if (match) {
        setProviderChoice(match)
        setProviderCustom('')
      } else {
        setProviderChoice('其他')
        setProviderCustom(existing.provider || '')
      }
    } else if (duty === 'import') {
      setProviderChoice('api-image-host')
      setProviderCustom('')
      setModelOptions(['api-image-host'])
      setModelId('api-image-host')
      setBaseUrl(nonEmptyBase(DUTY_DEFAULT_BASE.import, duty))
    } else {
      const fallback = PROVIDER_STATIC_MODELS[providerChoice] || []
      setModelOptions(fallback)
      setModelId(fallback[0] || '')
      setBaseUrl(nonEmptyBase(DUTY_DEFAULT_BASE[duty], duty))
    }
    setApiKey('')
  }, [duty, contracts])

  useEffect(() => {
    if (tab !== 'models' || !isAdmin) return
    const provider = providerChoice === '其他' ? providerCustom.trim() || '其他' : providerChoice
    const url = baseUrl.trim()
    if (!url) return
    const seq = window.setTimeout(() => {
      void (async () => {
        try {
          const data = await apiFetch<{ models?: string[]; probe?: string; baseUrl?: string }>(
            '/api/v1/realphotos/provider-contracts/probe-models',
            {
              method: 'POST',
              body: JSON.stringify({
                provider,
                duty,
                baseUrl: url,
                apiKey: apiKey.trim() || undefined,
              }),
            },
          )
          const models = (data.models || []).filter((item) => item.trim())
          const current = modelIdRef.current
          if (replaceModelRef.current) {
            replaceModelRef.current = false
            setModelOptions(models)
            setModelId(models[0] || current)
            return
          }
          if (current && !models.includes(current)) {
            setModelOptions([current, ...models])
          } else {
            setModelOptions(models.length ? models : PROVIDER_STATIC_MODELS[provider] || [])
          }
        } catch {
          const fallback = PROVIDER_STATIC_MODELS[provider] || []
          const current = modelIdRef.current
          setModelOptions(current && !fallback.includes(current) ? [current, ...fallback] : fallback)
        }
      })()
    }, 350)
    return () => window.clearTimeout(seq)
  }, [tab, isAdmin, providerChoice, providerCustom, baseUrl, duty, apiKey])

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
    if (duty !== 'import' && !apiKey.trim()) {
      // Non-import duties historically allow empty key when rotating meta only;
      // keep prior behavior (backend rejects enable without secret).
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
          apiKey: duty === 'import' ? undefined : apiKey.trim() || undefined,
          enabled: true,
        }),
      })
      setApiKey('')
      setMessage(
        duty === 'import'
          ? 'URL 导入供应商已保存（无需 API Key）；商家粘贴 /images/ 或 /api/images/ URL 后统一经 API 拉取。'
          : '模型配置已追加保存；列表仅显示掩码。同用途可共存多 Key，同时只启用一套。第一版不轮询。',
      )
      await loadContracts()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function updateContract() {
    if (!editing) return
    const targetModel = editModelId.trim()
    const targetBase = editBaseUrl.trim()
    if (!targetModel) {
      setMessage('请填写模型版本')
      return
    }
    if (!targetBase) {
      setMessage('请填写 Base URL')
      return
    }
    setSaving(true)
    try {
      await apiFetch(`/api/v1/realphotos/provider-contracts/${encodeURIComponent(editing.duty)}`, {
        method: 'PUT',
        body: JSON.stringify({
          modelId: targetModel,
          purpose: editPurpose,
          baseUrl: targetBase,
        }),
      })
      setMessage('渠道已更新，新配置立即对全站生效。')
      setEditing(null)
      await loadContracts()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '修改失败')
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
      <RpPageHeader title="系统管理" />
      <p className="text-sm">{message}</p>
      <div className="flex flex-wrap gap-2 text-sm">
        <button className={`rp-btn border px-3 py-1 ${tab === 'redo' ? 'bg-muted' : ''}`} type="button" onClick={() => setTab('redo')}>
          自动重做
        </button>
        {canManageModels ? (
          <button
            className={`rp-btn border px-3 py-1 ${tab === 'models' ? 'bg-muted' : ''}`}
            type="button"
            onClick={() => setTab('models')}
          >
            模型 API
          </button>
        ) : null}
        {canManageBaseline ? (
          <button
            className={`rp-btn border px-3 py-1 ${tab === 'baseline' ? 'bg-muted' : ''}`}
            type="button"
            onClick={() => setTab('baseline')}
          >
            检测基线
          </button>
        ) : null}
      </div>

      {tab === 'baseline' && canManageBaseline ? <DetectionPassScoreCard /> : null}

      {tab === 'redo' ? (
        <section className="rp-card rounded-xl border border-border bg-card shadow-sm p-4 space-y-3 text-sm">
          {isTechOnly ? (
            <p className="text-muted-foreground">技术客服只读，不可改写。</p>
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
            className="rp-btn border px-3 py-1 disabled:opacity-50"
            type="button"
            disabled={!canEditRedo}
            onClick={() => void saveRedo()}
          >
            保存
          </button>
        </section>
      ) : null}

      {tab === 'models' && canManageModels ? (
        <section className="space-y-5 text-sm">
              <div className="rp-card rounded-xl border border-border bg-card shadow-sm space-y-3 p-4">
                <h2 className="font-medium">大模型 API Key 配置与管理</h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="block">
                    提供商
                    <select
                      className="mt-1 w-full border px-2 py-1"
                      value={providerChoice}
                      onChange={(event) => onProviderChange(event.target.value)}
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
                    {providerChoice === '其他' && shownModels.length === 0 ? (
                      <input
                        className="mt-1 w-full border px-2 py-1"
                        value={modelId}
                        onChange={(event) => setModelId(event.target.value)}
                        placeholder="填写模型 ID"
                      />
                    ) : (
                      <select
                        className="mt-1 w-full border px-2 py-1"
                        value={shownModels.includes(modelId) ? modelId : shownModels[0] || ''}
                        onChange={(event) => setModelId(event.target.value)}
                      >
                        {shownModels.length === 0 ? <option value="">暂无可选模型</option> : null}
                        {shownModels.map((name) => (
                          <option key={name} value={name}>
                            {name}
                          </option>
                        ))}
                      </select>
                    )}
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
                  {duty === 'import' ? (
                    <p className="md:col-span-2 text-xs text-muted-foreground">
                      URL 导入为 API 型供应商：无需 API Key；粘贴图床完整 URL，系统统一请求{' '}
                      <code className="font-mono">{`{base}/api/images/<file>`}</code>。
                    </p>
                  ) : (
                    <label className="block md:col-span-2">
                      API Key
                      <input
                        className="mt-1 w-full border px-2 py-1"
                        type="password"
                        autoComplete="off"
                        value={apiKey}
                        onChange={(event) => setApiKey(event.target.value)}
                        placeholder="填写则追加一条，不覆盖已有 Key"
                      />
                    </label>
                  )}
                </div>
                <button
                  className="rp-btn border px-3 py-1 disabled:opacity-50"
                  type="button"
                  disabled={saving}
                  onClick={() => void saveModel()}
                >
                  保存模型配置
                </button>
              </div>

              <div className="rp-card rounded-xl border border-border bg-card shadow-sm space-y-2 p-4">
                <div className="rp-filter flex flex-wrap items-center justify-between gap-3">
                  <h2 className="font-medium">已登记渠道</h2>
                  <ListSearch value={channelSearch} placeholder="提供商 / 模型 / 用途" onChange={setChannelSearch} />
                </div>
                <table className="rp-table w-full border-collapse text-sm">
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
                          {item.duty === 'import' ? (
                            <span className="font-sans text-muted-foreground">无需鉴权</span>
                          ) : (item.credentials || []).length > 0 ? (
                            <div className="space-y-1">
                              {(item.credentials || []).map((cred) => (
                                <div key={cred.id} className="flex flex-wrap items-center gap-1">
                                  <span>{cred.masked || '已配置'}</span>
                                  {cred.modelId ? (
                                    <span className="text-muted-foreground font-sans">{cred.modelId}</span>
                                  ) : null}
                                  <span className="text-muted-foreground font-sans">
                                    {cred.enabled ? '启用中' : '已停用'}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            item.keyPrefix || item.masked || (item.hasSecret ? '已配置' : '未配置')
                          )}
                        </td>
                        <td className="border px-2 py-1">{item.enabled ? '已启用' : '已停用'}</td>
                        <td className="border px-2 py-1">平台</td>
                        <td className="border px-2 py-1">
                          <button
                            className="rp-btn mr-2 border px-2 py-0.5"
                            type="button"
                            onClick={() => {
                              setEditing(item)
                              setEditModelId(item.modelId || '')
                              setEditPurpose(item.duty)
                              setEditBaseUrl(item.baseUrl || '')
                            }}
                          >
                            修改
                          </button>
                          <button className="rp-btn mr-2 border px-2 py-0.5" type="button" onClick={() => void toggleEnabled(item)}>
                            {item.enabled ? '停用' : '启用'}
                          </button>
                          <button className="rp-btn border px-2 py-0.5" type="button" onClick={() => void deleteContract(item)}>
                            删除
                          </button>
                        </td>
                      </tr>
                    ))}
                    {editableContracts.length === 0 ? (
                      <tr>
                        <td className="rp-empty border px-2 py-2 text-muted-foreground" colSpan={6}>
                          暂无渠道，请先保存配置。
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
        </section>
      ) : null}
      {editing ? (
        <RpDialog title={`修改渠道 · ${editing.provider}`} label="修改渠道" onClose={() => setEditing(null)}>
          <label className="block text-sm">
            模型版本
            <input
              className="rp-input mt-1 block w-full"
              value={editModelId}
              onChange={(event) => setEditModelId(event.target.value)}
            />
          </label>
          <label className="block text-sm">
            用途
            <select
              className="rp-input mt-1 block w-full"
              value={editPurpose}
              onChange={(event) => setEditPurpose(event.target.value)}
            >
              {PURPOSES.map((item) => (
                <option key={item.duty} value={item.duty}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Base URL
            <input
              className="rp-input mt-1 block w-full"
              value={editBaseUrl}
              onChange={(event) => setEditBaseUrl(event.target.value)}
            />
          </label>
          {editPurpose !== editing.duty ? (
            <p className="text-xs text-amber-700">改用途会把该渠道的密钥条目一并迁移到新用途；目标用途不能已有渠道。</p>
          ) : null}
          <button
            className="rp-btn border px-3 py-1 text-sm disabled:opacity-50"
            type="button"
            disabled={saving}
            onClick={() => void updateContract()}
          >
            保存
          </button>
        </RpDialog>
      ) : null}
    </main>
  )
}
