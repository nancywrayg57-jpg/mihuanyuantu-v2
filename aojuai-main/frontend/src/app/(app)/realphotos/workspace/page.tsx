'use client'

import { useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'
import { inspectLocalFile } from '@/lib/realphotos-s1'

type Preset = { code: string; model: string; deviceType: string }
type PendingAsset = { id: string; previewUrl: string }

export default function RealphotosWorkspacePage() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [presetCode, setPresetCode] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [notice, setNotice] = useState('')
  const [assetId, setAssetId] = useState('')
  const [library, setLibrary] = useState<PendingAsset[]>([])
  const [redoEnabled, setRedoEnabled] = useState(false)
  const [redoThreshold, setRedoThreshold] = useState(70)
  const [redoRounds, setRedoRounds] = useState(1)

  useEffect(() => {
    void apiFetch<{ enabled: boolean; scoreThreshold: number; extraRounds: number }>(
      '/api/v1/realphotos/redo-settings',
    )
      .then((data) => {
        setRedoEnabled(Boolean(data.enabled))
        setRedoThreshold(Number(data.scoreThreshold))
        setRedoRounds(Number(data.extraRounds))
      })
      .catch(() => undefined)
    void apiFetch<{ items: Preset[] }>('/api/v1/realphotos/presets')
      .then((data) => {
        setPresets(data.items || [])
        setPresetCode((data.items || [])[0]?.code || '')
      })
      .catch((error: unknown) => setNotice(error instanceof ApiError ? error.message : '预设加载失败'))
  }, [])

  async function onFile(next: File | null) {
    setFile(null)
    setAssetId('')
    if (!next) return
    const inspected = await inspectLocalFile(next)
    if (!inspected.ok) {
      setNotice(`前端拒绝：${inspected.message}。未上传，不会建立资产。`)
      return
    }
    setFile(next)
    setNotice(`前端通过：${inspected.width}×${inspected.height} ${inspected.kind}`)
  }

  async function upload() {
    if (!file) {
      setNotice('请先选择通过校验的图片')
      return
    }
    const body = new FormData()
    body.set('file', file)
    try {
      const data = await apiFetch<{ id: string }>('/api/v1/realphotos/assets', { method: 'POST', body })
      setAssetId(data.id)
      setNotice(`已建立资产 ${data.id}`)
    } catch (error: unknown) {
      setAssetId('')
      setNotice(error instanceof ApiError ? `后端拒绝：${error.message}` : '上传失败')
    }
  }

  function addToBatch() {
    if (!assetId) {
      setNotice('先上传一张，再加入批次')
      return
    }
    const previewUrl = file ? URL.createObjectURL(file) : ''
    setLibrary((prev) => {
      if (prev.length >= 10) return prev
      return [...prev, { id: assetId, previewUrl }]
    })
  }

  async function submitTask() {
    if (!assetId || !presetCode) {
      setNotice('需要资产和预设')
      return
    }
    const data = await apiFetch<{ id: string; status: string }>('/api/v1/realphotos/processing-tasks', {
      method: 'POST',
      body: JSON.stringify({
        assetId,
        presetCode,
        idempotencyKey: `ui-${assetId}-${Date.now()}`,
      }),
    })
    window.sessionStorage.setItem('realphotos.s1.taskId', data.id)
    setNotice(`单张已提交，任务 ${data.id}，状态 ${data.status}。到任务详情查看。`)
  }

  async function submitBatch() {
    if (!presetCode || library.length < 1 || library.length > 10) {
      setNotice('批次需要 1 到 10 张，以及一个预设')
      return
    }
    try {
      const data = await apiFetch<{ batchId: string; tasks: { id: string }[] }>(
        '/api/v1/realphotos/processing-batches',
        {
          method: 'POST',
          body: JSON.stringify({
            assetIds: library.map((item) => Number(item.id)),
            presetCode,
            idempotencyKey: `ui-batch-${library.map((item) => item.id).join('-')}-${Date.now()}`,
          }),
        },
      )
      window.sessionStorage.setItem('realphotos.s4.batchId', data.batchId)
      if (data.tasks[0]) window.sessionStorage.setItem('realphotos.s1.taskId', data.tasks[0].id)
      setNotice(`批次 ${data.batchId} 已提交，共 ${data.tasks.length} 张。到任务详情查看。`)
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '批次提交失败')
    }
  }

  async function removeAsset() {
    if (!assetId) return
    try {
      await apiFetch(`/api/v1/realphotos/assets/${assetId}`, { method: 'DELETE' })
      setLibrary((prev) => prev.filter((item) => item.id !== assetId))
      setAssetId('')
      setNotice('资产已软删')
    } catch (error: unknown) {
      setNotice(error instanceof ApiError ? error.message : '删除失败')
    }
  }

  const presetLabel = presets.find((item) => item.code === presetCode)?.model || presetCode

  return (
    <main className="space-y-6 p-6">
      <h1 className="text-xl font-medium">批量原图</h1>
      <p className="text-sm text-muted-foreground">{notice}</p>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">提交</h2>
        <form
          className="flex flex-wrap items-end gap-3 text-sm"
          onSubmit={(event) => {
            event.preventDefault()
            void apiFetch('/api/v1/realphotos/redo-settings', {
              method: 'PUT',
              body: JSON.stringify({
                enabled: redoEnabled,
                scoreThreshold: redoThreshold,
                extraRounds: redoRounds,
              }),
            })
              .then(() => setNotice('自动重做设置已保存，只影响之后提交的任务'))
              .catch((error: unknown) => setNotice(error instanceof ApiError ? error.message : '设置保存失败'))
          }}
        >
          <label>
            <input
              type="checkbox"
              checked={redoEnabled}
              onChange={(event) => setRedoEnabled(event.target.checked)}
            />{' '}
            自动重做
          </label>
          <label>
            阈值
            <input
              className="ml-1 w-16 border px-1"
              type="number"
              min={0}
              max={100}
              value={redoThreshold}
              onChange={(event) => setRedoThreshold(Number(event.target.value))}
            />
          </label>
          <label>
            追加次数
            <input
              className="ml-1 w-16 border px-1"
              type="number"
              min={1}
              max={5}
              value={redoRounds}
              onChange={(event) => setRedoRounds(Number(event.target.value))}
            />
          </label>
          <button className="border px-3 py-1" type="submit">
            保存设置
          </button>
          <span className="text-muted-foreground">只影响之后提交的任务</span>
        </form>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            本地图片
            <input
              className="mt-1 block text-sm"
              type="file"
              accept="image/jpeg,image/png,.jpg,.jpeg,.png"
              onChange={(event) => void onFile(event.target.files?.[0] || null)}
            />
          </label>
          <label className="text-sm">
            预设
            <select
              className="mt-1 block border px-2 py-1 text-sm"
              value={presetCode}
              onChange={(event) => setPresetCode(event.target.value)}
            >
              {presets.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.model}（{item.code}）
                </option>
              ))}
            </select>
          </label>
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void upload()}>
            上传
          </button>
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => addToBatch()}>
            加入批次
          </button>
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void submitTask()}>
            提交单张
          </button>
          <button className="border px-3 py-1 text-sm" type="button" onClick={() => void removeAsset()}>
            删除资产
          </button>
        </div>
      </section>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">待处理图片</h2>
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left">缩略图</th>
              <th className="text-left">资产</th>
              <th className="text-left">预设</th>
              <th className="text-left">张数</th>
              <th className="text-left">开始处理</th>
            </tr>
          </thead>
          <tbody>
            {library.length === 0 ? (
              <tr>
                <td colSpan={5}>还没有加入图片</td>
              </tr>
            ) : (
              library.map((item, index) => (
                <tr key={`${item.id}-${index}`}>
                  <td>
                    {item.previewUrl ? (
                      <img src={item.previewUrl} alt="" className="h-12 w-12 object-cover" />
                    ) : (
                      <span className="inline-block h-12 w-12 border" />
                    )}
                  </td>
                  <td>{item.id}</td>
                  <td>{presetLabel}</td>
                  <td>
                    {index === 0 ? `${library.length} / 10` : ''}
                  </td>
                  <td>
                    {index === 0 ? (
                      <button className="border px-3 py-1" type="button" onClick={() => void submitBatch()}>
                        开始处理
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </main>
  )
}
