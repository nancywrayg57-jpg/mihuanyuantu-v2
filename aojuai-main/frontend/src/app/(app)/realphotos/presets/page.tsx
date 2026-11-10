'use client'

import { useEffect, useMemo, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'
import { deviceTypeLabel, gpsModeLabel } from '@/lib/realphotos-labels'
import {
  EXCLUDED_COPYRIGHT_KEYS,
  PRESET_FIELD_DEFS,
  PRESET_FORM_TABS,
  type PresetFieldDef,
} from '@/lib/realphotos-preset-fields'

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
  legacyParameters?: Record<string, unknown>
  copyrightPolicy?: string
}

type VersionRow = {
  presetCode: string
  versionNo: number
  snapshot: Record<string, unknown>
  createdAt?: string | null
}

type FormState = {
  code: string
  deviceType: string
  brand: string
  model: string
  gpsMode: string
  iso: string
  shutter: string
  aperture: string
  focalLength: string
  lat: string
  lng: string
  altitude: string
  sceneRule: string
  aiPositive: string
  aiNegative: string
  makerNote: string
  legacy: Record<string, string>
}

const emptyForm = (): FormState => ({
  code: '',
  deviceType: 'phone',
  brand: '',
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
  legacy: {},
})

function fieldValue(preset: Preset, field: PresetFieldDef): string {
  if (field.group === 'copyright_excluded') return ''
  if (field.column === 'code') return preset.code || ''
  if (field.column === 'deviceType') return preset.deviceType || ''
  if (field.column === 'brand') return preset.brand || ''
  if (field.column === 'model') return preset.model || ''
  if (field.column === 'iso') return preset.iso || ''
  if (field.column === 'shutter') return preset.shutter || ''
  if (field.column === 'aperture') return preset.aperture || ''
  if (field.column === 'focalLength') return preset.focalLength || ''
  if (field.column === 'gpsMode') return preset.gpsMode || 'none'
  if (field.column === 'makerNote') return preset.makerNote || ''
  if (field.column === 'aiPositivePrompt') return preset.aiPositivePrompt || ''
  if (field.column === 'aiNegativePrompt') return preset.aiNegativePrompt || ''
  const lp = preset.legacyParameters || {}
  const raw = lp[field.key]
  return raw == null || raw === '' ? '' : String(raw)
}

function formFromPreset(item: Preset): FormState {
  const legacy: Record<string, string> = {}
  for (const field of PRESET_FIELD_DEFS) {
    if (field.column || field.group === 'copyright_excluded') continue
    legacy[field.key] = fieldValue(item, field)
  }
  return {
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
    sceneRule: String(item.gpsConfig?.sceneRule ?? item.legacyParameters?.scene_type ?? ''),
    aiPositive: item.aiPositivePrompt || '',
    aiNegative: item.aiNegativePrompt || '',
    makerNote: item.makerNote || '',
    legacy,
  }
}

