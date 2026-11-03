import { apiFetch } from '@/lib/api'
import type { Session } from '@/lib/auth'

export type SampleItem = {
  id: number
  tenantId?: number
  code: string
  name: string
  description: string | null
  createdAt: string
  updatedAt: string | null
}

export type SampleItemInput = {
  code: string
  name: string
  description?: string | null
}

export type SampleItemPage = {
  list: SampleItem[]
  total: number
  pageSize: number
  currentPage: number
}

type RequestContext = {
  session: Session
  tenantId?: number | null
}

export const sampleItemsApi = {
  list({ session, tenantId }: RequestContext) {
    return apiFetch<SampleItemPage>('/api/v1/sample-items?page=1&pageSize=100', {
      session,
      tenantId,
    })
  },

  create(input: SampleItemInput, { session, tenantId }: RequestContext) {
    return apiFetch<SampleItem>('/api/v1/sample-items', {
      method: 'POST',
      session,
      tenantId,
      body: JSON.stringify(input),
    })
  },

  update(id: number, input: Partial<SampleItemInput>, { session, tenantId }: RequestContext) {
    return apiFetch<SampleItem>(`/api/v1/sample-items/${id}`, {
      method: 'PATCH',
      session,
      tenantId,
      body: JSON.stringify(input),
    })
  },

  remove(id: number, { session, tenantId }: RequestContext) {
    return apiFetch<null>(`/api/v1/sample-items/${id}`, {
      method: 'DELETE',
      session,
      tenantId,
    })
  },
}
