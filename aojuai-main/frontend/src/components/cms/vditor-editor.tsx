'use client'

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from 'react'

import { cn } from '@/lib/utils'

// Reused from the nextjs-plugins branch's documents editor. Vditor assets are
// self-hosted under /public/vendor/vditor (cdn + stylesheet), so no external CDN.

export type VditorEditorMode = 'sv' | 'ir' | 'wysiwyg'
export type VditorEditorHandle = {
  getValue: () => string
  setValue: (value: string) => void
  focus: () => void
}
type VditorInstance = {
  destroy?: () => void
  getValue?: () => string
  setValue?: (value: string) => void
  disabled?: () => void
  enable?: () => void
  focus?: () => void
}

const VDITOR_STYLESHEET_ID = 'aoju-vditor-stylesheet'
const VDITOR_STYLESHEET_HREF = '/vendor/vditor/dist/index.css'
const VDITOR_CDN_BASE = '/vendor/vditor'
const VDITOR_LANG = 'zh_CN'
let vditorStylesheetPromise: Promise<void> | null = null

function ensureVditorStylesheet() {
  if (typeof document === 'undefined') return Promise.resolve()
  if (vditorStylesheetPromise) return vditorStylesheetPromise
  vditorStylesheetPromise = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(VDITOR_STYLESHEET_ID) as HTMLLinkElement | null
    if (existing) {
      if (existing.dataset.loaded === 'true') return resolve()
      existing.addEventListener('load', () => resolve(), { once: true })
      existing.addEventListener('error', () => {
        vditorStylesheetPromise = null
        reject(new Error('vditor css failed'))
      }, { once: true })
      return
    }
    const link = document.createElement('link')
    link.id = VDITOR_STYLESHEET_ID
    link.rel = 'stylesheet'
    link.href = VDITOR_STYLESHEET_HREF
    link.addEventListener('load', () => {
      link.dataset.loaded = 'true'
      resolve()
    }, { once: true })
    link.addEventListener('error', () => {
      vditorStylesheetPromise = null
      reject(new Error('vditor css failed'))
    }, { once: true })
    document.head.appendChild(link)
  })
  return vditorStylesheetPromise
}

export const VditorEditor = forwardRef<
  VditorEditorHandle,
  {
    value: string
    onChange: (value: string) => void
    height?: number | string
    placeholder?: string
    disabled?: boolean
    mode?: VditorEditorMode
    className?: string
  }
>(function VditorEditor(
  { value, onChange, height = 420, placeholder = '在此撰写正文，支持 Markdown 与所见即所得编辑…', disabled = false, mode = 'ir', className },
  ref,
) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const instanceRef = useRef<VditorInstance | null>(null)
  const readyRef = useRef(false)
  const syncingFromEditorRef = useRef(false)
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const disabledRef = useRef(disabled)

  useEffect(() => {
    valueRef.current = value
  }, [value])
  useEffect(() => {
    onChangeRef.current = onChange
  }, [onChange])
  useEffect(() => {
    disabledRef.current = disabled
  }, [disabled])

  useEffect(() => {
    let active = true
    async function init() {
      if (!rootRef.current) return
      readyRef.current = false
      try {
        instanceRef.current?.destroy?.()
      } catch {
        /* ignore */
      } finally {
        instanceRef.current = null
      }
      await ensureVditorStylesheet()
      const mod = await import('vditor')
      if (!active || !rootRef.current) return
      const Vditor = mod.default as unknown as new (el: HTMLElement, opts: Record<string, unknown>) => VditorInstance
      instanceRef.current = new Vditor(rootRef.current, {
        height,
        mode,
        lang: VDITOR_LANG,
        cdn: VDITOR_CDN_BASE,
        cache: { enable: false },
        placeholder,
        counter: { enable: false },
        outline: { enable: false },
        resize: { enable: false },
        preview: { mode: 'editor' },
        toolbarConfig: { pin: true },
        input: (next: string) => {
          syncingFromEditorRef.current = true
          onChangeRef.current(next ?? '')
          syncingFromEditorRef.current = false
        },
        after: () => {
          readyRef.current = true
          instanceRef.current?.setValue?.(valueRef.current || '')
          if (disabledRef.current) instanceRef.current?.disabled?.()
        },
      })
    }
    void init()
    return () => {
      active = false
      readyRef.current = false
      try {
        instanceRef.current?.destroy?.()
      } catch {
        /* ignore */
      } finally {
        instanceRef.current = null
      }
    }
  }, [height, mode, placeholder])

  useEffect(() => {
    if (!instanceRef.current || !readyRef.current || syncingFromEditorRef.current) return
    let current = ''
    try {
      current = instanceRef.current.getValue?.() ?? ''
    } catch {
      return
    }
    if (current !== (value ?? '')) instanceRef.current.setValue?.(value ?? '')
  }, [value])

  const focus = useCallback(() => instanceRef.current?.focus?.(), [])
  useImperativeHandle(
    ref,
    () => ({
      getValue: () => instanceRef.current?.getValue?.() ?? valueRef.current ?? '',
      setValue: (v: string) => instanceRef.current?.setValue?.(v ?? ''),
      focus,
    }),
    [focus],
  )

  return (
    <div className={cn('aoju-vditor w-full max-w-none', className)}>
      <div ref={rootRef} />
    </div>
  )
})

export default VditorEditor
