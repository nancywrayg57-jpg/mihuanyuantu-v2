'use client'

export type SiteSeoConfig = {
  title?: string | null
  keywords?: string | null
  description?: string | null
}

function upsertMetaTag(name: string, content: string) {
  const trimmed = (content || '').trim()
  let el = document.querySelector(`meta[name="${name}"]`) as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('name', name)
    document.head.appendChild(el)
  }
  el.setAttribute('content', trimmed)
}

export function applySiteSeo(seo?: SiteSeoConfig | null) {
  if (!seo) return

  const title = String(seo.title ?? '').trim()
  if (title) {
    document.title = title
  }

  if (seo.keywords !== undefined && seo.keywords !== null) {
    upsertMetaTag('keywords', String(seo.keywords))
  }
  if (seo.description !== undefined && seo.description !== null) {
    upsertMetaTag('description', String(seo.description))
  }
}

