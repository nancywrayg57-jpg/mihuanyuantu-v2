/** Shared mourning-guest identity (passwordless entry). */
export const GUEST_DISPLAY_NAME = '吊唁贵宾'
export const GUEST_ROLE = 'guest'

export function isGuestUser(user) {
  if (!user) return false
  return user.role === GUEST_ROLE || user.display_name === GUEST_DISPLAY_NAME
}

export function isGuestName(name) {
  return String(name || '').trim() === GUEST_DISPLAY_NAME
}
