'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'

import { ApiError, apiFetch } from '@/lib/api'

type Contract = {
  duty: string
  provider: string
  modelId: string
  configVersion: string
  region: string
  credentialRef: string
  enabled: boolean
  gapNote: string
  capabilities?: Record<string, unknown>
}

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

  const isAdmin = useMemo(
    () => roles.includes('rp_admin') || roles.includes('admin'),
    [roles],
  )

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
    void apiFetch<{ items: Contract[] }>('/api/v1/realphotos/provider-contracts')
      .then((data) => setContracts(data.items || []))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '合同读取失败'))
  }, [tab, isAdmin])

  async function saveRedo() {
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
          <label className="block">
            <input type="checkbox" checked={redoEnabled} onChange={(event) => setRedoEnabled(event.target.checked)} />{' '}
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
              onChange={(event) => setRedoRounds(Number(event.target.value))}
            />
          </label>
          <button className="border px-3 py-1" type="button" onClick={() => void saveRedo()}>
            保存
          </button>
        </section>
      ) : null}

      {tab === 'models' ? (
        <section className="space-y-3 text-sm">
          {!isAdmin ? (
            <p>只有平台管理员可以查看和登记模型合同。列表不显示上游 Key。</p>
          ) : (
            <>
              <p>
                每职责一套配置。也可打开
                <Link className="mx-1 underline" href="/realphotos/provider-contracts">
                  模型合同
                </Link>
                独立页。
              </p>
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className="border px-2 py-1 text-left">职责</th>
                    <th className="border px-2 py-1 text-left">provider</th>
                    <th className="border px-2 py-1 text-left">model ID</th>
                    <th className="border px-2 py-1 text-left">凭据引用</th>
                    <th className="border px-2 py-1 text-left">启用</th>
                  </tr>
                </thead>
                <tbody>
                  {contracts.map((item) => (
                    <tr key={item.duty}>
                      <td className="border px-2 py-1">{item.duty}</td>
                      <td className="border px-2 py-1">{item.provider}</td>
                      <td className="border px-2 py-1">{item.modelId || '空'}</td>
                      <td className="border px-2 py-1">{item.credentialRef || '空'}</td>
                      <td className="border px-2 py-1">{item.enabled ? '是' : '否'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      ) : null}
    </main>
  )
}