export default function RealphotosPresetsPage() {
  const [items, setItems] = useState<Preset[]>([])
  const [form, setForm] = useState<FormState>(emptyForm)
  const [message, setMessage] = useState('')
  const [versions, setVersions] = useState<VersionRow[]>([])
  const [versionCode, setVersionCode] = useState('')
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [formTab, setFormTab] = useState<(typeof PRESET_FORM_TABS)[number]['id']>('basic')
  const [detail, setDetail] = useState<Preset | null>(null)
  const [detailTab, setDetailTab] = useState<(typeof PRESET_FORM_TABS)[number]['id']>('basic')

  async function load() {
    const data = await apiFetch<{ items: Preset[] }>('/api/v1/realphotos/device-presets')
    setItems(data.items)
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
    setForm(emptyForm())
    setFormTab('basic')
    setFormOpen(true)
  }

  async function openEdit(item: Preset) {
    try {
      const full = await apiFetch<Preset>(`/api/v1/realphotos/device-presets/${encodeURIComponent(item.code)}`)
      setFormMode('edit')
      setForm(formFromPreset(full))
      setFormTab('basic')
      setFormOpen(true)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '读取预设详情失败')
    }
  }

  async function openDetail(item: Preset) {
    try {
      const full = await apiFetch<Preset>(`/api/v1/realphotos/device-presets/${encodeURIComponent(item.code)}`)
      setDetail(full)
      setDetailTab('basic')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '读取预设详情失败')
    }
  }

  async function savePreset() {
    const missing: string[] = []
    if (!String(form.brand || '').trim()) missing.push('品牌')
    if (!String(form.model || '').trim()) missing.push('型号')
    if (!String(form.iso || '').trim()) missing.push('ISO')
    if (!String(form.shutter || '').trim()) missing.push('快门')
    if (!String(form.aperture || '').trim()) missing.push('光圈')
    if (!String(form.focalLength || '').trim()) missing.push('焦距')
    if (String(form.brand || '').trim().toLowerCase() === 'honeybadger') {
      setMessage('禁止使用 Honeybadger 占位品牌；请填写真实设备品牌')
      return
    }
    if (missing.length) {
      setMessage(`预设缺少必填字段：${missing.join('、')}（启用前须补全，不会静默填默认值）`)
      return
    }
    const gpsConfig =
      form.gpsMode === 'fixed'
        ? { latitude: form.lat, longitude: form.lng, altitude: form.altitude }
        : form.gpsMode === 'random_by_scene'
          ? { sceneRule: form.sceneRule }
          : undefined
    const legacyParameters: Record<string, string> = { ...form.legacy }
    legacyParameters.camera_make = form.brand
    legacyParameters.camera_model = form.model
    legacyParameters.iso = form.iso
    legacyParameters.shutter_speed = form.shutter
    legacyParameters.aperture = form.aperture
    legacyParameters.focal_length = form.focalLength
    legacyParameters.gps_mode = form.gpsMode
    if (form.makerNote) legacyParameters.maker_note_template = form.makerNote
    if (form.aiPositive) legacyParameters.ai_positive_prompt = form.aiPositive
    if (form.aiNegative) legacyParameters.ai_negative_prompt = form.aiNegative
    if (form.gpsMode === 'random_by_scene' && form.sceneRule) {
      legacyParameters.scene_type = form.sceneRule
    }
    for (const key of EXCLUDED_COPYRIGHT_KEYS) {
      delete legacyParameters[key]
    }
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
          legacyParameters,
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

  async function loadVersions(target: string) {
    try {
      const data = await apiFetch<{ items: VersionRow[] }>(`/api/v1/realphotos/device-presets/${target}/versions`)
      setVersionCode(target)
      setVersions(data.items || [])
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '版本读取失败')
    }
  }

  function patchForm<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function patchLegacy(key: string, value: string) {
    setForm((prev) => ({ ...prev, legacy: { ...prev.legacy, [key]: value } }))
  }

  function renderFieldInput(field: PresetFieldDef, readOnly = false) {
    if (field.group === 'copyright_excluded') {
      return (
        <p key={field.key} className="text-xs text-muted-foreground">
          {field.label}：产品策略不采集（PRD / AGENTS 禁止客户路径写入作者、版权、IP-GEO）
        </p>
      )
    }
    let value = ''
    if (field.column === 'code') value = form.code
    else if (field.column === 'deviceType') value = form.deviceType
    else if (field.column === 'brand') value = form.brand
    else if (field.column === 'model') value = form.model
    else if (field.column === 'iso') value = form.iso
    else if (field.column === 'shutter') value = form.shutter
    else if (field.column === 'aperture') value = form.aperture
    else if (field.column === 'focalLength') value = form.focalLength
    else if (field.column === 'gpsMode') value = form.gpsMode
    else if (field.column === 'makerNote') value = form.makerNote
    else if (field.column === 'aiPositivePrompt') value = form.aiPositive
    else if (field.column === 'aiNegativePrompt') value = form.aiNegative
    else value = form.legacy[field.key] || ''

    const onChange = (next: string) => {
      if (field.column === 'code') patchForm('code', next)
      else if (field.column === 'deviceType') patchForm('deviceType', next)
      else if (field.column === 'brand') patchForm('brand', next)
      else if (field.column === 'model') patchForm('model', next)
      else if (field.column === 'iso') patchForm('iso', next)
      else if (field.column === 'shutter') patchForm('shutter', next)
      else if (field.column === 'aperture') patchForm('aperture', next)
      else if (field.column === 'focalLength') patchForm('focalLength', next)
      else if (field.column === 'gpsMode') patchForm('gpsMode', next)
      else if (field.column === 'makerNote') patchForm('makerNote', next)
      else if (field.column === 'aiPositivePrompt') patchForm('aiPositive', next)
      else if (field.column === 'aiNegativePrompt') patchForm('aiNegative', next)
      else patchLegacy(field.key, next)
    }

    const label = (
      <label className="mb-1 block text-xs text-muted-foreground">
        {field.label}
        {field.required ? ' *' : ''}
        {field.sparse ? ' · 旧版极少/无，空态诚实' : ''}
      </label>
    )

    if (field.kind === 'select' && field.options) {
      return (
        <div key={field.key} className="min-w-[10rem] flex-1">
          {label}
          <select
            className="w-full border px-2 py-1 text-sm"
            value={value}
            disabled={readOnly || (field.column === 'code' && formMode === 'edit')}
            onChange={(event) => onChange(event.target.value)}
          >
            {field.options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )
    }
    if (field.kind === 'textarea') {
      return (
        <div key={field.key} className="w-full">
          {label}
          <textarea
            className="w-full border px-2 py-1 text-sm"
            rows={3}
            value={value}
            disabled={readOnly}
            onChange={(event) => onChange(event.target.value)}
          />
        </div>
      )
    }
    return (
      <div key={field.key} className="min-w-[10rem] flex-1">
        {label}
        <input
          className="w-full border px-2 py-1 text-sm"
          value={value}
          disabled={readOnly || (field.column === 'code' && formMode === 'edit')}
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
    )
  }

  function renderTabFields(tabId: (typeof PRESET_FORM_TABS)[number]['id'], mode: 'form' | 'detail') {
    const fields = PRESET_FIELD_DEFS.filter((field) => field.group === tabId)
    if (mode === 'detail' && detail) {
      return (
        <div className="grid gap-2 sm:grid-cols-2">
          {fields.map((field) => {
            if (field.group === 'copyright_excluded') {
              return (
                <p key={field.key} className="text-xs text-muted-foreground sm:col-span-2">
                  {field.label}：产品策略不采集（PRD 排除），不可编辑写入
                </p>
              )
            }
            const value = fieldValue(detail, field)
            return (
              <p key={field.key} className="text-sm">
                <span className="text-muted-foreground">{field.label}：</span>
                {value || (field.sparse ? '（空 · 旧版无此键或不采集）' : '（空）')}
              </p>
            )
          })}
        </div>
      )
    }
    return <div className="flex flex-wrap gap-3">{fields.map((field) => renderFieldInput(field))}</div>
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">设备预设</h1>
      <p className="text-sm text-muted-foreground">
        运行台账启停/编辑/详情。GPS 只配在预设上。不含作者/版权、IP-GEO。导入记录区已移除（405
        旧版已全量激活进台账；脚本 API 仍保留）。禁止 Honeybadger 占位品牌。
      </p>
      <p className="text-sm">{message}</p>

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
                  <button className="border px-2 py-1" type="button" onClick={() => void openDetail(item)}>
                    查看详情
                  </button>
                  <button className="border px-2 py-1" type="button" onClick={() => void openEdit(item)}>
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
            className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden border bg-background text-sm shadow"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
              <h2 className="text-sm font-medium">{formMode === 'create' ? '新增预设' : '编辑预设'}</h2>
              <button className="border px-2 py-0.5" type="button" onClick={() => setFormOpen(false)}>
                关闭
              </button>
            </div>
            <div className="flex gap-1 overflow-x-auto border-b px-4 py-2">
              {PRESET_FORM_TABS.map((tab) => (
                <button
                  key={tab.id}
                  className={`border px-3 py-1 whitespace-nowrap ${formTab === tab.id ? 'bg-muted font-medium' : ''}`}
                  type="button"
                  data-preset-form-tab={tab.id}
                  onClick={() => setFormTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto p-4" data-preset-form-section={formTab}>
              {renderTabFields(formTab, 'form')}
              {formTab === 'exif' ? (
                <div className="space-y-2 border-t pt-3">
                  <p className="text-xs text-muted-foreground">GPS 坐标（按模式；写入合同仍走预设 gpsConfig）</p>
                  {form.gpsMode === 'fixed' ? (
                    <div className="flex flex-wrap gap-2">
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
                    </div>
                  ) : null}
                  {form.gpsMode === 'random_by_scene' ? (
                    <input
                      className="w-full border px-2 py-1 text-sm"
                      placeholder="场景规则"
                      value={form.sceneRule}
                      onChange={(event) => patchForm('sceneRule', event.target.value)}
                    />
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="border-t px-4 py-3">
              <button className="border px-3 py-1 text-sm" type="button" onClick={() => void savePreset()}>
                保存并生成版本快照
              </button>
            </div>
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
            className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden border bg-background text-sm shadow"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
              <strong>预设详情 · {detail.code}</strong>
              <button className="border px-2 py-0.5" type="button" onClick={() => setDetail(null)}>
                关闭
              </button>
            </div>
            <div className="flex gap-1 overflow-x-auto border-b px-4 py-2">
              {PRESET_FORM_TABS.map((tab) => (
                <button
                  key={tab.id}
                  className={`border px-3 py-1 whitespace-nowrap ${detailTab === tab.id ? 'bg-muted font-medium' : ''}`}
                  type="button"
                  onClick={() => setDetailTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {renderTabFields(detailTab, 'detail')}
              <p className="text-xs text-muted-foreground">
                来源：{detail.source || '—'} · 状态：{detail.enabled ? '启用' : '停用'} · legacy 键数：
                {Object.keys(detail.legacyParameters || {}).length}
              </p>
              {detail.gpsConfig ? <p className="text-xs">GPS 配置：{JSON.stringify(detail.gpsConfig)}</p> : null}
              <button
                className="border px-2 py-1"
                type="button"
                onClick={() => {
                  setDetail(null)
                  void openEdit(detail)
                }}
              >
                去编辑
              </button>
            </div>
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
                      {row.snapshot.legacyParameters
                        ? ` · legacy=${Object.keys(row.snapshot.legacyParameters as object).length}`
                        : ''}
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
