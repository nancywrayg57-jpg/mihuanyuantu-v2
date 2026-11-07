import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import pb from '../lib/pb'
import { resolveIdentity } from '../lib/roster'

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

  async function login(nameOrEmail, password) {
    loading.value = true
    error.value = ''
    try {
      const identity = resolveIdentity(nameOrEmail)
      const loginId = identity?.email || nameOrEmail
      if (!loginId) throw new Error('请输入或点选家族姓名')
      const auth = await pb.collection('users').authWithPassword(loginId, password)
      user.value = auth.record
      token.value = auth.token
      return auth.record
    } catch (e) {
      error.value = e?.message || '登录失败，请检查姓名与密码'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function changePassword(newPassword, confirmPassword) {
    if (!user.value?.id) throw new Error('未登录')
    if (!newPassword || newPassword.length < 6) throw new Error('新密码至少 6 位')
    if (newPassword !== confirmPassword) throw new Error('两次输入的密码不一致')
    await pb.collection('users').update(user.value.id, {
      password: newPassword,
      passwordConfirm: confirmPassword,
      oldPassword: undefined,
    })
    // Re-auth to refresh token with new password is caller's responsibility when needed
  }

  async function changePasswordWithOld(oldPassword, newPassword, confirmPassword) {
    if (!user.value?.id) throw new Error('未登录')
    if (!newPassword || newPassword.length < 6) throw new Error('新密码至少 6 位')
    if (newPassword !== confirmPassword) throw new Error('两次输入的密码不一致')
    await pb.collection('users').update(user.value.id, {
      oldPassword,
      password: newPassword,
      passwordConfirm: confirmPassword,
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
