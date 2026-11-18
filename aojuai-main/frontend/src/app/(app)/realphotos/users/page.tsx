'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

import { ListSearch, matchSearchText } from '@/components/realphotos/list-search'
import { RpPageHeader } from '@/components/realphotos/rp-page-header'
import { RpEmptyState, RpSkeletonRows, RpTableScroll, RpDialog } from '@/components/realphotos/rp-table'
import { ApiError, apiFetch } from '@/lib/api'
import { formatDateTimeShort } from '@/lib/realphotos-time'

type TenantRow = {
  tenantId: number
  tenantName: string
  tenantCode: string
  accountCount: number
  isActive?: boolean
  createdAt?: string | null
  lastActiveAt?: string | null
  ownerUsername?: string | null
}

type TenantDetail = {
  tenant: {
    tenantId: number
    tenantName: string
    tenantCode: string
    isActive: boolean
    createdAt?: string | null
  }
  accounts: Account[]
  stats: { assetCount: number; taskTotal: number; taskDelivered: number; taskFailed: number }
  wallet: { availableInteger?: string; reservedInteger?: string }
}

type Account = {
  id: number
  username: string
  status: number
  tenantId: number
  roleCodes?: string[]
}

type OpType = 'credits' | 'password' | 'roles' | 'enable' | 'disable' | 'delete'

const OP_OPTIONS: { value: OpType; label: string }[] = [
  { value: 'credits', label: '加减分' },
  { value: 'password', label: '重置密码' },
  { value: 'roles', label: '改角色' },
  { value: 'enable', label: '启用' },
  { value: 'disable', label: '停用' },
  { value: 'delete', label: '删除' },
]

const ROLE_OPTIONS = ['rp_merchant', 'rp_order_support', 'rp_tech_support'] as const

function statusLabel(status: number): string {
  return status === 1 ? '启用' : '停用'
}

function tenantLabel(row: TenantRow): string {
  if (row.tenantName && row.tenantCode) return `${row.tenantName}（${row.tenantCode}）`
  return row.tenantName || row.tenantCode || `租户 #${row.tenantId}`
}

