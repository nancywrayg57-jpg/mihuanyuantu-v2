<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ChevronDown, RefreshCw } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { FAMILY_ROSTER } from '../lib/roster'
import { GUEST_DISPLAY_NAME, isGuestName } from '../lib/guest'
import { fetchCaptcha, fetchSiteSettings, SITE_TITLE, verifyCaptcha } from '../lib/siteSettings'
import { zhError } from '../lib/errors'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

/** 1 身份 → 2 输密码（家族）→ 3 进入 */
const step = ref(1)
const name = ref(GUEST_DISPLAY_NAME)
const password = ref('')
const showPicker = ref(false)
const localError = ref('')
const roster = ref([...FAMILY_ROSTER])
const pwdInput = ref(null)

const guestPasswordless = ref(true)
const loginCaptcha = ref(false)
const captchaId = ref('')
const captchaSvg = ref('')
const captchaCode = ref('')
const captchaImg = ref('')

const isGuestSelected = computed(() => isGuestName(name.value))

const stepHint = computed(() => {
  if (step.value === 1) return isGuestSelected.value ? GUEST_DISPLAY_NAME : '选择姓名'
  if (step.value === 2) return '输入密码'
  return '进入纪念馆'
})

async function loadSettings() {
  try {
    const s = await fetchSiteSettings()
    guestPasswordless.value = s.guest_passwordless !== false
    loginCaptcha.value = !!s.login_captcha
    if (!guestPasswordless.value && isGuestSelected.value) {
      name.value = ''
    } else if (guestPasswordless.value && !name.value) {
      name.value = GUEST_DISPLAY_NAME
    }
  } catch (_) {
    guestPasswordless.value = true
    loginCaptcha.value = false
  }
}

