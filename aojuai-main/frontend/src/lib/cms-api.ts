/**
 * CMS API client — thin typed wrappers over apiFetch.
 *
 * Public reads use { anonymous: true } (no token). Admin calls pass a session.
 */
import { apiFetch } from '@/lib/api'
import type { Session } from '@/lib/auth'

import type { Data as PuckData } from '@measured/puck'

export type CmsPageStatus = 'draft' | 'published'

export type PublicPage = {
  slug: string
  title: string
  blocks: PuckData
  seo: { title?: string; description?: string; keywords?: string }
}

export type PublicPost = {
  slug: string
  title: string
  excerpt?: string | null
  coverImage?: string | null
  body: string
  tags: string[]
  publishedAt?: string | null
}

export type NavItem = { label: string; href: string; external?: boolean; children?: NavItem[] }
export type SiteSettings = {
  brandName?: string
  logo?: string
  tagline?: string
  footerText?: string
  contactEmail?: string
  social?: { github?: string; x?: string; linkedin?: string }
  /** Raw HTML/JS injected at end of <head> (analytics, verification tags). */
  headHtml?: string
  /** Raw HTML/JS injected at end of <body> (chat widgets, floating helpers). */
  bodyHtml?: string
  /** Enabled public-site locales + default; drives the language switcher. */
  locales?: string[]
  defaultLocale?: string
}

export type PageListItem = {
  id: number
  slug: string
  title: string
  locale?: string
  status: CmsPageStatus
  sortOrder: number
  isSystem: boolean
  publishedAt?: string | null
  updatedAt?: string | null
}

export type PageDetail = PageListItem & {
  blocks: PuckData
  seo: Record<string, unknown>
}

export type PostListItem = {
  id: number
  slug: string
  title: string
  excerpt?: string | null
  coverImage?: string | null
  status: CmsPageStatus
  tags: string[]
  publishedAt?: string | null
  updatedAt?: string | null
}

export type PostDetail = PostListItem & { body: string; seo: Record<string, unknown> }

export type SubmissionItem = {
  id: number
  name: string
  email: string
  company?: string | null
  message: string
  sourcePage?: string | null
  status: string
  createdAt?: string | null
}

type PageResult<T> = { list: T[]; total: number; pageSize: number; currentPage: number }

// --------------------------------------------------------------------------- //
// Public (no auth)
// --------------------------------------------------------------------------- //
function localeQS(locale?: string) {
  return locale && locale !== 'default' ? `?locale=${encodeURIComponent(locale)}` : ''
}

export function getPublicPage(slug: string, locale?: string) {
  return apiFetch<PublicPage>(`/api/v1/site/cms/pages/${slug}${localeQS(locale)}`, { anonymous: true })
}

export function getPublicPosts(currentPage = 1, pageSize = 12, locale?: string) {
  const lq = locale && locale !== 'default' ? `&locale=${encodeURIComponent(locale)}` : ''
  return apiFetch<PageResult<PublicPost>>(
    `/api/v1/site/cms/posts?currentPage=${currentPage}&pageSize=${pageSize}${lq}`,
    { anonymous: true },
  )
}

export function getPublicPost(slug: string, locale?: string) {
  return apiFetch<PublicPost>(`/api/v1/site/cms/posts/${slug}${localeQS(locale)}`, { anonymous: true })
}

export function getPublicNavigation() {
  return apiFetch<{ header: NavItem[]; footer: NavItem[] }>(`/api/v1/site/cms/navigation`, {
    anonymous: true,
  })
}

export function getPublicSettings() {
  return apiFetch<{ settings: SiteSettings }>(`/api/v1/site/cms/settings`, { anonymous: true })
}

export function submitContact(body: {
  name: string
  email: string
  company?: string
  message: string
  sourcePage?: string
  website?: string
}) {
  return apiFetch<unknown>(`/api/v1/site/cms/contact`, {
    method: 'POST',
    anonymous: true,
    body: JSON.stringify(body),
  })
}

// --------------------------------------------------------------------------- //
// Admin (auth)
// --------------------------------------------------------------------------- //
export function listPages(session: Session | null, params: { currentPage?: number; keyword?: string } = {}) {
  const qs = new URLSearchParams()
  qs.set('currentPage', String(params.currentPage ?? 1))
  qs.set('pageSize', '100')
  if (params.keyword) qs.set('keyword', params.keyword)
  return apiFetch<PageResult<PageListItem>>(`/api/v1/cms/pages?${qs.toString()}`, { session })
}

export function getPage(session: Session | null, id: number) {
  return apiFetch<PageDetail>(`/api/v1/cms/pages/${id}`, { session })
}

export function aiGeneratePage(session: Session | null, prompt: string) {
  return apiFetch<{ blocks: PuckData; mode: 'ai' | 'template' }>(`/api/v1/cms/ai/generate-page`, {
    method: 'POST',
    session,
    body: JSON.stringify({ prompt }),
  })
}

export function aiTranslatePage(session: Session | null, pageId: number, targetLang: string) {
  return apiFetch<{ blocks: PuckData; title: string; slug: string; mode: 'ai' | 'copy' }>(
    `/api/v1/cms/ai/translate-page`,
    { method: 'POST', session, body: JSON.stringify({ pageId, targetLang }) },
  )
}

