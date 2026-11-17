/**
 * 2026-11-17：蜜獾原图账号登录后应直接进入业务工作台，
 * 而不是平台默认的「欢迎」页。角色或权限任一命中即视为蜜獾原图账号。
 */

const REALPHOTOS_ROLES = new Set([
  'rp_admin',
  'rp_merchant',
  'rp_order_support',
  'rp_tech_support',
])

type SessionLike =
  | {
      roles?: string[] | null
      permissions?: string[] | null
    }
  | null
  | undefined

export const REALPHOTOS_HOME = '/realphotos/workspace'

export function isRealphotosSession(session: SessionLike): boolean {
  if (!session) return false
  const roles = Array.isArray(session.roles) ? session.roles : []
  if (roles.some((role) => REALPHOTOS_ROLES.has(String(role)))) return true
  const permissions = Array.isArray(session.permissions) ? session.permissions : []
  return permissions.some((perm) => String(perm).startsWith('realphotos:'))
}
