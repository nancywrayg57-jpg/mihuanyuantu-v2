'use client'

import { useCallback, useEffect, useState } from 'react'

import { ApiError, apiFetch } from '@/lib/api'

type Account = {
  id: number
  username: string
  status: number
  tenantId?: number
  roleCodes?: string[]
}

type MeInfo = { roleCodes?: string[]; tenantId?: number | string }

export default function RealphotosUsersPage() {
  const [items, setItems] = useState<Account[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [message, setMessage] = useState('')
  const [operatorTenantId, setOperatorTenantId] = useState<number | null>(null)

  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('rp_merchant')
  const [newTenantId, setNewTenantId] = useState('')

  const [creditUserId, setCreditUserId] = useState('')
  const [creditTenantId, setCreditTenantId] = useState('')
  const [creditDelta, setCreditDelta] = useState('10')
  const [creditReason, setCreditReason] = useState('')

  const [roleUserId, setRoleUserId] = useState('')
  const [roleTenantId, setRoleTenantId] = useState('')
  const [roleCodes, setRoleCodes] = useState('rp_merchant')

  const [pwdUserId, setPwdUserId] = useState('')
  const [pwd1, setPwd1] = useState('')
  const [pwd2, setPwd2] = useState('')

  const [deleteUserId, setDeleteUserId] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState('')

  const load = useCallback(async () => {
    const data = await apiFetch<{ items: Account[]; pageSize: number }>(
      `/api/v1/realphotos/managed-users?page=${page}`,
    )
    setItems(data.items)
    setPageSize(data.pageSize)
  }, [page])

  useEffect(() => {
    void apiFetch<MeInfo>('/api/v1/realphotos/me')
      .then((me) => {
        const tid = me.tenantId != null ? Number(me.tenantId) : null
        setOperatorTenantId(tid)
        if (tid != null) {
          setNewTenantId(String(tid))
          setCreditTenantId(String(tid))
          setRoleTenantId(String(tid))
        }
      })
      .catch(() => undefined)
    void load().catch((error: unknown) =>
      setMessage(error instanceof ApiError ? error.message : '用户读取失败'),
    )
  }, [load])

  async function createUser() {
    try {
      const created = await apiFetch<{ id: number; username: string }>('/api/v1/realphotos/managed-users', {
        method: 'POST',
        body: JSON.stringify({
          tenantId: Number(newTenantId),
          username: newUsername,
          password: newPassword,
          roleCode: newRole,
        }),
      })
      setMessage(`已创建 ${created.username} (#${created.id})`)
      setNewUsername('')
      setNewPassword('')
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '创建失败')
    }
  }

  async function adjustCredits() {
    const raw = creditDelta.trim()
    if (!/^-?\d+$/.test(raw)) {
      setMessage('积分必须是整数，拒绝小数')
      return
    }
    try {
      const data = await apiFetch<{ availableInteger: number }>('/api/v1/realphotos/managed-users/credits', {
        method: 'POST',
        body: JSON.stringify({
          tenantId: Number(creditTenantId),
          userId: Number(creditUserId),
          delta: Number(raw),
          reason: creditReason,
          eventKey: `ui-credit-${creditUserId}-${Date.now()}`,
        }),
      })
      setMessage(`加减分成功；可用=${data.availableInteger}`)
      setCreditReason('')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '加减分失败')
    }
  }

  async function saveRoles() {
    try {
      await apiFetch(`/api/v1/realphotos/managed-users/${Number(roleUserId)}/roles`, {
        method: 'POST',
        body: JSON.stringify({
          tenantId: Number(roleTenantId),
          roleCodes: roleCodes.split(',').map((item) => item.trim()).filter(Boolean),
        }),
      })
      setMessage('角色已保存')
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '角色保存失败')
    }
  }

  async function setStatus(userId: number, enabled: boolean) {
    try {
      await apiFetch(`/api/v1/realphotos/managed-users/${userId}/status`, {
        method: 'POST',
        body: JSON.stringify({ enabled }),
      })
      setMessage(enabled ? '已启用' : '已停用')
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '启停失败')
    }
  }

  async function resetPassword() {
    try {
      await apiFetch(`/api/v1/realphotos/managed-users/${Number(pwdUserId)}/password`, {
        method: 'POST',
        body: JSON.stringify({ password: pwd1, confirm: pwd2 }),
      })
      setMessage('密码已重置（明文不回显、不进日志）')
      setPwd1('')
      setPwd2('')
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '重置失败')
    }
  }

  async function deleteUser() {
    try {
      await apiFetch(`/api/v1/realphotos/managed-users/${Number(deleteUserId)}/delete`, {
        method: 'POST',
        body: JSON.stringify({ confirmUsername: deleteConfirm }),
      })
      setMessage('账号已删除')
      setDeleteConfirm('')
      await load()
    } catch (error: unknown) {
      setMessage(error instanceof ApiError ? error.message : '删除失败')
    }
  }

  return (
    <main className="space-y-4 p-6">
      <h1 className="text-lg font-medium">用户管理</h1>
      <p className="text-sm text-muted-foreground">
        每页 {pageSize} 条。密码只保存散列，不出现在本页与系统日志。当前操作者租户 {operatorTenantId ?? '（读中）'}。
      </p>
      <p className="text-sm">{message}</p>

      <section className="space-y-2 border p-3 text-sm">
        <h2 className="font-medium">创建账号</h2>
        <input className="border px-2 py-1" placeholder="登录名" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} />
        <input className="ml-2 border px-2 py-1" type="password" placeholder="初始密码" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
        <input className="ml-2 w-24 border px-2 py-1" placeholder="租户" value={newTenantId} onChange={(e) => setNewTenantId(e.target.value)} />
        <select className="ml-2 border px-2 py-1" value={newRole} onChange={(e) => setNewRole(e.target.value)}>
          <option value="rp_merchant">rp_merchant</option>
          <option value="rp_order_support">rp_order_support</option>
          <option value="rp_tech_support">rp_tech_support</option>
        </select>
        <button className="ml-2 border px-3 py-1" type="button" onClick={() => void createUser()}>
          创建
        </button>
      </section>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="border px-2 py-1 text-left">编号</th>
            <th className="border px-2 py-1 text-left">登录名</th>
            <th className="border px-2 py-1 text-left">状态</th>
            <th className="border px-2 py-1 text-left">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="border px-2 py-1">{item.id}</td>
              <td className="border px-2 py-1">{item.username}</td>
              <td className="border px-2 py-1">{item.status === 1 ? '启用' : '停用'}</td>
              <td className="border px-2 py-1 space-x-1">
                <button className="border px-2 py-0.5" type="button" onClick={() => void setStatus(item.id, true)}>
                  启用
                </button>
                <button className="border px-2 py-0.5" type="button" onClick={() => void setStatus(item.id, false)}>
                  停用
                </button>
                <button
                  className="border px-2 py-0.5"
                  type="button"
                  onClick={() => {
                    setCreditUserId(String(item.id))
                    setRoleUserId(String(item.id))
                    setPwdUserId(String(item.id))
                    setDeleteUserId(String(item.id))
                    setDeleteConfirm('')
                  }}
                >
                  选中
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2 text-sm">
        <button className="border px-2 py-1" type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          上一页
        </button>
        <span>第 {page} 页</span>
        <button className="border px-2 py-1" type="button" onClick={() => setPage((p) => p + 1)}>
          下一页
        </button>
      </div>

      <section className="space-y-2 border p-3 text-sm">
        <h2 className="font-medium">整数加减分</h2>
        <input className="border px-2 py-1" placeholder="用户编号" value={creditUserId} onChange={(e) => setCreditUserId(e.target.value)} />
        <input className="ml-2 border px-2 py-1" placeholder="租户" value={creditTenantId} onChange={(e) => setCreditTenantId(e.target.value)} />
        <input className="ml-2 w-24 border px-2 py-1" placeholder="整数Δ" value={creditDelta} onChange={(e) => setCreditDelta(e.target.value)} />
        <input className="ml-2 border px-2 py-1" placeholder="原因（必填）" value={creditReason} onChange={(e) => setCreditReason(e.target.value)} />
        <button className="ml-2 border px-3 py-1" type="button" onClick={() => void adjustCredits()}>
          提交加减分
        </button>
      </section>

      <section className="space-y-2 border p-3 text-sm">
        <h2 className="font-medium">保存角色</h2>
        <input className="border px-2 py-1" placeholder="用户编号" value={roleUserId} onChange={(e) => setRoleUserId(e.target.value)} />
        <input className="ml-2 border px-2 py-1" placeholder="租户" value={roleTenantId} onChange={(e) => setRoleTenantId(e.target.value)} />
        <input className="ml-2 w-64 border px-2 py-1" placeholder="roleCodes 逗号分隔" value={roleCodes} onChange={(e) => setRoleCodes(e.target.value)} />
        <button className="ml-2 border px-3 py-1" type="button" onClick={() => void saveRoles()}>
          保存角色
        </button>
      </section>

      <section className="space-y-2 border p-3 text-sm">
        <h2 className="font-medium">重置密码</h2>
        <input className="border px-2 py-1" placeholder="用户编号" value={pwdUserId} onChange={(e) => setPwdUserId(e.target.value)} />
        <input className="ml-2 border px-2 py-1" type="password" placeholder="新密码" value={pwd1} onChange={(e) => setPwd1(e.target.value)} />
        <input className="ml-2 border px-2 py-1" type="password" placeholder="确认密码" value={pwd2} onChange={(e) => setPwd2(e.target.value)} />
        <button className="ml-2 border px-3 py-1" type="button" onClick={() => void resetPassword()}>
          重置
        </button>
      </section>

      <section className="space-y-2 border p-3 text-sm">
        <h2 className="font-medium">删除（须输入登录名确认）</h2>
        <input className="border px-2 py-1" placeholder="用户编号" value={deleteUserId} onChange={(e) => setDeleteUserId(e.target.value)} />
        <input className="ml-2 border px-2 py-1" placeholder="确认登录名" value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} />
        <button className="ml-2 border px-3 py-1" type="button" onClick={() => void deleteUser()}>
          删除
        </button>
      </section>
    </main>
  )
}
