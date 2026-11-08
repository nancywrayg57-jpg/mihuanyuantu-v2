'use client'

import { useEffect, useMemo, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'
import { deviceTypeLabel, gpsModeLabel } from '@/lib/realphotos-labels'

const DEVICE_TYPES = ['phone', 'dslr', 'mirrorless', 'action'] as const
const PRESET_PAGE_SIZE = 20

type Preset = {
  code: string
  deviceType: string
  brand: string
  model: string
  gpsMode: string
  enabled: boolean
  iso?: string
  shutter?: string
  aperture?: string
  focalLength?: string
  aiPositivePrompt?: string
  aiNegativePrompt?: string
  makerNote?: string
  gpsConfig?: Record<string, unknown> | null
  source?: string | null
  gpsWritable?: boolean
  gpsWillSkip?: boolean
  gpsWritableReason?: string
}

type VersionRow = {
  presetCode: string
  versionNo: number
  snapshot: Record<string, unknown>
  createdAt?: string | null
}

type ImportRow = {
  sourceId?: number | string | null
  templateRef?: string | null
  deviceDisplay?: string | null
  legacyCategory?: string | null
  visibility?: string | null
  activationStatus?: string | null
  reviewBucket?: string | null
  makerNoteImported?: boolean
  runtimeActivated?: boolean
}

const emptyForm = {
  code: '',
  deviceType: 'phone',
  brand: 'Honeybadger',
  model: '',
  gpsMode: 'none',
  iso: '',
  shutter: '',
  aperture: '',
  focalLength: '',
  lat: '',
  lng: '',
  altitude: '',
  sceneRule: '',
  aiPositive: '',
  aiNegative: '',
  makerNote: '',
}

export default function RealphotosPresetsPage() {
  const [items, setItems] = useState<Preset[]>([])
  const [form, setForm] = useState(emptyForm)
  const [message, setMessage] = useState('')
  const [importRows, setImportRows] = useState<ImportRow[]>([])
  const [importTotal, setImportTotal] = useState(0)
  const [importNote, setImportNote] = useState('')
  const [versions, setVersions] = useState<VersionRow[]>([])
  const [versionCode, setVersionCode] = useState('')
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [detail, setDetail] = useState<Preset | null>(null)

  async function load() {
    const data = await apiFetch<{ items: Preset[] }>('/api/v1/realphotos/device-presets')
    const imported = await apiFetch<{
      importedBrands: string[]
      items?: ImportRow[]
      total?: number
      note?: string
    }>('/api/v1/realphotos/device-preset-imports')
    setItems(data.items)
    setImportRows(imported.items || [])
    setImportTotal(Number(imported.total || 0))
    setImportNote(
      imported.importedBrands?.length
        ? `已激活导入品牌：${imported.importedBrands.join(', ')}`
        : imported.note || '尚无激活导入品牌（不伪造 MakerNote 已导入）',
    )
  }

  useEffect(() => {
    void load().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '预设读取失败'))
  }, [])

  const pageCount = Math.max(1, Math.ceil(items.length / PRESET_PAGE_SIZE))
  const pageItems = useMemo(
    () => items.slice((page - 1) * PRESET_PAGE_SIZE, page * PRESET_PAGE_SIZE),
    [items, page],
  )

  async function setEnabled(target: string, enabled: boolean) {
    try {
      await apiFetch(`/api/v1/realphotos/device-presets/${target}/enabled`, {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      })
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '更新失败')
    }
  }

  function openCreate() {
    setFormMode('create')
    setForm(emptyForm)
    setFormOpen(true)
  }

  function openEdit(item: Preset) {
    setFormMode('edit')
    setForm({
      code: item.code,
      deviceType: item.deviceType,
      brand: item.brand,
      model: item.model,
      gpsMode: item.gpsMode,
      iso: item.iso || '',
      shutter: item.shutter || '',
      aperture: item.aperture || '',
      focalLength: item.focalLength || '',
      lat: String(item.gpsConfig?.latitude ?? ''),
      lng: String(item.gpsConfig?.longitude ?? ''),
      altitude: String(item.gpsConfig?.altitude ?? ''),
      sceneRule: String(item.gpsConfig?.sceneRule ?? ''),
      aiPositive: item.aiPositivePrompt || '',
      aiNegative: item.aiNegativePrompt || '',
      makerNote: item.makerNote || '',
    })
    setFormOpen(true)
  }

  async function savePreset() {
    const gpsConfig =
      form.gpsMode === 'fixed'
        ? { latitude: form.lat, longitude: form.lng, altitude: form.altitude }
        : form.gpsMode === 'random_by_scene'
          ? { sceneRule: form.sceneRule }
          : undefined
    try {
      await apiFetch('/api/v1/realphotos/device-presets', {
        method: 'POST',
        body: JSON.stringify({
          code: form.code,
          brand: form.brand,
          model: form.model,
          gpsMode: form.gpsMode,
          deviceType: form.deviceType,
          enabled: true,
          iso: form.iso,
          shutter: form.shutter,
          aperture: form.aperture,
          focalLength: form.focalLength,
          gpsConfig,
          aiPositivePrompt: form.aiPositive,
          aiNegativePrompt: form.aiNegative,
          makerNote: form.makerNote,
        }),
      })
      setMessage(
        form.gpsMode === 'fixed' || form.gpsMode === 'random_by_scene'
          ? '已保存预设与版本快照。GPS 将随处理任务写入 EXIF 并可回读。'
          : '已保存预设与版本快照',
      )
      setFormOpen(false)
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    }
  }

  async function activateImport(templateRef: string) {
    try {
      await apiFetch('/api/v1/realphotos/device-preset-imports/activate', {
        method: 'POST',
        body: JSON.stringify({ templateRef, enabled: true }),
      })
      setMessage(`已激活旧版导入 ${templateRef}`)
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '激活失败')
    }
  }

  async function loadVersions(target: string) {
    try {
      const data = await apiFetch<{ items: VersionRow[] }>(`/api/v1/realphotos/device-presets/${target}/versions`)
      setVersionCode(target)
      setVersions(data.items || [])
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '版本读取失败')
    }
  }

  function patchForm<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">设备预设</h1>
      <p className="text-sm text-muted-foreground">
        GPS 只配在预设上。处理页不提供单独选点。不含作者/版权、IP-GEO。导入为浏览旧版记录，不伪造 MakerNote
        已导入。运营批量「清除占位 / 一键导入全部」入口已按 UX 工单撤回（API 仍保留）。
      </p>
      <p className="text-sm">{message}</p>

      <section className="space-y-2">
        <h2 className="text-sm font-medium">导入记录 · 共 {importTotal} 条</h2>
        <p className="text-xs text-muted-foreground">{importNote}</p>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="border px-2 py-1 text-left">来源 ID</th>
              <th className="border px-2 py-1 text-left">设备</th>
              <th className="border px-2 py-1 text-left">可见性</th>
              <th className="border px-2 py-1 text-left">激活状态</th>
              <th className="border px-2 py-1 text-left">复核</th>
              <th className="border px-2 py-1 text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {importRows.length === 0 ? (
              <tr>
                <td className="border px-2 py-1" colSpan={6}>
                  尚无导入记录（与数据事实一致，不伪造已导入品牌）
                </td>
              </tr>
            ) : (
              importRows.map((row, index) => (
                <tr key={`${row.templateRef || row.sourceId || 'row'}-${index}`}>
                  <td className="border px-2 py-1">{row.sourceId ?? ''}</td>
                  <td className="border px-2 py-1">{row.deviceDisplay || row.templateRef || ''}</td>
                  <td className="border px-2 py-1">{row.visibility || ''}</td>
                  <td className="border px-2 py-1">{row.activationStatus || ''}</td>
                  <td className="border px-2 py-1">{row.reviewBucket || ''}</td>
                  <td className="border px-2 py-1">
                    {row.runtimeActivated ? (
                      '已启用'
                    ) : (
                      <button
                        className="border px-2 py-1"
                        type="button"
                        disabled={!row.templateRef}
                        onClick={() => row.templateRef && void activateImport(row.templateRef)}
                      >
                        激活
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button className="border px-3 py-1" type="button" onClick={openCreate}>
          新增预设
        </button>
        <span>
          第 {page} / {pageCount} 页 · 每页 {PRESET_PAGE_SIZE} 条 · 共 {items.length} 条
        </span>
        <button className="border px-2 py-1" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          上一页
        </button>
        <button
          className="border px-2 py-1"
          type="button"
          disabled={page >= pageCount}
          onClick={() => setPage((p) => p + 1)}
        >
          下一页
        </button>
      </div>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="border px-2 py-1 text-left">编号</th>
            <th className="border px-2 py-1 text-left">类型</th>
            <th className="border px-2 py-1 text-left">品牌</th>
            <th className="border px-2 py-1 text-left">型号</th>
            <th className="border px-2 py-1 text-left">GPS</th>
            <th className="border px-2 py-1 text-left">状态</th>
            <th className="border px-2 py-1 text-left">操作</th>
          </tr>
        </thead>
        <tbody>
          {pageItems.length === 0 ? (
            <tr>
              <td className="border px-2 py-1" colSpan={7}>
                暂无预设
              </td>
            </tr>
          ) : (
            pageItems.map((item) => (
              <tr key={item.code}>
                <td className="border px-2 py-1">{item.code}</td>
                <td className="border px-2 py-1">{deviceTypeLabel(item.deviceType)}</td>
                <td className="border px-2 py-1">{item.brand}</td>
                <td className="border px-2 py-1">{item.model}</td>
                <td className="border px-2 py-1">{gpsModeLabel(item.gpsMode)}</td>
                <td className="border px-2 py-1">{item.enabled ? '启用' : '停用'}</td>
                <td className="border px-2 py-1 space-x-1">
                  <button className="border px-2 py-1" type="button" onClick={() => setDetail(item)}>
                    查看详情
                  </button>
                  <button className="border px-2 py-1" type="button" onClick={() => openEdit(item)}>
                    编辑
                  </button>
                  <button
                    className="border px-2 py-1"
                    type="button"
                    onClick={() => void setEnabled(item.code, !item.enabled)}
                  >
                    {item.enabled ? '停用' : '启用'}
                  </button>
                  <button className="border px-2 py-1" type="button" onClick={() => void loadVersions(item.code)}>
                    版本
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {formOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setFormOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label={formMode === 'create' ? '新增预设' : '编辑预设'}
        >
          <div
            className="max-h-[90vh] w-full max-w-2xl space-y-3 overflow-y-auto border bg-background p-4 text-sm shadow"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex justify-between gap-2">
              <h2 className="text-sm font-medium">{formMode === 'create' ? '新增预设' : '编辑预设'}</h2>
              <button className="border px-2 py-0.5" type="button" onClick={() => setFormOpen(false)}>
                关闭
              </button>
            </div>
            <div className="space-y-2">
              <h3 className="text-xs font-medium">基本信息</h3>
              <input
                className="border px-2 py-1 text-sm"
                placeholder="编号"
                value={form.code}
                onChange={(event) => patchForm('code', event.target.value)}
                disabled={formMode === 'edit'}
              />
              <select
                className="ml-2 border px-2 py-1 text-sm"
                value={form.deviceType}
                onChange={(event) => patchForm('deviceType', event.target.value)}
              >
                {DEVICE_TYPES.map((item) => (
                  <option key={item} value={item}>
                    {deviceTypeLabel(item)}
                  </option>
                ))}
              </select>
              <input
                className="ml-2 border px-2 py-1 text-sm"
                placeholder="品牌"
                value={form.brand}
                onChange={(event) => patchForm('brand', event.target.value)}
              />
              <input
                className="ml-2 border px-2 py-1 text-sm"
                placeholder="型号"
                value={form.model}
                onChange={(event) => patchForm('model', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-xs font-medium">拍摄参数</h3>
              <input
                className="border px-2 py-1 text-sm"
                placeholder="ISO"
                value={form.iso}
                onChange={(event) => patchForm('iso', event.target.value)}
              />
              <input
                className="ml-2 border px-2 py-1 text-sm"
                placeholder="快门"
                value={form.shutter}
                onChange={(event) => patchForm('shutter', event.target.value)}
              />
              <input
                className="ml-2 border px-2 py-1 text-sm"
                placeholder="光圈"
                value={form.aperture}
                onChange={(event) => patchForm('aperture', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-xs font-medium">图像属性</h3>
              <input
                className="border px-2 py-1 text-sm"
                placeholder="焦距"
                value={form.focalLength}
                onChange={(event) => patchForm('focalLength', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-xs font-medium">AI 提示词（可空）</h3>
              <textarea
                className="w-full border px-2 py-1 text-sm"
                rows={3}
                placeholder="正向提示词"
                value={form.aiPositive}
                onChange={(event) => patchForm('aiPositive', event.target.value)}
              />
              <textarea
                className="w-full border px-2 py-1 text-sm"
                rows={2}
                placeholder="负向提示词"
                value={form.aiNegative}
                onChange={(event) => patchForm('aiNegative', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-xs font-medium">EXIF / GPS</h3>
              <input
                className="mb-2 w-full border px-2 py-1 text-sm"
                placeholder="MakerNote（可空；写入须可回读）"
                value={form.makerNote}
                onChange={(event) => patchForm('makerNote', event.target.value)}
              />
              <select
                className="border px-2 py-1 text-sm"
                value={form.gpsMode}
                onChange={(event) => patchForm('gpsMode', event.target.value)}
              >
                <option value="none">{gpsModeLabel('none')}</option>
                <option value="fixed">{gpsModeLabel('fixed')}</option>
                <option value="random_by_scene">{gpsModeLabel('random_by_scene')}</option>
              </select>
              {form.gpsMode === 'fixed' ? (
                <div className="mt-2 space-x-2">
                  <input
                    className="border px-2 py-1 text-sm"
                    placeholder="纬度"
                    value={form.lat}
                    onChange={(event) => patchForm('lat', event.target.value)}
                  />
                  <input
                    className="border px-2 py-1 text-sm"
                    placeholder="经度"
                    value={form.lng}
                    onChange={(event) => patchForm('lng', event.target.value)}
                  />
                  <input
                    className="border px-2 py-1 text-sm"
                    placeholder="海拔"
                    value={form.altitude}
                    onChange={(event) => patchForm('altitude', event.target.value)}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">固定坐标：处理任务会按配置写入 EXIF GPS，并可回读核对。</p>
                </div>
              ) : null}
              {form.gpsMode === 'random_by_scene' ? (
                <div className="mt-2">
                  <input
                    className="w-full border px-2 py-1 text-sm"
                    placeholder="场景规则"
                    value={form.sceneRule}
                    onChange={(event) => patchForm('sceneRule', event.target.value)}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">按场景随机：按场景规则抽样坐标写入 EXIF；不写入则选「不写入」。</p>
                </div>
              ) : null}
            </div>
            <button className="border px-3 py-1 text-sm" type="button" onClick={() => void savePreset()}>
              保存并生成版本快照
            </button>
          </div>
        </div>
      ) : null}

      {detail ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setDetail(null)}
          role="dialog"
          aria-modal="true"
          aria-label={`预设 ${detail.code} 详情`}
        >
          <div
            className="max-h-[90vh] w-full max-w-lg space-y-2 overflow-y-auto border bg-background p-4 text-sm shadow"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex justify-between gap-2">
              <strong>预设详情 · {detail.code}</strong>
              <button className="border px-2 py-0.5" type="button" onClick={() => setDetail(null)}>
                关闭
              </button>
            </div>
            <p>编号：{detail.code}</p>
            <p>类型：{deviceTypeLabel(detail.deviceType)}</p>
            <p>品牌：{detail.brand}</p>
            <p>型号：{detail.model}</p>
            <p>ISO / 快门 / 光圈 / 焦距：{detail.iso || '—'} / {detail.shutter || '—'} / {detail.aperture || '—'} / {detail.focalLength || '—'}</p>
            <p>正向提示词：{detail.aiPositivePrompt || '（空）'}</p>
            <p>负向提示词：{detail.aiNegativePrompt || '（空）'}</p>
            <p>MakerNote：{detail.makerNote || '（空）'}</p>
            <p>GPS 模式：{gpsModeLabel(detail.gpsMode)}</p>
            {detail.gpsConfig ? <p>GPS 配置：{JSON.stringify(detail.gpsConfig)}</p> : null}
            <p>
              GPS 可写：
              {detail.gpsWritable === false
                ? '否'
                : detail.gpsWillSkip
                  ? '可提交（运行时将跳过 GPS）'
                  : '是'}
            </p>
            {detail.gpsWritableReason ? (
              <p className={detail.gpsWritable === false || detail.gpsWillSkip ? 'text-destructive' : ''}>
                GPS 说明：{detail.gpsWritableReason}
              </p>
            ) : null}
            <p>状态：{detail.enabled ? '启用' : '停用'}</p>
            {detail.source ? <p>来源：{detail.source}</p> : null}
            <button
              className="border px-2 py-1"
              type="button"
              onClick={() => {
                setDetail(null)
                openEdit(detail)
              }}
            >
              去编辑
            </button>
          </div>
        </div>
      ) : null}

      {versionCode ? (
        <section className="space-y-2">
          <h2 className="text-sm font-medium">版本快照 · {versionCode}</h2>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="border px-2 py-1 text-left">版本</th>
                <th className="border px-2 py-1 text-left">时间</th>
                <th className="border px-2 py-1 text-left">快照摘要</th>
              </tr>
            </thead>
            <tbody>
              {versions.length === 0 ? (
                <tr>
                  <td className="border px-2 py-1" colSpan={3}>
                    尚无版本
                  </td>
                </tr>
              ) : (
                versions.map((row) => (
                  <tr key={`${row.presetCode}-${row.versionNo}`}>
                    <td className="border px-2 py-1">{row.versionNo}</td>
                    <td className="border px-2 py-1">{row.createdAt || ''}</td>
                    <td className="border px-2 py-1">
                      {String(row.snapshot.brand || '')}/{String(row.snapshot.model || '')}/
                      {gpsModeLabel(String(row.snapshot.gpsMode || ''))}
                      {row.snapshot.gpsWriteConnected === false ? ' · 写入未接通' : ''}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  )
}
