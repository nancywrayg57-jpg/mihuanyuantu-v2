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

type OpsMetrics = {
  queueDepth?: number | null
  detectionPassRate?: number | null
  failureRate?: number | null
}

function formatRate(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return '暂无抽样数据'
  const n = Number(value)
  const pct = n <= 1 ? n * 100 : n
  return `${pct.toFixed(1)}%`
}

export default function RealphotosProviderContractsPage() {
  const [items, setItems] = useState<Contract[]>([])
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [capabilityTarget, setCapabilityTarget] = useState<Contract | null>(null)
  const [opsMetrics, setOpsMetrics] = useState<OpsMetrics | null>(null)

  useEffect(() => {
    setLoading(true)
    void apiFetch<{ items: Contract[] }>('/api/v1/realphotos/provider-contracts')
      .then((data) => setItems(data.items))
      .catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '读取失败'))
      .finally(() => setLoading(false))
    void apiFetch<OpsMetrics>('/api/v1/realphotos/ops-metrics')
      .then((data) => setOpsMetrics(data))
      .catch(() => setOpsMetrics(null))
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

  const detection = items.find((item) => item.duty === 'final_detection')
  const importContract = items.find((item) => item.duty === 'import')

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">模型合同</h1>
      <p className="text-sm">{message}</p>

      <section className="rp-card space-y-3 p-4 shadow-sm" data-testid="default-strategy-summary">
        <h2 className="text-sm font-medium">检测 / 处理默认策略摘要（只读）</h2>
        {detection ? (
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">最终检测供应商</dt>
              <dd>{detection.provider || '—'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">模型 modelId</dt>
              <dd className="break-all font-mono text-xs">{detection.modelId || '空'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">启用状态</dt>
              <dd>{detection.enabled ? '启用' : '停用'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">configVersion</dt>
              <dd className="font-mono text-xs">{detection.configVersion || '—'}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">处理默认（服务端）</dt>
              <dd>见服务端默认（五层 pipeline），本页不虚构参数表</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">最近抽样通过率</dt>
              <dd>
                {opsMetrics ? formatRate(opsMetrics.detectionPassRate) : '暂无抽样数据'}
                {opsMetrics?.queueDepth != null ? ` · 队列深度 ${opsMetrics.queueDepth}` : ''}
              </dd>
            </div>
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">暂无最终检测合同；加载后显示摘要。</p>
        )}
        {importContract ? (
          <p className="text-xs text-muted-foreground">
            URL 导入：{importContract.enabled ? '启用' : '停用'} · Base{' '}
            <span className="break-all font-mono">{importContract.baseUrl || '—'}</span>
          </p>
        ) : null}
        <div className="space-y-1 border-t pt-3 text-xs text-muted-foreground">
          <p>
            回退说明：若需改回上一检测模型，请到「系统管理 → 模型 API」对「最终检测」使用现有「修改」对话框改回
            modelId / Base URL；本页只读，不会自动改模型。
          </p>
          <p data-testid="strategy-pass-score-note">
            话术对齐：调用成功 ≠ 业务通过 ≠ 已收费；通过线仍为服务端 PASS_SCORE（本包未修改）。
            production_billing 保持 false。
          </p>
        </div>
      </section>

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
                <RpTh>能力</RpTh>
                <RpTh>状态</RpTh>
                <RpTh>缺口</RpTh>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <RpSkeletonRows colSpan={8} />
              ) : visibleItems.length === 0 ? (
                <RpEmptyState
                  colSpan={8}
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
                      <td className="whitespace-nowrap">{item.enabled ? '启用' : '停用'}</td>
                      <td className="max-w-[16rem] truncate" title={item.gapNote}>
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
          <p className="text-xs text-muted-foreground">
            凭据引用：{capabilityTarget.credentialRef || '空'}
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
            <details className="rounded-md border bg-muted/30 p-3 text-xs">
              <summary className="cursor-pointer font-medium">关键限制 / 缺口（技术备注）</summary>
              <div className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap text-muted-foreground">
                {capabilityTarget.gapNote}
              </div>
            </details>
          ) : null}
        </RpDialog>
      ) : null}
    </main>
  )
}
