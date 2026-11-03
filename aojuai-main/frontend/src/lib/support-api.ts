import { apiFetch } from '@/lib/api'
import type { Session } from '@/lib/auth'

export type SupportUserBrief = {
  id: number
  username: string | null
  nickname: string | null
  email: string | null
}

export type SupportTicketMessage = {
  id: number
  ticketId: number
  authorUserId: number | null
  author: SupportUserBrief | null
  authorRole: string
  messageType: string
  body: string
  isInternal: boolean
  attachments: Record<string, unknown>[]
  createdAt: string | null
}

export type SupportTicket = {
  id: number
  ticketNo: string | null
  requesterUserId: number
  requester: SupportUserBrief | null
  assigneeUserId: number | null
  assignee: SupportUserBrief | null
  category: string
  status: string
  priority: string
  subject: string
  relatedType: string | null
  relatedId: string | null
  lastMessageAt: string | null
  lastRepliedAt: string | null
  slaHours: number
  slaDueAt: string | null
  slaOverdue: boolean
  waitingHours: number | null
  resolvedAt: string | null
  closedAt: string | null
  createdAt: string | null
  updatedAt: string | null
  extra: Record<string, unknown>
}

export type SupportTicketDetail = SupportTicket & {
  description: string
  messages: SupportTicketMessage[]
}

export type SupportTicketPage = {
  list: SupportTicket[]
  total: number
  pageSize: number
  currentPage: number
}

export type SupportOptions = {
  categories: string[]
  statuses: string[]
  priorities: string[]
}

export type SupportSummary = {
  total: number
  open: number
  pending: number
  resolved: number
  closed: number
}

export type SupportTicketInput = {
  subject: string
  description: string
  category?: string
  priority?: string
  relatedType?: string | null
  relatedId?: string | null
}

export type SupportTicketPatch = {
  status?: string
  priority?: string
  category?: string
  assigneeUserId?: number
  clearAssignee?: boolean
  internalNote?: string
}

export type SupportTicketFilters = {
  page?: number
  pageSize?: number
  status?: string
  category?: string
  priority?: string
  keyword?: string
  relatedType?: string
  excludeRelatedType?: string
  unassigned?: boolean
}

type RequestContext = {
  session: Session
  tenantId?: number | null
}

function buildQuery(filters: SupportTicketFilters = {}): string {
  const params = new URLSearchParams()
  params.set('page', String(filters.page ?? 1))
  params.set('pageSize', String(filters.pageSize ?? 20))
  if (filters.status) params.set('status', filters.status)
  if (filters.category) params.set('category', filters.category)
  if (filters.priority) params.set('priority', filters.priority)
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.relatedType) params.set('relatedType', filters.relatedType)
  if (filters.excludeRelatedType) params.set('excludeRelatedType', filters.excludeRelatedType)
  if (filters.unassigned) params.set('unassigned', 'true')
  return params.toString()
}

export const supportApi = {
  options({ session, tenantId }: RequestContext) {
    return apiFetch<SupportOptions>('/api/v1/support/options', { session, tenantId })
  },

  listMine(filters: SupportTicketFilters, { session, tenantId }: RequestContext) {
    return apiFetch<SupportTicketPage>(`/api/v1/support/tickets?${buildQuery(filters)}`, {
      session,
      tenantId,
    })
  },

  getMine(id: number, { session, tenantId }: RequestContext) {
    return apiFetch<SupportTicketDetail>(`/api/v1/support/tickets/${id}`, { session, tenantId })
  },

  create(input: SupportTicketInput, { session, tenantId }: RequestContext) {
    return apiFetch<SupportTicketDetail>('/api/v1/support/tickets', {
      method: 'POST',
      session,
      tenantId,
      body: JSON.stringify(input),
    })
  },

  reply(id: number, body: string, { session, tenantId }: RequestContext) {
    return apiFetch<SupportTicketDetail>(`/api/v1/support/tickets/${id}/messages`, {
      method: 'POST',
      session,
      tenantId,
      body: JSON.stringify({ body }),
    })
  },

  adminSummary({ session, tenantId }: RequestContext) {
    return apiFetch<SupportSummary>('/api/v1/support/admin/summary', { session, tenantId })
  },

  adminList(filters: SupportTicketFilters, { session, tenantId }: RequestContext) {
    return apiFetch<SupportTicketPage>(`/api/v1/support/admin/tickets?${buildQuery(filters)}`, {
      session,
      tenantId,
    })
  },

  adminGet(id: number, { session, tenantId }: RequestContext) {
    return apiFetch<SupportTicketDetail>(`/api/v1/support/admin/tickets/${id}`, {
      session,
      tenantId,
    })
  },

  adminUpdate(id: number, patch: SupportTicketPatch, { session, tenantId }: RequestContext) {
    return apiFetch<SupportTicketDetail>(`/api/v1/support/admin/tickets/${id}`, {
      method: 'PATCH',
      session,
      tenantId,
      body: JSON.stringify(patch),
    })
  },

  adminReply(
    id: number,
    input: { body: string; isInternal?: boolean; status?: string },
    { session, tenantId }: RequestContext,
  ) {
    return apiFetch<SupportTicketDetail>(`/api/v1/support/admin/tickets/${id}/messages`, {
      method: 'POST',
      session,
      tenantId,
      body: JSON.stringify(input),
    })
  },
}
