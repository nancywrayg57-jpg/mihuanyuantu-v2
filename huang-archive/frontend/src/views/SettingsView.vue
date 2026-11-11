<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Settings } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { fetchSiteSettings, patchSiteSettings } from '../lib/siteSettings'
import { zhError } from '../lib/errors'
import pb from '../lib/pb'
import { useLocaleStore } from '../stores/locale'

const auth = useAuthStore()
const router = useRouter()
const i18n = useLocaleStore()

const guestPasswordless = ref(true)
const loginCaptcha = ref(false)
const settingsMsg = ref('')
const settingsSaving = ref(false)

async function writeAudit(detail) {
  try {
    await pb.collection('audit_logs').create({
      action: 'update_site_settings',
      target: 'global',
      detail,
      actor: auth.user.id,
      actor_name: auth.displayName,
    })
  } catch (_) {}
}

async function loadSettings() {
  try {
    const s = await fetchSiteSettings()
    guestPasswordless.value = s.guest_passwordless !== false
    loginCaptcha.value = !!s.login_captcha
  } catch (_) {}
}

async function saveSettings() {
  if (settingsSaving.value) return
  settingsSaving.value = true
  settingsMsg.value = ''
  try {
    const s = await patchSiteSettings(auth.token, {
      guest_passwordless: guestPasswordless.value,
      login_captcha: loginCaptcha.value,
    })
    guestPasswordless.value = s.guest_passwordless !== false
    loginCaptcha.value = !!s.login_captcha
    await writeAudit(
      `guest_passwordless=${guestPasswordless.value};login_captcha=${loginCaptcha.value}`,
    )
    settingsMsg.value = '全局设置已保存'
  } catch (e) {
    settingsMsg.value = zhError(e, '保存设置失败')
  } finally {
    settingsSaving.value = false
  }
}

onMounted(() => {
  if (!auth.isAdmin) {
    router.replace('/')
    return
  }
  loadSettings()
})
</script>

<template>
  <div class="min-h-screen pb-10" data-testid="admin-settings-page">
    <header class="border-b border-clay bg-parchment/90 sticky top-0 z-40">
      <div class="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3 flex-wrap">
        <button
          type="button"
          class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
          @click="router.push('/')"
        >
          <ArrowLeft class="w-5 h-5" /> 返回
        </button>
        <h1 class="font-song text-xl flex-1 inline-flex items-center gap-2">
          <Settings class="w-5 h-5" /> {{ i18n.t('settings') }}
        </h1>
      </div>
    </header>

    <main class="max-w-3xl mx-auto px-4 py-6">
      <section class="border border-clay bg-parchment p-4 sm:p-6 space-y-4" data-testid="admin-site-settings">
        <label class="flex items-center justify-between gap-4 min-h-tap">
          <span>吊唁免登录模式</span>
          <input
            v-model="guestPasswordless"
            type="checkbox"
            class="w-6 h-6"
            data-testid="toggle-guest-passwordless"
          />
        </label>
        <p class="text-mute text-sm -mt-2">
          开启后，登录页默认「吊唁贵宾」可免密进入；关闭后须点选家族成员并输入密码。
        </p>
        <label class="flex items-center justify-between gap-4 min-h-tap">
          <span>登录弹出图形验证码</span>
          <input
            v-model="loginCaptcha"
            type="checkbox"
            class="w-6 h-6"
            data-testid="toggle-login-captcha"
          />
        </label>
        <p class="text-mute text-sm -mt-2">开启后，进入纪念馆前需填写图形验证码。</p>
        <div class="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            class="min-h-tap px-4 bg-cinnabar text-parchment disabled:opacity-60"
            data-testid="save-site-settings"
            :disabled="settingsSaving"
            @click="saveSettings"
          >
            {{ settingsSaving ? '保存中…' : i18n.t('save') }}
          </button>
          <p
            v-if="settingsMsg"
            class="text-sm"
            :class="settingsMsg.includes('失败') ? 'text-cinnabar' : 'text-celadon'"
          >
            {{ settingsMsg }}
          </p>
        </div>
      </section>
    </main>
  </div>
</template>