export default function RealphotosUsersPage() {
  const [tenants, setTenants] = useState<TenantRow[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [message, setMessage] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  const [accountsOpen, setAccountsOpen] = useState<TenantRow | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [accountsLoading, setAccountsLoading] = useState(false)
  const [detailOpen, setDetailOpen] = useState<TenantRow | null>(null)
  const [detailData, setDetailData] = useState<TenantDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [moreTenantId, setMoreTenantId] = useState<number | null>(null)

  const [createOpen, setCreateOpen] = useState<TenantRow | null>(null)
  const [deleteOpen, setDeleteOpen] = useState<TenantRow | null>(null)
  const [tenantConfirm, setTenantConfirm] = useState('')
  const [deleteBusy, setDeleteBusy] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<string>('rp_merchant')

  const [opOpen, setOpOpen] = useState<TenantRow | null>(null)
  const [opAccounts, setOpAccounts] = useState<Account[]>([])
  const [opLoading, setOpLoading] = useState(false)
  const [opType, setOpType] = useState<OpType>('credits')
  const [opUserId, setOpUserId] = useState('')
  const [creditDelta, setCreditDelta] = useState('10')
  const [creditReason, setCreditReason] = useState('')
  const [roleCodes, setRoleCodes] = useState('rp_merchant')
  const [pwd1, setPwd1] = useState('')
  const [pwd2, setPwd2] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState('')

  const loadTenants = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch<{
        items?: TenantRow[]
        pageSize?: number
        total?: number
        page?: number
      }>(`/api/v1/realphotos/managed-tenants?page=${page}`)
      const rows = Array.isArray(data?.items) ? data.items : []
      setTenants(rows)
      setPageSize(Number(data?.pageSize) || 20)
      setTotal(Number(data?.total) || rows.length)
      setMessage('')
    } catch (error: unknown) {
      // 回退：旧环境若无 managed-tenants，用账号列表按租户聚合，避免整页空白。
      try {
        const users = await apiFetch<{ items?: Account[] }>(
          `/api/v1/realphotos/managed-users?page=1`,
        )
        const accounts = Array.isArray(users?.items) ? users.items : []
        const byTenant = new Map<number, TenantRow>()
        for (const account of accounts) {
          const tid = Number(account.tenantId)
          if (!Number.isFinite(tid) || tid <= 0) continue
          const existing = byTenant.get(tid)
          if (existing) {
            existing.accountCount += 1
          } else {
            byTenant.set(tid, {
              tenantId: tid,
              tenantName: `租户#${tid}`,
              tenantCode: '',
              accountCount: 1,
            })
          }
        }
        const rows = Array.from(byTenant.values()).sort((a, b) => a.tenantId - b.tenantId)
        setTenants(rows)
        setTotal(rows.length)
        setPageSize(Math.max(rows.length, 1))
        setMessage(
          error instanceof ApiError
            ? `${error.message}；已回退为账号聚合租户视图`
            : '租户接口不可用；已回退为账号聚合租户视图',
        )
      } catch (fallbackError: unknown) {
        setTenants([])
        setTotal(0)
        setMessage(
          fallbackError instanceof ApiError
            ? fallbackError.message
            : error instanceof ApiError
              ? error.message
              : '租户读取失败',
        )
      }
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => {
    void loadTenants()
  }, [loadTenants])

  async function loadAccountsForTenant(tenantId: number): Promise<Account[]> {
    const data = await apiFetch<{ items: Account[] }>(
      `/api/v1/realphotos/managed-users?tenantId=${tenantId}`,
    )
    return data.items || []
  }

  async function openAccounts(row: TenantRow) {
    setAccountsOpen(row)
    setAccounts([])
    setAccountsLoading(true)
    try {
      setAccounts(await loadAccountsForTenant(row.tenantId))
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '账号读取失败')
    } finally {
      setAccountsLoading(false)
    }
  }

  async function openTenantDetail(row: TenantRow) {
    setDetailOpen(row)
    setDetailData(null)
    setDetailLoading(true)
    try {
      const data = await apiFetch<TenantDetail>(`/api/v1/realphotos/managed-tenants/${row.tenantId}`)
      setDetailData(data)
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '租户详情读取失败')
    } finally {
      setDetailLoading(false)
    }
  }

  async function deleteTenantRow() {
    if (!deleteOpen) return
    setDeleteBusy(true)
    try {
      await apiFetch('/api/v1/realphotos/managed-tenants/delete', {
        method: 'POST',
        body: JSON.stringify({ tenantId: deleteOpen.tenantId, confirmCode: tenantConfirm.trim() }),
      })
      setMessage(`已删除租户「${deleteOpen.tenantName || deleteOpen.tenantCode}」`)
      setDeleteOpen(null)
      setTenantConfirm('')
      await loadTenants()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '删除租户失败')
    } finally {
      setDeleteBusy(false)
    }
  }

  async function openCreate(row: TenantRow) {    setCreateOpen(row)
    setNewUsername('')
    setNewPassword('')
    setNewRole('rp_merchant')
  }

  async function openOp(row: TenantRow) {
    setOpOpen(row)
    setOpAccounts([])
    setOpUserId('')
    setOpType('credits')
    setCreditDelta('10')
    setCreditReason('')
    setRoleCodes('rp_merchant')
    setPwd1('')
    setPwd2('')
    setDeleteConfirm('')
    setOpLoading(true)
    try {
      setOpAccounts(await loadAccountsForTenant(row.tenantId))
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '账号读取失败')
    } finally {
      setOpLoading(false)
    }
  }

  async function createUser() {
    if (!createOpen) return
    try {
      const created = await apiFetch<{ id: number; username: string }>('/api/v1/realphotos/managed-users', {
        method: 'POST',
        body: JSON.stringify({
          tenantId: createOpen.tenantId,
          username: newUsername,
          password: newPassword,
          roleCode: newRole,
        }),
      })
      setMessage(`已创建 ${created.username} (#${created.id}) · ${tenantLabel(createOpen)}`)
      setCreateOpen(null)
      await loadTenants()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '创建失败')
    }
  }

  async function submitOp() {
    if (!opOpen) return
    const userId = Number(opUserId)
    if (!Number.isFinite(userId) || userId <= 0) {
      setMessage('请选择目标账号')
      return
    }
    const selected = opAccounts.find((item) => item.id === userId)
    try {
      if (opType === 'credits') {
        const raw = creditDelta.trim()
        if (!/^-?\d+$/.test(raw)) {
          setMessage('积分必须是整数，拒绝小数')
          return
        }
        const data = await apiFetch<{ availableInteger: number }>('/api/v1/realphotos/managed-users/credits', {
          method: 'POST',
          body: JSON.stringify({
            tenantId: opOpen.tenantId,
            userId,
            delta: Number(raw),
            reason: creditReason,
            eventKey: `ui-credit-${userId}-${Date.now()}`,
          }),
        })
        setMessage(`加减分成功；可用=${data.availableInteger}`)
      } else if (opType === 'roles') {
        await apiFetch(`/api/v1/realphotos/managed-users/${userId}/roles`, {
          method: 'POST',
          body: JSON.stringify({
            tenantId: opOpen.tenantId,
            roleCodes: roleCodes.split(',').map((item) => item.trim()).filter(Boolean),
          }),
        })
        setMessage('角色已保存')
      } else if (opType === 'password') {
        await apiFetch(`/api/v1/realphotos/managed-users/${userId}/password`, {
          method: 'POST',
          body: JSON.stringify({ password: pwd1, confirm: pwd2 }),
        })
        setMessage('密码已重置（明文不回显、不进日志）')
      } else if (opType === 'enable' || opType === 'disable') {
        await apiFetch(`/api/v1/realphotos/managed-users/${userId}/status`, {
          method: 'POST',
          body: JSON.stringify({ enabled: opType === 'enable' }),
        })
        setMessage(opType === 'enable' ? '已启用' : '已停用')
      } else if (opType === 'delete') {
        await apiFetch(`/api/v1/realphotos/managed-users/${userId}/delete`, {
          method: 'POST',
          body: JSON.stringify({ confirmUsername: deleteConfirm }),
        })
        setMessage(`账号已删除${selected ? `：${selected.username}` : ''}`)
      }
      setOpOpen(null)
      await loadTenants()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '操作失败')
    }
  }

  const visibleTenants = useMemo(
    () =>
      tenants.filter((item) =>
        matchSearchText(
          search,
          item.tenantId,
          item.tenantName,
          item.tenantCode,
          item.accountCount,
        ),
      ),
    [tenants, search],
  )

  const selectedOpAccount = opAccounts.find((item) => String(item.id) === opUserId) || null
  const pageCount = Math.max(1, Math.ceil(total / Math.max(pageSize, 1)))

  return (
    <main className="space-y-4 p-6">
      <RpPageHeader title="用户管理" />
      <p className="text-sm">{message || (loading ? '加载中…' : '')}</p>
      <div className="rp-filter">
        <ListSearch value={search} placeholder="租户名 / 编码 / 编号" onChange={setSearch} />
      </div>

      <section className="rp-card p-4 shadow-sm space-y-3">
        <RpTableScroll>
        <table className="rp-table">
          <thead>
            <tr>
              <th className="text-left">租户编号</th>
              <th className="text-left">租户</th>
              <th className="text-left">状态</th>
              <th className="text-left">账号数</th>
              <th className="text-left">创建时间</th>
              <th className="text-left">最近活跃</th>
              <th className="text-left">操作</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <RpSkeletonRows colSpan={7} />
            ) : visibleTenants.length === 0 ? (
              <RpEmptyState
                colSpan={7}
                title={message || '暂无租户'}
                description="平台租户会在商家注册后自动出现；也可以由管理员创建账号。"
              />
            ) : (
              visibleTenants.map((item) => (
                <tr key={item.tenantId}>
                  <td>{item.tenantId}</td>
                  <td>
                    <button
                      className="text-left font-medium text-primary hover:underline"
                      type="button"
                      onClick={() => void openTenantDetail(item)}
                    >
                      {item.tenantName || '—'}
                    </button>
                    <div className="text-xs text-muted-foreground">
                      {item.tenantCode || '—'}
                      {item.ownerUsername ? ` · 负责人 ${item.ownerUsername}` : ''}
                    </div>
                  </td>
                  <td>{item.isActive === false ? '停用' : '正常'}</td>
                  <td>{item.accountCount}</td>
                  <td className="whitespace-nowrap">{formatDateTimeShort(item.createdAt) || '—'}</td>
                  <td className="whitespace-nowrap">
                    {item.lastActiveAt ? formatDateTimeShort(item.lastActiveAt) : '从未登录'}
                  </td>
                  <td className="space-x-1 whitespace-nowrap">
                    <button
                      className="rp-btn rp-btn-sm"
                      type="button"
                      onClick={() => void openTenantDetail(item)}
                    >
                      详情
                    </button>
                    <button
                      className="rp-btn rp-btn-sm"
                      type="button"
                      onClick={() => void openCreate(item)}
                    >
                      创建账号
                    </button>
                    <button
                      className="rp-btn rp-btn-sm"
                      type="button"
                      onClick={() => void openOp(item)}
                    >
                      操作
                    </button>
                    <button
                      className="rp-btn rp-btn-sm"
                      type="button"
                      onClick={() => setMoreTenantId((prev) => (prev === item.tenantId ? null : item.tenantId))}
                    >
                      更多
                    </button>
                    {moreTenantId === item.tenantId ? (
                      <button
                        className="rp-btn rp-btn-sm rp-btn-danger"
                        type="button"
                        onClick={() => {
                          setDeleteOpen(item)
                          setTenantConfirm('')
                          setMessage('')
                          setMoreTenantId(null)
                        }}
                      >
                        删除租户
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </RpTableScroll>
        <div className="flex items-center gap-2 text-sm">
          <button
            className="rp-btn rp-btn-sm"
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </button>
          <span>
            第 {page} / {pageCount} 页 · 共 {total} 条
          </span>
          <button
            className="rp-btn rp-btn-sm"
            type="button"
            disabled={page >= pageCount || loading}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </button>
        </div>
      </section>

      {detailOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setDetailOpen(null)}
          role="dialog"
          aria-modal="true"
          aria-label="租户详情"
        >
          <div
            className="rp-dialog flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden border bg-card text-sm"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
              <h2 className="text-sm font-medium">租户详情 · {tenantLabel(detailOpen)}</h2>
              <div className="flex gap-2">
                <button
                  className="rp-btn rp-btn-sm"
                  type="button"
                  onClick={() => void openAccounts(detailOpen)}
                >
                  查看账号
                </button>
                <button className="rp-btn rp-btn-sm" type="button" onClick={() => setDetailOpen(null)}>
                  关闭
                </button>
              </div>
            </div>
            <div className="overflow-y-auto p-4">
              {detailLoading ? <p className="text-muted-foreground">加载中…</p> : null}
              {detailData ? (
                <div className="space-y-4">
                  <dl className="rp-kv">
                    <dt>状态</dt>
                    <dd>{detailData.tenant.isActive ? '正常' : '停用'}</dd>
                    <dt>创建时间</dt>
                    <dd>{formatDateTimeShort(detailData.tenant.createdAt) || '—'}</dd>
                    <dt>可用积分</dt>
                    <dd>{detailData.wallet.availableInteger ?? '—'}</dd>
                    <dt>冻结积分</dt>
                    <dd>{detailData.wallet.reservedInteger ?? '—'}</dd>
                    <dt>资源</dt>
                    <dd>{detailData.stats.assetCount}</dd>
                    <dt>任务</dt>
                    <dd>
                      共 {detailData.stats.taskTotal} · 已交付 {detailData.stats.taskDelivered} · 失败{' '}
                      {detailData.stats.taskFailed}
                    </dd>
                    <dt>账号</dt>
                    <dd>{detailData.accounts.length}</dd>
                  </dl>
                  <table className="rp-table">
                    <thead>
                      <tr>
                        <th className="text-left">登录名</th>
                        <th className="text-left">状态</th>
                        <th className="text-left">角色</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailData.accounts.length === 0 ? (
                        <tr>
                          <td className="rp-empty" colSpan={3}>
                            该租户暂无账号
                          </td>
                        </tr>
                      ) : (
                        detailData.accounts.map((account) => (
                          <tr key={account.id}>
                            <td>{account.username}</td>
                            <td>{statusLabel(account.status)}</td>
                            <td>{(account.roleCodes || []).join(', ') || '—'}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {accountsOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setAccountsOpen(null)}
          role="dialog"
          aria-modal="true"
          aria-label="查看账号"
        >
          <div
            className="rp-dialog flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden border bg-card text-sm"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 border-b px-4 py-3">
              <h2 className="text-sm font-medium">账号列表 · {tenantLabel(accountsOpen)}</h2>
              <button
                className="rp-btn rp-btn-sm"
                type="button"
                onClick={() => setAccountsOpen(null)}
              >
                关闭
              </button>
            </div>
            <div className="overflow-y-auto p-4">
              {accountsLoading ? (
                <p className="text-muted-foreground">加载中…</p>
              ) : (
                <table className="rp-table">
                  <thead>
                    <tr>
                      <th className="text-left">编号</th>
                      <th className="text-left">登录名</th>
                      <th className="text-left">状态</th>
                      <th className="text-left">角色</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.length === 0 ? (
                      <tr>
                        <td className="rp-empty text-muted-foreground" colSpan={4}>
                          该租户暂无账号
                        </td>
                      </tr>
                    ) : (
                      accounts.map((item) => (
                        <tr key={item.id}>
                          <td>{item.id}</td>
                          <td>{item.username}</td>
                          <td>{statusLabel(item.status)}</td>
                          <td>{(item.roleCodes || []).join(', ') || '—'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {createOpen ? (
        <RpDialog
          title={`创建账号 · ${tenantLabel(createOpen)}`}
          label="创建账号"
          closeOnBackdrop={false}
          onClose={() => setCreateOpen(null)}
        >
          <p className="text-xs text-muted-foreground">租户编号 {createOpen.tenantId}（已锁定，不可改）</p>
          <input
            className="rp-input w-full"
            placeholder="登录名"
            value={newUsername}
            onChange={(e) => setNewUsername(e.target.value)}
          />
          <input
            className="rp-input w-full"
            type="password"
            placeholder="初始密码"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <select className="rp-input w-full" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
            {ROLE_OPTIONS.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
          <button className="rp-btn" type="button" onClick={() => void createUser()}>
            创建
          </button>
        </RpDialog>
      ) : null}

      {deleteOpen ? (
        <RpDialog
          title={`删除租户 · ${tenantLabel(deleteOpen)}`}
          label="删除租户"
          closeOnBackdrop={false}
          onClose={() => setDeleteOpen(null)}
        >
          <p className="text-xs text-muted-foreground">
            删除后该租户不再出现在列表中，且无法恢复。仅允许删除没有账号、图片、任务、充值单、工单且余额为零的租户。
          </p>
          <input
            className="rp-input w-full"
            placeholder="输入租户编码或名称确认"
            value={tenantConfirm}
            onChange={(e) => setTenantConfirm(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <button className="rp-btn rp-btn-sm" type="button" onClick={() => setDeleteOpen(null)}>
              取消
            </button>
            <button
              className="rp-btn rp-btn-sm rp-btn-danger"
              type="button"
              disabled={deleteBusy}
              onClick={() => void deleteTenantRow()}
            >
              {deleteBusy ? '删除中…' : '确认删除'}
            </button>
          </div>
        </RpDialog>
      ) : null}

      {opOpen ? (
        <RpDialog
          title={`操作 · ${tenantLabel(opOpen)}`}
          label="账号操作"
          closeOnBackdrop={false}
          onClose={() => setOpOpen(null)}
        >

            <label className="block space-y-1">
              <span className="text-xs text-muted-foreground">操作类型</span>
              <select
                className="rp-input w-full"
                value={opType}
                onChange={(e) => setOpType(e.target.value as OpType)}
              >
                {OP_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block space-y-1">
              <span className="text-xs text-muted-foreground">目标账号</span>
              <select
                className="rp-input w-full"
                value={opUserId}
                disabled={opLoading}
                onChange={(e) => {
                  setOpUserId(e.target.value)
                  setDeleteConfirm('')
                }}
              >
                <option value="">{opLoading ? '加载中…' : '请选择账号'}</option>
                {opAccounts.map((item) => (
                  <option key={item.id} value={String(item.id)}>
                    {item.username}（#{item.id} · {statusLabel(item.status)}）
                  </option>
                ))}
              </select>
            </label>

            {opType === 'credits' ? (
              <div className="space-y-2">
                <input
                  className="rp-input w-full"
                  placeholder="整数Δ（可负）"
                  value={creditDelta}
                  onChange={(e) => setCreditDelta(e.target.value)}
                />
                <input
                  className="rp-input w-full"
                  placeholder="原因（必填）"
                  value={creditReason}
                  onChange={(e) => setCreditReason(e.target.value)}
                />
              </div>
            ) : null}

            {opType === 'roles' ? (
              <input
                className="rp-input w-full"
                placeholder="roleCodes 逗号分隔"
                value={roleCodes}
                onChange={(e) => setRoleCodes(e.target.value)}
              />
            ) : null}

            {opType === 'password' ? (
              <div className="space-y-2">
                <input
                  className="rp-input w-full"
                  type="password"
                  placeholder="新密码"
                  value={pwd1}
                  onChange={(e) => setPwd1(e.target.value)}
                />
                <input
                  className="rp-input w-full"
                  type="password"
                  placeholder="确认密码"
                  value={pwd2}
                  onChange={(e) => setPwd2(e.target.value)}
                />
              </div>
            ) : null}

            {opType === 'delete' ? (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  须输入登录名确认删除
                  {selectedOpAccount ? `：${selectedOpAccount.username}` : ''}
                </p>
                <input
                  className="rp-input w-full"
                  placeholder="确认登录名"
                  value={deleteConfirm}
                  onChange={(e) => setDeleteConfirm(e.target.value)}
                />
              </div>
            ) : null}

            <button
              className="rp-btn"
              type="button"
              onClick={() => void submitOp()}
            >
              提交
            </button>
        </RpDialog>
      ) : null}
    </main>
  )
}
