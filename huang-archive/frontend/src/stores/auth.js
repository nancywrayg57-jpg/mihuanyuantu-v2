import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import pb from '../lib/pb'
import { normalizePassword, resolveIdentity } from '../lib/roster'

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
  const displayName = computed(() => user.value?.display_name || '')

  async function authOnce(identity, password) {
    return pb.collection('users').authWithPassword(identity, password)
  }

  async function login(nameOrEmail, password) {
    loading.value = true
    error.value = ''
    try {
      const identity = resolveIdentity(nameOrEmail)
      const pwd = normalizePassword(password)
      if (!pwd) throw new Error('请输入密码')

      const candidates = []
      if (identity?.email) candidates.push(identity.email)
      if (identity?.username) candidates.push(identity.username)
      if (!candidates.length && nameOrEmail) candidates.push(String(nameOrEmail).trim())

      if (!candidates.length) throw new Error('请输入或点选家族姓名')

      // Unknown Chinese name (not in roster) cannot auth against PocketBase identity fields
      if (!identity?.email && !identity?.username?.includes('@') && /[\u4e00-\u9fff]/.test(candidates[0])) {
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
      const msg = e?.message || ''
      if (msg.includes('Failed to authenticate') || e?.status === 400) {
        error.value = '登录失败：姓名或密码不正确（密码请用半角英文/数字，默认成员密码 hzs1933）'
      } else {
        error.value = msg || '登录失败，请检查姓名与密码'
      }
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
    displayName,
    login,
    changePassword,
    changePasswordWithOld,
    logout,
  }
})
