'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

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
}

type VersionRow = {
  presetCode: string
  versionNo: number
  snapshot: Record<string, unknown>
  createdAt?: string | null
}

export default function RealphotosPresetsPage() {
  const [items, setItems] = useState<Preset[]>([])
  const [code, setCode] = useState('')
  const [deviceType, setDeviceType] = useState('phone')
  const [brand, setBrand] = useState('Honeybadger')
  const [model, setModel] = useState('')
  const [gpsMode, setGpsMode] = useState('none')
  const [iso, setIso] = useState('')
  const [shutter, setShutter] = useState('')
  const [aperture, setAperture] = useState('')
  const [focalLength, setFocalLength] = useState('')
  const [lat, setLat] = useState('')
  const [lng, setLng] = useState('')
  const [altitude, setAltitude] = useState('')
  const [sceneRule, setSceneRule] = useState('')
  const [message, setMessage] = useState('')
  const [imports, setImports] = useState<string[]>([])
  const [versions, setVersions] = useState<VersionRow[]>([])
  const [versionCode, setVersionCode] = useState('')

  async function load() {
    const data = await apiFetch<{ items: Preset[] }>('/api/v1/realphotos/device-presets')
    const imported = await apiFetch<{ importedBrands: string[]; items?: unknown[] }>(
      '/api/v1/realphotos/device-preset-imports',
    )
    setItems(data.items)
    setImports(imported.importedBrands || [])
  }

  useEffect(() => {
    void load().catch((error: unknown) => setMessage(error instanceof ApiError ? error.message : '预设读取失败'))
  }, [])

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

  function fillForm(item: Preset) {
    setCode(item.code)
    setDeviceType(item.deviceType)
    setBrand(item.brand)
    setModel(item.model)
    setGpsMode(item.gpsMode)
    setIso(item.iso || '')
    setShutter(item.shutter || '')
    setAperture(item.aperture || '')
    setFocalLength(item.focalLength || '')
  }

  async function savePreset() {
    const gpsConfig =
      gpsMode === 'fixed'
        ? { latitude: lat, longitude: lng, altitude }
        : gpsMode === 'random_by_scene'
          ? { sceneRule }
          : undefined
    try {
      await apiFetch('/api/v1/realphotos/device-presets', {
        method: 'POST',
        body: JSON.stringify({
          code,
          brand,
          model,
          gpsMode,
          deviceType,
          enabled: true,
          iso,
          shutter,
          aperture,
          focalLength,
          gpsConfig,
        }),
      })
      setMessage(
        gpsMode === 'fixed' || gpsMode === 'random_by_scene'
          ? '已保存预设与版本快照。GPS 配置已记录；五层写入未接通，禁止静默假装已写入。'
          : '已保存预设与版本快照',
      )
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

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">设备预设</h1>
      <p className="text-sm text-muted-foreground">
        GPS 只配在预设上。处理页不提供单独选点。不含作者/版权、IP-GEO。导入记录空态诚实展示。
      </p>
      <p className="text-sm">{message}</p>
      <section className="space-y-2">
        <h2 className="text-sm font-medium">导入记录</h2>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="border px-2 py-1 text-left">品牌</th>
              <th className="border px-2 py-1 text-left">说明</th>
            </tr>
          </thead>
          <tbody>
            {imports.length === 0 ? (
              <tr>
                <td className="border px-2 py-1" colSpan={2}>
                  尚无导入记录（不伪造已导入品牌）
                </td>
              </tr>
            ) : (
              imports.map((brandName) => (
                <tr key={brandName}>
                  <td className="border px-2 py-1">{brandName}</td>
                  <td className="border px-2 py-1">已登记</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
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
          {items.map((item) => (
            <tr key={item.code}>
              <td className="border px-2 py-1">{item.code}</td>
              <td className="border px-2 py-1">{item.deviceType}</td>
              <td className="border px-2 py-1">{item.brand}</td>
              <td className="border px-2 py-1">{item.model}</td>
              <td className="border px-2 py-1">{item.gpsMode}</td>
              <td className="border px-2 py-1">{item.enabled ? '启用' : '停用'}</td>
              <td className="border px-2 py-1 space-x-1">
                <button className="border px-2 py-1" type="button" onClick={() => fillForm(item)}>
                  编辑
                </button>
                <button className="border px-2 py-1" type="button" onClick={() => void setEnabled(item.code, !item.enabled)}>
                  {item.enabled ? '停用' : '启用'}
                </button>
                <button className="border px-2 py-1" type="button" onClick={() => void loadVersions(item.code)}>
                  版本
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <section className="space-y-3 border p-3">
        <h2 className="text-sm font-medium">新建 / 编辑预设</h2>
        <div className="space-y-2">
          <h3 className="text-xs font-medium">基本信息</h3>
          <input className="border px-2 py-1 text-sm" placeholder="编号" value={code} onChange={(event) => setCode(event.target.value)} />
          <select className="ml-2 border px-2 py-1 text-sm" value={deviceType} onChange={(event) => setDeviceType(event.target.value)}>
            <option value="phone">phone</option>
            <option value="camera">camera</option>
          </select>
          <input className="ml-2 border px-2 py-1 text-sm" placeholder="品牌" value={brand} onChange={(event) => setBrand(event.target.value)} />
          <input className="ml-2 border px-2 py-1 text-sm" placeholder="型号" value={model} onChange={(event) => setModel(event.target.value)} />
        </div>
        <div className="space-y-2">
          <h3 className="text-xs font-medium">拍摄参数</h3>
          <input className="border px-2 py-1 text-sm" placeholder="ISO" value={iso} onChange={(event) => setIso(event.target.value)} />
          <input className="ml-2 border px-2 py-1 text-sm" placeholder="快门" value={shutter} onChange={(event) => setShutter(event.target.value)} />
          <input className="ml-2 border px-2 py-1 text-sm" placeholder="光圈" value={aperture} onChange={(event) => setAperture(event.target.value)} />
        </div>
        <div className="space-y-2">
          <h3 className="text-xs font-medium">图像属性</h3>
          <input
            className="border px-2 py-1 text-sm"
            placeholder="焦距"
            value={focalLength}
            onChange={(event) => setFocalLength(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <h3 className="text-xs font-medium">EXIF / GPS</h3>
          <select className="border px-2 py-1 text-sm" value={gpsMode} onChange={(event) => setGpsMode(event.target.value)}>
            <option value="none">none</option>
            <option value="fixed">fixed</option>
            <option value="random_by_scene">random_by_scene</option>
          </select>
          {gpsMode === 'fixed' ? (
            <div className="mt-2 space-x-2">
              <input className="border px-2 py-1 text-sm" placeholder="纬度" value={lat} onChange={(event) => setLat(event.target.value)} />
              <input className="border px-2 py-1 text-sm" placeholder="经度" value={lng} onChange={(event) => setLng(event.target.value)} />
              <input
                className="border px-2 py-1 text-sm"
                placeholder="海拔"
                value={altitude}
                onChange={(event) => setAltitude(event.target.value)}
              />
              <p className="mt-1 text-xs text-muted-foreground">写入未接通：可保存配置，处理结果不得静默假装已写入 GPS。</p>
            </div>
          ) : null}
          {gpsMode === 'random_by_scene' ? (
            <div className="mt-2">
              <input
                className="w-full max-w-md border px-2 py-1 text-sm"
                placeholder="场景规则"
                value={sceneRule}
                onChange={(event) => setSceneRule(event.target.value)}
              />
              <p className="mt-1 text-xs text-muted-foreground">写入未接通：可保存配置，处理结果须标明未写入。</p>
            </div>
          ) : null}
        </div>
        <button className="border px-3 py-1 text-sm" type="button" onClick={() => void savePreset()}>
          保存并生成版本快照
        </button>
      </section>
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
                      {String(row.snapshot.gpsMode || '')}
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
