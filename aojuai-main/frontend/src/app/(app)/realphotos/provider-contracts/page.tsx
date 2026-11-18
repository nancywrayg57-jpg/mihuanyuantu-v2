'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import {
  RpDialog,
  RpEmptyState,
  RpSkeletonRows,
  RpStatus,
  RpTable,
  RpTableScroll,
  RpTh,
} from '@/components/realphotos/rp-table'
import { ApiError, apiFetch } from '@/lib/api'

type Contract = {
  duty: string
  provider: string
  modelId: string
  configVersion: string
  region: string
  credentialRef: string
  baseUrl: string
  capabilities: Record<string, unknown>
  enabled: boolean
  gapNote: string
}

const DUTY_LABELS: Record<string, string> = {
  pre_review: '内容预审',
  generation: '生图',
  prompt_opt: '提示词优化',
  final_detection: '最终检测',
  import: 'URL 导入',
}

function dutyLabel(duty: string): string {
  return DUTY_LABELS[duty] || duty
}

function capText(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join('、')
  if (typeof value === 'boolean') return value ? '支持' : '不支持'
  if (value === null || value === undefined) return '空'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function limitTags(caps: Record<string, unknown>): Array<{ label: string; tone: 'warn' | 'bad' }> {
  const tags: Array<{ label: string; tone: 'warn' | 'bad' }> = []
  const seed = String(caps.seed ?? '').toLowerCase()
  if (seed.includes('gap') || seed.includes('not') || caps.seed === false) {
    tags.push({ label: '种子不支持', tone: 'warn' })
  }
  const size = String(caps.sizeControl ?? '').toLowerCase()
  if (size.includes('unsupported') || size.includes('not_honored') || size.includes('not-honored')) {
    tags.push({ label: '尺寸不保证', tone: 'warn' })
  }
  if (caps.pollingEnabled === false) {
    tags.push({ label: '不轮询', tone: 'bad' })
  }
  if (caps.formalSupplier === false) {
    tags.push({ label: '非正式供应商', tone: 'warn' })
  }
  return tags
}

export default function RealphotosProviderContractsPage() {
  const [items, setItems] = useState<Contract[]>([])
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [capabilityTarget, setCapabilityTarget] = useState<Contract | null>(null)

  useEffect(() => {
    setLoading(true)
    void apiFetch<{ items: Contract[] }>('/api/v1/realphotos/provider-contracts')
      .then((data) => setItems(data.items))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '读取失败'))
      .finally(() => setLoading(false))
  }, [])

  const visibleItems = useMemo(
    () =>
      items.filter((item) =>
        matchSearchText(
          search,
          dutyLabel(item.duty),
          item.duty,
          item.provider,
          item.modelId,
          item.configVersion,
          item.region,
          item.gapNote,
        ),
      ),
    [items, search],
  )

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">模型合同</h1>
      <p className="text-sm">{message}</p>
      <section className="rp-card p-4 shadow-sm space-y-3">
        <ListSearch value={search} placeholder="职责 / 供应商 / 模型" onChange={setSearch} />
        <RpTableScroll>
          <RpTable>
            <thead>
              <tr>
                <RpTh>职责</RpTh>
                <RpTh>供应商</RpTh>
                <RpTh>模型</RpTh>
                <RpTh>版本</RpTh>
                <RpTh>区域</RpTh>
                <RpTh>凭据引用</RpTh>
                <RpTh>能力</RpTh>
                <RpTh>状态</RpTh>
                <RpTh>缺口</RpTh>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <RpSkeletonRows colSpan={9} />
              ) : visibleItems.length === 0 ? (
                <RpEmptyState
                  colSpan={9}
                  title="暂无模型合同"
                  description="合同由平台初始化；如需接入新的供应商，请联系平台管理员。"
                />
              ) : (
                visibleItems.map((item) => {
                  const tags = limitTags(item.capabilities || {})
                  const capCount = Object.keys(item.capabilities || {}).length
                  return (
                    <tr key={item.duty}>
                      <td className="whitespace-nowrap">{dutyLabel(item.duty)}</td>
                      <td>{item.provider}</td>
                      <td className="max-w-[14rem] truncate" title={item.modelId}>
                        {item.modelId || '空'}
                      </td>
                      <td>{item.configVersion}</td>
                      <td className="max-w-[12rem] truncate" title={item.region}>
                        {item.region || '空'}
                      </td>
                      <td className="max-w-[16rem] truncate" title={item.credentialRef}>
                        {item.credentialRef || '空'}
                      </td>
                      <td>
                        <div className="flex flex-wrap items-center gap-1">
                          <button
                            className="rp-btn rp-btn-sm"
                            type="button"
                            onClick={() => setCapabilityTarget(item)}
                          >
                            查看能力（{capCount}）
                          </button>
                          {tags.map((tag) => (
                            <RpStatus key={tag.label} tone={tag.tone}>
                              {tag.label}
                            </RpStatus>
                          ))}
                        </div>
                      </td>
                      <td>{item.enabled ? '启用' : '停用'}</td>
                      <td className="max-w-[18rem] truncate" title={item.gapNote}>
                        {item.gapNote || '—'}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </RpTable>
        </RpTableScroll>
      </section>

      {capabilityTarget ? (
        <RpDialog
          title={`能力 · ${dutyLabel(capabilityTarget.duty)}`}
          label={`能力 · ${dutyLabel(capabilityTarget.duty)}`}
          onClose={() => setCapabilityTarget(null)}
        >
          <p className="text-xs text-muted-foreground">
            {capabilityTarget.provider} / {capabilityTarget.modelId} / 版本 {capabilityTarget.configVersion}
          </p>
          <RpTable>
            <thead>
              <tr>
                <RpTh>能力项</RpTh>
                <RpTh>值</RpTh>
              </tr>
            </thead>
            <tbody>
              {Object.entries(capabilityTarget.capabilities || {}).length === 0 ? (
                <RpEmptyState colSpan={2} title="暂无能力字段" />
              ) : (
                Object.entries(capabilityTarget.capabilities || {}).map(([key, value]) => (
                  <tr key={key}>
                    <td className="align-top font-mono text-xs">{key}</td>
                    <td className="break-all">{capText(value)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </RpTable>
          {capabilityTarget.gapNote ? (
            <div className="rounded-md border bg-muted/30 p-3 text-xs">
              <div className="mb-1 font-medium">关键限制 / 缺口</div>
              {capabilityTarget.gapNote}
            </div>
          ) : null}
        </RpDialog>
      ) : null}
    </main>
  )
}
