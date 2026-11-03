'use client'

import { CheckCircle2 } from 'lucide-react'
import { useState } from 'react'

import { submitContact } from '@/lib/cms-api'

export function ContactForm({ sourcePath }: { sourcePath: string }) {
  const [form, setForm] = useState({ name: '', email: '', company: '', message: '', website: '' })
  const [status, setStatus] = useState<'idle' | 'sending' | 'done' | 'error'>('idle')
  const [error, setError] = useState('')

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus('sending')
    setError('')
    try {
      await submitContact({ ...form, sourcePage: sourcePath })
      setStatus('done')
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : '提交失败，请稍后再试')
    }
  }

  const inputCls =
    'w-full rounded-lg border border-border/70 bg-background px-3.5 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20'

  if (status === 'done') {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <CheckCircle2 className="h-12 w-12 text-primary" />
        <h2 className="mt-4 text-lg font-semibold">提交成功！</h2>
        <p className="mt-2 text-sm text-muted-foreground">感谢你的留言，我们会尽快与你联系。</p>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-sm font-medium">姓名 *</label>
          <input required className={inputCls} value={form.name} onChange={(e) => set('name', e.target.value)} />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium">邮箱 *</label>
          <input required type="email" className={inputCls} value={form.email} onChange={(e) => set('email', e.target.value)} />
        </div>
      </div>
      <div>
        <label className="mb-1.5 block text-sm font-medium">公司</label>
        <input className={inputCls} value={form.company} onChange={(e) => set('company', e.target.value)} />
      </div>
      <div>
        <label className="mb-1.5 block text-sm font-medium">需求描述 *</label>
        <textarea required rows={4} className={inputCls} value={form.message} onChange={(e) => set('message', e.target.value)} />
      </div>
      <input type="text" tabIndex={-1} autoComplete="off" className="hidden" value={form.website} onChange={(e) => set('website', e.target.value)} />
      {status === 'error' ? <p className="text-sm text-destructive">{error}</p> : null}
      <button
        type="submit"
        disabled={status === 'sending'}
        className="inline-flex w-full items-center justify-center rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/25 transition hover:opacity-90 disabled:opacity-60"
      >
        {status === 'sending' ? '提交中…' : '提交'}
      </button>
    </form>
  )
}

export default ContactForm
