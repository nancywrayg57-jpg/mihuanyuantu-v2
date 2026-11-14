<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Settings, ChevronUp, ChevronDown } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { fetchSiteSettings, patchSiteSettings } from '../lib/siteSettings'
import { zhError } from '../lib/errors'
import pb from '../lib/pb'
import { useLocaleStore } from '../stores/locale'
import { coverOrThumbUrl } from '../lib/mediaPrepare'

const auth = useAuthStore()
const router = useRouter()
const i18n = useLocaleStore()

const guestPasswordless = ref(true)
const loginCaptcha = ref(false)
const settingsMsg = ref('')
const settingsSaving = ref(false)

const homeRows = ref([])
const homeLoading = ref(false)
const homeSaving = ref(false)
const homeMsg = ref('')

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

function thumb(a) {
  return coverOrThumbUrl(pb, a) || ''
}

async function loadHomeOrder() {
  homeLoading.value = true
  homeMsg.value = ''
  try {
    const list = await pb.collection('archives').getList(1, 500, {
      sort: 'sort_order,-created',
    })
    homeRows.value = list.items.map((a, i) => ({
      id: a.id,
      title: a.title || '',
      category: a.category || '',
      occurred_time: a.occurred_time || '',
      listed: a.listed !== false,
      sort_order: Number(a.sort_order) || 0,
      _thumb: thumb(a),
      _raw: a,
      _idx: i,
    }))
  } catch (e) {
    homeMsg.value = zhError(e, '加载档案列表失败')
  } finally {
    homeLoading.value = false
  }
}

function moveRow(index, dir) {
  const j = index + dir
  if (j < 0 || j >= homeRows.value.length) return
  const copy = homeRows.value.slice()
  const tmp = copy[index]
  copy[index] = copy[j]
  copy[j] = tmp
  homeRows.value = copy.map((r, i) => ({ ...r, _idx: i }))
}

async function saveHomeOrder() {
  if (homeSaving.value) return
  homeSaving.value = true
  homeMsg.value = ''
  try {
    const tasks = homeRows.value.map((row, i) =>
      pb.collection('archives').update(row.id, {
        sort_order: i + 1,
        listed: !!row.listed,
      }),
    )
    await Promise.all(tasks)
    await writeAudit(`home_order n=${homeRows.value.length}`)
    homeMsg.value = i18n.t('homeOrderSaved')
    await loadHomeOrder()
  } catch (e) {
    homeMsg.value = zhError(e, '保存排序失败')
  } finally {
    homeSaving.value = false
  }
}

onMounted(() => {
  if (!auth.isAdmin) {
    router.replace('/')
    return
  }
  loadSettings()
  loadHomeOrder()
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

    <main class="max-w-3xl mx-auto px-4 py-6 space-y-8">
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

      <section class="border border-clay bg-parchment p-4 sm:p-6 space-y-4" data-testid="admin-home-order">
        <div class="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h2 class="font-song text-xl">{{ i18n.t('homeOrder') }}</h2>
            <p class="text-mute text-sm mt-1">{{ i18n.t('homeOrderHint') }}</p>
          </div>
          <button
            type="button"
            class="min-h-tap px-4 bg-cinnabar text-parchment disabled:opacity-60"
            data-testid="save-home-order"
            :disabled="homeSaving || homeLoading || !homeRows.length"
            @click="saveHomeOrder"
          >
            {{ homeSaving ? '保存中…' : i18n.t('saveHomeOrder') }}
          </button>
        </div>
        <p
          v-if="homeMsg"
          class="text-sm"
          :class="homeMsg.includes('失败') ? 'text-cinnabar' : 'text-celadon'"
          data-testid="home-order-msg"
        >
          {{ homeMsg }}
        </p>
        <p v-if="homeLoading" class="text-mute">加载中…</p>
        <ul v-else class="divide-y divide-clay/60 border border-clay" data-testid="home-order-list">
          <li
            v-for="(row, index) in homeRows"
            :key="row.id"
            class="flex items-center gap-2 sm:gap-3 p-2 sm:p-3 bg-rice/40"
            :data-archive-id="row.id"
          >
            <img
              v-if="row._thumb"
              :src="row._thumb"
              alt=""
              class="w-12 h-12 object-cover border border-clay shrink-0"
            />
            <div
              v-else
              class="w-12 h-12 border border-clay shrink-0 grid place-items-center text-mute text-xs"
            >
              —
            </div>
            <div class="min-w-0 flex-1">
              <p class="font-song truncate">{{ row.title }}</p>
              <p class="text-mute text-xs truncate">{{ row.category }} · {{ row.occurred_time }}</p>
            </div>
            <label class="inline-flex items-center gap-1 shrink-0 text-sm">
              <input
                v-model="row.listed"
                type="checkbox"
                class="w-5 h-5"
                data-testid="home-listed-toggle"
              />
              {{ i18n.t('listed') }}
            </label>
            <div class="flex flex-col gap-1 shrink-0">
              <button
                type="button"
                class="min-h-[36px] min-w-[36px] grid place-items-center border border-clay"
                :disabled="index === 0"
                data-testid="home-move-up"
                :title="i18n.t('moveUp')"
                @click="moveRow(index, -1)"
              >
                <ChevronUp class="w-4 h-4" />
              </button>
              <button
                type="button"
                class="min-h-[36px] min-w-[36px] grid place-items-center border border-clay"
                :disabled="index >= homeRows.length - 1"
                data-testid="home-move-down"
                :title="i18n.t('moveDown')"
                @click="moveRow(index, 1)"
              >
                <ChevronDown class="w-4 h-4" />
              </button>
            </div>
          </li>
        </ul>
      </section>
    </main>
  </div>
</template>