export function aiTranslatePost(session: Session | null, postId: number, targetLang: string) {
  return apiFetch<{ slug: string; title: string; excerpt?: string; body: string; tags: string[]; mode: 'ai' | 'copy' }>(
    `/api/v1/cms/ai/translate-post`,
    { method: 'POST', session, body: JSON.stringify({ postId, targetLang }) },
  )
}

// --- Language taxonomy ---
export type CmsLanguage = {
  id: number
  code: string
  name: string
  isDefault: boolean
  isActive: boolean
  sortOrder: number
}

export function listLanguages(session: Session | null) {
  return apiFetch<{ list: CmsLanguage[] }>(`/api/v1/cms/languages`, { session })
}
export function createLanguage(session: Session | null, body: Partial<CmsLanguage>) {
  return apiFetch<CmsLanguage>(`/api/v1/cms/languages`, { method: 'POST', session, body: JSON.stringify(body) })
}
export function updateLanguage(session: Session | null, id: number, body: Partial<CmsLanguage>) {
  return apiFetch<CmsLanguage>(`/api/v1/cms/languages/${id}`, { method: 'PUT', session, body: JSON.stringify(body) })
}
export function deleteLanguage(session: Session | null, id: number) {
  return apiFetch<unknown>(`/api/v1/cms/languages/${id}`, { method: 'DELETE', session })
}

export function createPage(session: Session | null, body: Record<string, unknown>) {
  return apiFetch<PageDetail>(`/api/v1/cms/pages`, { method: 'POST', session, body: JSON.stringify(body) })
}

export function updatePage(session: Session | null, id: number, body: Record<string, unknown>) {
  return apiFetch<PageDetail>(`/api/v1/cms/pages/${id}`, { method: 'PUT', session, body: JSON.stringify(body) })
}

export function publishPage(session: Session | null, id: number, publish: boolean) {
  return apiFetch<PageDetail>(`/api/v1/cms/pages/${id}/publish?publish=${publish}`, {
    method: 'POST',
    session,
  })
}

export function deletePage(session: Session | null, id: number) {
  return apiFetch<unknown>(`/api/v1/cms/pages/${id}`, { method: 'DELETE', session })
}

export function listPosts(session: Session | null) {
  return apiFetch<PageResult<PostListItem>>(`/api/v1/cms/posts?currentPage=1&pageSize=100`, { session })
}

export function getPost(session: Session | null, id: number) {
  return apiFetch<PostDetail>(`/api/v1/cms/posts/${id}`, { session })
}

export function createPost(session: Session | null, body: Record<string, unknown>) {
  return apiFetch<PostDetail>(`/api/v1/cms/posts`, { method: 'POST', session, body: JSON.stringify(body) })
}

export function updatePost(session: Session | null, id: number, body: Record<string, unknown>) {
  return apiFetch<PostDetail>(`/api/v1/cms/posts/${id}`, { method: 'PUT', session, body: JSON.stringify(body) })
}

export function publishPost(session: Session | null, id: number, publish: boolean) {
  return apiFetch<PostDetail>(`/api/v1/cms/posts/${id}/publish?publish=${publish}`, {
    method: 'POST',
    session,
  })
}

export function deletePost(session: Session | null, id: number) {
  return apiFetch<unknown>(`/api/v1/cms/posts/${id}`, { method: 'DELETE', session })
}

export function getAdminNavigation(session: Session | null) {
  return apiFetch<{ list: { location: string; items: NavItem[] }[] }>(`/api/v1/cms/navigation`, { session })
}

export function updateNavigation(session: Session | null, location: string, items: NavItem[]) {
  return apiFetch<unknown>(`/api/v1/cms/navigation/${location}`, {
    method: 'PUT',
    session,
    body: JSON.stringify({ items }),
  })
}

export function getAdminSettings(session: Session | null) {
  return apiFetch<{ settings: SiteSettings }>(`/api/v1/cms/settings`, { session })
}

export type CmsAiConfig = {
  mode: 'inherit' | 'custom'
  baseUrl?: string | null
  model?: string | null
  temperature?: number | null
  maxTokens?: number | null
  hasApiKey?: boolean
  systemConfigured?: boolean
}

export function getCmsAiConfig(session: Session | null) {
  return apiFetch<CmsAiConfig>(`/api/v1/cms/ai-config`, { session })
}

export function updateCmsAiConfig(
  session: Session | null,
  body: Partial<CmsAiConfig> & { apiKey?: string; clearApiKey?: boolean },
) {
  return apiFetch<CmsAiConfig>(`/api/v1/cms/ai-config`, {
    method: 'PUT',
    session,
    body: JSON.stringify(body),
  })
}

export function updateSettings(session: Session | null, settings: SiteSettings) {
  return apiFetch<unknown>(`/api/v1/cms/settings`, {
    method: 'PUT',
    session,
    body: JSON.stringify({ settings }),
  })
}

export function listSubmissions(session: Session | null, status?: string) {
  const qs = new URLSearchParams({ currentPage: '1', pageSize: '100' })
  if (status) qs.set('status', status)
  return apiFetch<PageResult<SubmissionItem>>(`/api/v1/cms/submissions?${qs.toString()}`, { session })
}

export function updateSubmission(session: Session | null, id: number, status: string) {
  return apiFetch<unknown>(`/api/v1/cms/submissions/${id}`, {
    method: 'PUT',
    session,
    body: JSON.stringify({ status }),
  })
}