async function loadCaptcha() {
  if (!loginCaptcha.value) return
  try {
    const c = await fetchCaptcha()
    captchaId.value = c.id
    captchaSvg.value = c.svg || ''
    captchaCode.value = ''
    captchaImg.value = c.svg
      ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(c.svg)}`
      : ''
  } catch (e) {
    localError.value = zhError(e, '验证码加载失败')
  }
}

async function ensureCaptchaTicket() {
  if (!loginCaptcha.value) return undefined
  if (!captchaCode.value.trim()) throw new Error('请输入验证码')
  return verifyCaptcha(captchaId.value, captchaCode.value.trim())
}

async function loadNames() {
  try {
    const res = await fetch('/api/hz/member-names')
    if (!res.ok) return
    const data = await res.json()
    if (Array.isArray(data.items) && data.items.length) {
      roster.value = data.items
        .filter((p) => p.role !== 'guest' && p.display_name !== GUEST_DISPLAY_NAME)
        .map((p) => ({
          display_name: p.display_name,
          role: p.role,
          email: p.display_name,
        }))
    }
  } catch (_) {}
}

function openPicker(e) {
  e?.stopPropagation?.()
  localError.value = ''
  showPicker.value = true
}

function onIdentityClick() {
  localError.value = ''
  if (isGuestSelected.value && guestPasswordless.value) {
    step.value = 3
    return
  }
  openPicker()
}

function pickGuest() {
  if (!guestPasswordless.value) {
    localError.value = '吊唁免登录模式已关闭，请选择家族成员并输入密码'
    return
  }
  name.value = GUEST_DISPLAY_NAME
  password.value = ''
  localError.value = ''
  showPicker.value = false
  step.value = 3
}

function pick(person) {
  name.value = person.display_name
  showPicker.value = false
  password.value = ''
  localError.value = ''
  if ((isGuestName(person.display_name) || person.role === 'guest') && guestPasswordless.value) {
    step.value = 3
    return
  }
  step.value = 2
  requestAnimationFrame(() => pwdInput.value?.focus?.())
}

function backToName() {
  step.value = 1
  password.value = ''
  localError.value = ''
  showPicker.value = false
}

function goEnterStep() {
  localError.value = ''
  if (!password.value.trim()) {
    localError.value = '请输入密码'
    return
  }
  step.value = 3
}

async function onEnter() {
  localError.value = ''
  if (!name.value) {
    localError.value = '请先选择身份'
    step.value = 1
    return
  }
  try {
    const ticket = await ensureCaptchaTicket()
    if (isGuestSelected.value) {
      if (!guestPasswordless.value) {
        throw new Error('吊唁免登录模式已关闭，请使用家族姓名与密码登录')
      }
      await auth.loginAsGuest({ ticket })
    } else {
      if (!password.value.trim()) {
        localError.value = '请输入密码'
        step.value = 2
        return
      }
      await auth.login(name.value, password.value, {
        ticket,
        useApi: !!loginCaptcha.value,
      })
    }
    router.replace(route.query.redirect || '/')
  } catch (e) {
    localError.value = auth.error || zhError(e, '登录失败')
    if (loginCaptcha.value) await loadCaptcha()
    step.value = isGuestSelected.value ? 1 : 2
  }
}

watch(showPicker, (open) => {
  document.documentElement.classList.toggle('overflow-hidden', open)
})

watch(loginCaptcha, (on) => {
  if (on) loadCaptcha()
})

onMounted(async () => {
  await Promise.all([loadNames(), loadSettings()])
  if (loginCaptcha.value) await loadCaptcha()
})
</script>

<template>
  <div
    class="login-screen relative min-h-[100dvh] w-full overflow-hidden text-white"
    data-testid="login-screen"
  >
    <!-- Mobile: unchanged cover crop of login-bg.jpg. Desktop: full near-1:1 portrait + side tone fills. -->
    <div class="login-hero-stage absolute inset-0" aria-hidden="true" data-testid="login-hero-stage">
      <div class="login-hero-fill absolute inset-0" data-testid="login-hero-fill" />
      <div class="login-hero-photo login-hero-photo--mobile absolute inset-0" data-testid="login-hero-mobile" />
      <div class="login-hero-photo login-hero-photo--desktop absolute inset-0" data-testid="login-hero-desktop" />
    </div>
    <div class="absolute inset-0 bg-gradient-to-b from-black/35 via-black/15 to-black/70 pointer-events-none" aria-hidden="true" />

    <div class="relative z-10 min-h-[100dvh] flex flex-col px-3 sm:px-5 pt-[max(0.4rem,env(safe-area-inset-top))] pb-[max(1.5rem,env(safe-area-inset-bottom))]">
      <header class="login-hero-copy pt-1.5 sm:pt-6 text-center shrink-0">
        <h1
          class="login-title font-lishu drop-shadow-[0_2px_10px_rgba(0,0,0,0.55)]"
          data-testid="login-title"
        >
          {{ SITE_TITLE }}
        </h1>
        <p
          class="login-subtitle mt-1 sm:mt-2 text-white/90 font-sans"
          data-testid="login-subtitle"
        >
          （1933—2026）
        </p>
      </header>

      <div class="flex-1" aria-hidden="true" />

      <div class="w-full max-w-sm mx-auto space-y-3 pb-4" data-testid="login-slot">
        <button
          v-if="step > 1 && name"
          type="button"
          class="block w-full text-center text-white/95 text-lg tracking-wide"
          data-testid="login-selected-name"
          title="点击可重新选择身份"
          @click="backToName"
        >
          {{ name }}
        </button>

        <p v-if="localError" class="text-center text-sm text-red-200" data-testid="login-error">
          {{ localError }}
        </p>

        <div
          v-if="step === 1"
          class="login-field w-full min-h-[52px] rounded-2xl inline-flex items-stretch overflow-hidden"
          data-testid="login-identity"
        >
          <button
            type="button"
            class="flex-1 min-h-[52px] px-4 text-left"
            :class="name ? 'text-white' : 'text-white/55'"
            data-testid="login-pick-name"
            @click="onIdentityClick"
          >
            {{ name || '选择姓名' }}
          </button>
          <button
            type="button"
            class="min-h-[52px] px-3 border-l border-white/20 text-white/70"
            data-testid="login-open-roster"
            title="选择家族成员"
            aria-label="选择家族成员"
            @click="openPicker"
          >
            <ChevronDown class="w-5 h-5" />
          </button>
        </div>

        <form v-else-if="step === 2" @submit.prevent="goEnterStep">
          <input
            ref="pwdInput"
            v-model="password"
            type="password"
            autocomplete="current-password"
            lang="en"
            inputmode="latin"
            spellcheck="false"
            class="login-field w-full min-h-[52px] px-4 rounded-2xl outline-none text-white placeholder:text-white/55"
            placeholder="输入密码"
            data-testid="login-password"
          />
        </form>

        <template v-else>
          <div
            v-if="loginCaptcha"
            class="space-y-2"
            data-testid="login-captcha"
          >
            <div class="flex items-center gap-2">
              <img
                v-if="captchaImg"
                :src="captchaImg"
                alt="验证码"
                class="h-[52px] w-[160px] rounded-xl bg-parchment object-contain"
                data-testid="captcha-image"
              />
              <button
                type="button"
                class="min-h-[52px] px-3 login-field rounded-2xl"
                title="刷新验证码"
                data-testid="captcha-refresh"
                @click="loadCaptcha"
              >
                <RefreshCw class="w-5 h-5" />
              </button>
            </div>
            <input
              v-model="captchaCode"
              type="text"
              autocomplete="off"
              class="login-field w-full min-h-[52px] px-4 rounded-2xl outline-none text-white placeholder:text-white/55 uppercase tracking-widest"
              placeholder="输入验证码"
              data-testid="captcha-input"
            />
          </div>
          <button
            type="button"
            class="w-full min-h-[52px] rounded-2xl bg-cinnabar text-parchment text-lg tracking-widest font-medium disabled:opacity-60 shadow-lg shadow-black/30"
            data-testid="login-submit"
            :disabled="auth.loading"
            @click="onEnter"
          >
            {{ auth.loading ? '进入中…' : '进入纪念馆' }}
          </button>
        </template>

        <p class="sr-only">步骤 {{ step }} / 3 · {{ stepHint }}</p>
      </div>
    </div>

    <div
      v-if="showPicker"
      class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/55 p-0 sm:p-6"
      data-testid="login-name-sheet"
      @click.self="showPicker = false"
    >
      <div class="w-full max-w-md max-h-[75dvh] bg-[#1a1714]/95 backdrop-blur-md border border-white/15 rounded-t-3xl sm:rounded-2xl overflow-hidden flex flex-col">
        <div class="px-5 py-4 border-b border-white/10 flex items-center justify-between">
          <h2 class="text-lg text-white">选择身份</h2>
          <button type="button" class="text-white/70 min-h-tap px-2" @click="showPicker = false">关闭</button>
        </div>
        <div class="overflow-y-auto divide-y divide-white/10">
          <button
            v-if="guestPasswordless"
            type="button"
            class="w-full text-left px-5 min-h-tap text-white hover:bg-white/10"
            data-testid="login-pick-guest"
            @click="pickGuest"
          >
            {{ GUEST_DISPLAY_NAME }}
            <span class="text-white/45 text-sm ml-2">免密进入</span>
          </button>
          <button
            v-for="p in roster"
            :key="p.display_name"
            type="button"
            class="w-full text-left px-5 min-h-tap text-white hover:bg-white/10"
            @click="pick(p)"
          >
            {{ p.display_name }}
            <span class="text-white/45 text-sm ml-2">{{ p.role === 'admin' ? '管理员' : '成员' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-field {
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.28);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

/*
 * 方案 A — Desktop only:
 * Side fills use deep black + dark brick-brown (dominant portrait tones).
 * Portrait is contain/centered — never stretched to wide aspect.
 * Mobile photo layer keeps prior cover crop (accepted).
 */
.login-hero-fill {
  background:
    radial-gradient(ellipse 70% 90% at 50% 45%, #3a1e18 0%, transparent 62%),
    linear-gradient(
      90deg,
      #050403 0%,
      #140c0a 14%,
      #2a1612 36%,
      #3a1e18 50%,
      #2a1612 64%,
      #140c0a 86%,
      #050403 100%
    );
}

.login-hero-photo--mobile {
  display: block;
  background-image: url('/login-bg.jpg');
  background-size: cover;
  background-position: 30% 62%;
  background-repeat: no-repeat;
}

.login-hero-photo--desktop {
  display: none;
  background-image: url('/login-bg-desktop.jpg');
  background-size: contain;
  background-position: center center;
  background-repeat: no-repeat;
}

@media (min-width: 768px) {
  .login-hero-photo--mobile {
    display: none;
  }
  .login-hero-photo--desktop {
    display: block;
  }
}

.login-hero-copy {
  /* Fluid title size: 8 隶书字 must fit one line on 320px-wide phones. */
  --login-title-size: clamp(1.28rem, 0.55rem + 4.6vw, 3rem);
}

.login-title {
  font-size: var(--login-title-size);
  line-height: 1.12;
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: clip;
  max-width: 100%;
}

/* 「主标题字号 − 2」→ two rem/Tailwind steps (0.25rem × 2). */
.login-subtitle {
  font-size: calc(var(--login-title-size) - 0.5rem);
  line-height: 1.2;
  letter-spacing: 0.08em;
}
</style>
