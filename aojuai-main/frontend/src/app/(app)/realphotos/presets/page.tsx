'use client'

import { useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { ApiError, apiFetch } from '@/lib/api'
import { deviceTypeLabel, gpsModeLabel } from '@/lib/realphotos-labels'
import {
  EXCLUDED_IP_GEO_KEYS,
  GPS_COORD_LABELS,
  PRESET_FIELD_DEFS,
  PRESET_FORM_TABS,
  REMOVED_PROTOTYPE_ONLY_KEYS,
  presetDisplayName,
  type PresetFieldDef,
} from '@/lib/realphotos-preset-fields'
import { optionsForPresetField } from '@/lib/realphotos-preset-options'

const PRESET_PAGE_SIZE = 20

type Preset = {
  code: string
  name?: string | null
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
  name: string
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
  name: '',
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

function slugCodeFromName(name: string): string {
  const base = String(name || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48)
  const stamp = Date.now().toString(36).slice(-4)
  return `admin-${base || 'preset'}-${stamp}`.slice(0, 64)
}

function fieldValue(preset: Preset, field: PresetFieldDef): string {
  if (field.key === 'name') {
    return String(preset.name || preset.legacyParameters?.name || '').trim()
  }
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
    if (field.column || field.key === 'name') continue
    legacy[field.key] = fieldValue(item, field)
  }
  return {
    code: item.code,
    name: String(item.name || item.legacyParameters?.name || ''),
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
  const [search, setSearch] = useState('')

  async function load() {
    const data = await apiFetch<{ items: Preset[] }>('/api/v1/realphotos/device-presets')
    setItems(data.items)
  }

  useEffect(() => {
    void load().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '预设读取失败'))
  }, [])

  const filteredItems = useMemo(
    () =>
      items.filter((item) =>
        matchSearchText(
          search,
          presetDisplayName(item),
          item.code,
          item.brand,
          item.model,
          item.deviceType,
          deviceTypeLabel(item.deviceType),
        ),
      ),
    [items, search],
  )
  const pageCount = Math.max(1, Math.ceil(filteredItems.length / PRESET_PAGE_SIZE))
  const pageItems = useMemo(
    () => filteredItems.slice((page - 1) * PRESET_PAGE_SIZE, page * PRESET_PAGE_SIZE),
    [filteredItems, page],
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
    if (!String(form.name || '').trim()) missing.push('预设名称')
    if (!String(form.brand || '').trim()) missing.push('品牌')
    if (!String(form.model || '').trim()) missing.push('型号')
    if (!String(form.iso || '').trim()) missing.push('ISO')
    if (!String(form.shutter || '').trim()) missing.push('快门')
    if (!String(form.aperture || '').trim()) missing.push('光圈')
    if (!String(form.focalLength || '').trim()) missing.push('焦距')
    if (['honeybadger', 'runtimecam', 'bizcam'].includes(String(form.brand || '').trim().toLowerCase())) {
      setMessage('禁止使用占位品牌（Honeybadger / RuntimeCam / BizCam）；请填写真实设备品牌')
      return
    }
    if (missing.length) {
      setMessage(`预设缺少必填字段：${missing.join('、')}（启用前须补全，不会静默填默认值）`)
      return
    }
    const code = formMode === 'edit' ? form.code : form.code.trim() || slugCodeFromName(form.name)
    const gpsConfig =
      form.gpsMode === 'fixed'
        ? { latitude: form.lat, longitude: form.lng, altitude: form.altitude }
        : form.gpsMode === 'random_by_scene'
          ? { sceneRule: form.sceneRule }
          : undefined
    const legacyParameters: Record<string, string> = { ...form.legacy }
    legacyParameters.name = form.name.trim()
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
    for (const key of EXCLUDED_IP_GEO_KEYS) {
      delete legacyParameters[key]
    }
    for (const key of REMOVED_PROTOTYPE_ONLY_KEYS) {
      delete legacyParameters[key]
    }
    try {
      await apiFetch('/api/v1/realphotos/device-presets', {
        method: 'POST',
        body: JSON.stringify({
          code,
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

  function renderFieldInput(field: PresetFieldDef) {
    if (field.formHidden) return null

    let value = ''
    if (field.key === 'name') value = form.name
    else if (field.column === 'code') value = form.code
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
      if (field.key === 'name') patchForm('name', next)
      else if (field.column === 'code') patchForm('code', next)
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
      </label>
    )

    const selectOptions =
      field.options && field.options.length > 0
        ? field.options
        : field.kind === 'select'
          ? optionsForPresetField(field.column || field.key, form.deviceType, value)
          : []

    if (field.kind === 'select' && selectOptions.length > 0) {
      return (
        <div key={field.key} className="min-w-[10rem] flex-1">
          {label}
          <select
            className="w-full border px-2 py-1 text-sm"
            value={value}
            onChange={(event) => onChange(event.target.value)}
          >
            {selectOptions.map((opt) => (
              <option key={`${opt.value}::${opt.label}`} value={opt.value}>
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
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
    )
  }

  function renderGpsDetail(preset: Preset) {
    const cfg = preset.gpsConfig
    if (!cfg || typeof cfg !== 'object') return null
    const rows: { label: string; value: string }[] = []
    const lat = cfg.latitude
    const lng = cfg.longitude
    const alt = cfg.altitude
    const scene = cfg.sceneRule ?? preset.legacyParameters?.scene_type
    if (lat != null && String(lat) !== '') rows.push({ label: GPS_COORD_LABELS.latitude, value: String(lat) })
    if (lng != null && String(lng) !== '') rows.push({ label: GPS_COORD_LABELS.longitude, value: String(lng) })
    if (alt != null && String(alt) !== '') rows.push({ label: GPS_COORD_LABELS.altitude, value: String(alt) })
    if (scene != null && String(scene) !== '') rows.push({ label: '场景规则', value: String(scene) })
    if (!rows.length) return null
    return (
      <div className="space-y-1 border-t pt-3">
        <p className="text-xs text-muted-foreground">GPS 配置</p>
        {rows.map((row) => (
          <p key={row.label} className="text-sm">
            <span className="text-muted-foreground">{row.label}：</span>
            {row.value}
          </p>
        ))}
      </div>
    )
  }

  function renderTabFields(tabId: (typeof PRESET_FORM_TABS)[number]['id'], mode: 'form' | 'detail') {
    const fields = PRESET_FIELD_DEFS.filter((field) => field.group === tabId)
    if (mode === 'detail' && detail) {
      const visible = fields.filter((field) => {
        if (field.formHidden && field.key === 'code') return false
        const value = fieldValue(detail, field)
        return Boolean(String(value || '').trim())
      })
      return (
        <div className="grid gap-2 sm:grid-cols-2">
          {visible.length === 0 ? <p className="text-sm text-muted-foreground">本页无已填参数</p> : null}
          {visible.map((field) => {
            const value = fieldValue(detail, field)
            return (
              <p key={field.key} className="text-sm">
                <span className="text-muted-foreground">{field.label}：</span>
                {value}
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
      <p className="text-sm">{message}</p>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button className="border px-3 py-1" type="button" onClick={openCreate}>
          新增预设
        </button>
        <ListSearch
          value={search}
          placeholder="名称 / 品牌 / 型号"
          onChange={(value) => {
            setSearch(value)
            setPage(1)
          }}
        />
        <span>
          第 {page} / {pageCount} 页 · 每页 {PRESET_PAGE_SIZE} 条 · 共 {filteredItems.length} 条
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
            <th className="border px-2 py-1 text-left">预设名称</th>
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
                <td className="border px-2 py-1">{presetDisplayName(item)}</td>
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
                  <p className="text-xs text-muted-foreground">GPS 坐标（随预设模式保存）</p>
                  {form.gpsMode === 'fixed' ? (
                    <div className="flex flex-wrap gap-3">
                      <div className="min-w-[8rem] flex-1">
                        <label className="mb-1 block text-xs text-muted-foreground">{GPS_COORD_LABELS.latitude}</label>
                        <input
                          className="w-full border px-2 py-1 text-sm"
                          value={form.lat}
                          onChange={(event) => patchForm('lat', event.target.value)}
                        />
                      </div>
                      <div className="min-w-[8rem] flex-1">
                        <label className="mb-1 block text-xs text-muted-foreground">{GPS_COORD_LABELS.longitude}</label>
                        <input
                          className="w-full border px-2 py-1 text-sm"
                          value={form.lng}
                          onChange={(event) => patchForm('lng', event.target.value)}
                        />
                      </div>
                      <div className="min-w-[8rem] flex-1">
                        <label className="mb-1 block text-xs text-muted-foreground">{GPS_COORD_LABELS.altitude}</label>
                        <input
                          className="w-full border px-2 py-1 text-sm"
                          value={form.altitude}
                          onChange={(event) => patchForm('altitude', event.target.value)}
                        />
                      </div>
                    </div>
                  ) : null}
                  {form.gpsMode === 'random_by_scene' ? (
                    <div>
                      <label className="mb-1 block text-xs text-muted-foreground">场景规则</label>
                      <select
                        className="w-full border px-2 py-1 text-sm"
                        value={form.sceneRule}
                        onChange={(event) => patchForm('sceneRule', event.target.value)}
                      >
                        {optionsForPresetField('scene_type', form.deviceType, form.sceneRule).map((opt) => (
                          <option key={`${opt.value}::${opt.label}`} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
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
          aria-label={`预设 ${presetDisplayName(detail)} 详情`}
        >
          <div
            className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden border bg-background text-sm shadow"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
              <strong>预设详情 · {presetDisplayName(detail)}</strong>
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
              {detailTab === 'basic' ? (
                <p className="text-xs text-muted-foreground">状态：{detail.enabled ? '启用' : '停用'}</p>
              ) : null}
              {detailTab === 'exif' ? renderGpsDetail(detail) : null}
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
          <h2 className="text-sm font-medium">
            版本快照 ·{' '}
            {presetDisplayName(items.find((item) => item.code === versionCode) || { code: versionCode })}
          </h2>
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
                      {String(
                        (row.snapshot.legacyParameters as Record<string, unknown> | undefined)?.name ||
                          `${String(row.snapshot.brand || '')}/${String(row.snapshot.model || '')}`,
                      )}
                      {' · '}
                      {gpsModeLabel(String(row.snapshot.gpsMode || ''))}
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
