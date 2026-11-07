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
}

export default function RealphotosPresetsPage() {
  const [items, setItems] = useState<Preset[]>([])
  const [code, setCode] = useState('')
  const [brand, setBrand] = useState('Honeybadger')
  const [model, setModel] = useState('')
  const [gpsMode, setGpsMode] = useState('none')
  const [message, setMessage] = useState('')
  const [imports, setImports] = useState<string[]>([])

  async function load() {
    const data = await apiFetch<{ items: Preset[] }>('/api/v1/realphotos/device-presets')
    const imported = await apiFetch<{ importedBrands: string[] }>('/api/v1/realphotos/device-preset-imports')
    setItems(data.items)
    setImports(imported.importedBrands)
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

  async function createPreset() {
    try {
      await apiFetch('/api/v1/realphotos/device-presets', {
        method: 'POST',
        body: JSON.stringify({ code, brand, model, gpsMode, deviceType: 'phone', enabled: true }),
      })
      setMessage('已保存预设')
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '保存失败')
    }
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">设备预设</h1>
      <p className="text-sm text-muted-foreground">GPS 只配在预设上。处理页不提供单独选点。导入记录：{imports.length === 0 ? '尚无' : imports.join('、')}</p>
      <p className="text-sm">{message}</p>
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
              <td className="border px-2 py-1">
                <button className="border px-2 py-1" type="button" onClick={() => void setEnabled(item.code, !item.enabled)}>
                  {item.enabled ? '停用' : '启用'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <section className="space-y-2">
        <h2 className="text-sm font-medium">新建虚构预设</h2>
        <input className="border px-2 py-1 text-sm" placeholder="编号" value={code} onChange={(event) => setCode(event.target.value)} />
        <input className="ml-2 border px-2 py-1 text-sm" placeholder="品牌" value={brand} onChange={(event) => setBrand(event.target.value)} />
        <input className="ml-2 border px-2 py-1 text-sm" placeholder="型号" value={model} onChange={(event) => setModel(event.target.value)} />
        <select className="ml-2 border px-2 py-1 text-sm" value={gpsMode} onChange={(event) => setGpsMode(event.target.value)}>
          <option value="none">none</option>
          <option value="fixed">fixed</option>
          <option value="random_by_scene">random_by_scene</option>
        </select>
        <button className="ml-2 border px-3 py-1 text-sm" type="button" onClick={() => void createPreset()}>保存</button>
      </section>
    </main>
  )
}
