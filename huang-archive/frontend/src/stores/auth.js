import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import pb from '../lib/pb'
import { normalizePassword, normalizePersonName, resolveIdentity } from '../lib/roster'
import { isGuestUser } from '../lib/guest'
import { zhError } from '../lib/errors'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(pb.authStore.model)
  const token = ref(pb.authStore.token)
  const error = ref('')
  const loading = ref(false)

  pb.authStore.onChange((t, model) => {
    token.value = t
    user.value = model
  })

  const isLoggedIn = computed(() => !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isGuest = computed(() => isGuestUser(user.value))
  const canUpload = computed(() => isLoggedIn.value && !isGuest.value)
  const displayName = computed(() => user.value?.display_name || '')

  async function authOnce(identity, password) {
    return pb.collection('users').authWithPassword(identity, password)
  }

  async function resolveDynamicIdentity(nameOrEmail) {
    const raw = normalizePersonName(nameOrEmail)
    if (!raw || raw.includes('@')) return null
    try {
      const res = await fetch(`/api/hz/resolve-name?name=${encodeURIComponent(raw)}`)
      if (!res.ok) return null
      return await res.json()
    } catch {
      return null
    }
  }

  async function loginAsGuest(opts = {}) {
    loading.value = true
    error.value = ''
    try {
      const res = await fetch('/api/hz/guest-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket: opts.ticket || undefined,
          captcha_id: opts.captcha_id || undefined,
          captcha_code: opts.captcha_code || undefined,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data?.message || '吊唁贵宾登录失败')
      }
      if (!data?.token || !data?.record) {
        throw new Error('吊唁贵宾登录失败')
      }
      pb.authStore.save(data.token, data.record)
      user.value = data.record
      token.value = data.token
      return data.record
    } catch (e) {
      error.value = zhError(e, '吊唁贵宾登录失败')
      throw e
    } finally {
      loading.value = false
    }
  }

  async function loginViaApi(nameOrEmail, password, opts = {}) {
    const res = await fetch('/api/hz/member-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: String(nameOrEmail || '').trim(),
        password: normalizePassword(password),
        ticket: opts.ticket || undefined,
        captcha_id: opts.captcha_id || undefined,
        captcha_code: opts.captcha_code || undefined,
      }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data?.message || '登录失败：姓名或密码不正确')
    if (!data?.token || !data?.record) throw new Error('登录失败')
    pb.authStore.save(data.token, data.record)
    user.value = data.record
    token.value = data.token
    return data.record
  }

  async function login(nameOrEmail, password, opts = {}) {
    loading.value = true
    error.value = ''
    try {
      const pwd = normalizePassword(password)
      if (!pwd) throw new Error('请输入密码')

      // Prefer gated API when captcha ticket/codes provided, or always for consistency
      if (opts.ticket || opts.captcha_id || opts.useApi) {
        return await loginViaApi(nameOrEmail, password, opts)
      }

      let identity = resolveIdentity(nameOrEmail)

      // Dynamic members not in static roster
      if (!identity?.email) {
        const dyn = await resolveDynamicIdentity(nameOrEmail)
        if (dyn?.email) {
          identity = {
            display_name: dyn.display_name,
            email: dyn.email,
            username: dyn.username,
            role: dyn.role,
          }
        }
      }

      const candidates = []
      if (identity?.email) candidates.push(identity.email)
      if (identity?.username) candidates.push(identity.username)
      if (!candidates.length && nameOrEmail) candidates.push(String(nameOrEmail).trim())

      if (!candidates.length) throw new Error('请输入或点选家族姓名')

      if (!identity?.email && /[\u4e00-\u9fff]/.test(candidates[0] || '')) {
        throw new Error('未找到该家族姓名，请点选列表中的姓名')
      }

      let lastErr
      for (const id of candidates) {
        try {
          const auth = await authOnce(id, pwd)
          user.value = auth.record
          token.value = auth.token
          return auth.record
        } catch (e) {
          lastErr = e
        }
      }
      throw lastErr || new Error('登录失败，请检查姓名与密码')
    } catch (e) {
      error.value = zhError(e, '登录失败：姓名或密码不正确')
      throw e
    } finally {
      loading.value = false
    }
  }

  async function changePassword(newPassword, confirmPassword) {
    if (!user.value?.id) throw new Error('未登录')
    const np = normalizePassword(newPassword)
    const cp = normalizePassword(confirmPassword)
    if (!np || np.length < 6) throw new Error('新密码至少 6 位')
    if (np !== cp) throw new Error('两次输入的密码不一致')
    await pb.collection('users').update(user.value.id, {
      password: np,
      passwordConfirm: cp,
    })
  }

  async function changePasswordWithOld(oldPassword, newPassword, confirmPassword) {
    if (!user.value?.id) throw new Error('未登录')
    const op = normalizePassword(oldPassword)
    const np = normalizePassword(newPassword)
    const cp = normalizePassword(confirmPassword)
    if (!np || np.length < 6) throw new Error('新密码至少 6 位')
    if (np !== cp) throw new Error('两次输入的密码不一致')
    await pb.collection('users').update(user.value.id, {
      oldPassword: op,
      password: np,
      passwordConfirm: cp,
    })
  }

  function logout() {
    pb.authStore.clear()
    user.value = null
    token.value = ''
  }

  return {
    user,
    token,
    error,
    loading,
    isLoggedIn,
    isAdmin,
    isGuest,
    canUpload,
    displayName,
    login,
    loginAsGuest,
    changePassword,
    changePasswordWithOld,
    logout,
  }
})
