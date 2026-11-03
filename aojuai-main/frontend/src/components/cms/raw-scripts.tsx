'use client'

import { useEffect } from 'react'

/**
 * Injects admin-configured raw HTML/JS into the document so third-party
 * snippets (analytics, chat widgets) actually execute.
 *
 * React's dangerouslySetInnerHTML does NOT run <script> tags, so we parse the
 * markup and recreate each script node. Each block is injected once and tagged
 * with data-cms-injected to avoid duplicates on client navigation.
 */
function inject(target: HTMLElement, html: string, marker: string) {
  if (!html || typeof document === 'undefined') return
  if (document.querySelector(`[data-cms-injected="${marker}"]`)) return

  const tpl = document.createElement('div')
  tpl.innerHTML = html

  Array.from(tpl.childNodes).forEach((node) => {
    if (node.nodeName === 'SCRIPT') {
      const old = node as HTMLScriptElement
      const script = document.createElement('script')
      Array.from(old.attributes).forEach((attr) => script.setAttribute(attr.name, attr.value))
      script.text = old.text
      script.setAttribute('data-cms-injected', marker)
      target.appendChild(script)
    } else {
      const clone = node.cloneNode(true)
      if (clone instanceof HTMLElement) clone.setAttribute('data-cms-injected', marker)
      target.appendChild(clone)
    }
  })
}

export function RawScripts({ head, body }: { head?: string; body?: string }) {
  useEffect(() => {
    if (head) inject(document.head, head, 'head')
    if (body) inject(document.body, body, 'body')
  }, [head, body])
  return null
}

export default RawScripts
