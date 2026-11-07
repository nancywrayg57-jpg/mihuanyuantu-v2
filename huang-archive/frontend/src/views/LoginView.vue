<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ChevronDown } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { FAMILY_ROSTER } from '../lib/roster'
import { GUEST_DISPLAY_NAME, isGuestName } from '../lib/guest'
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

const isGuestSelected = computed(() => isGuestName(name.value))

const stepHint = computed(() => {
  if (step.value === 1) return isGuestSelected.value ? '吊唁贵宾' : '选择姓名'
  if (step.value === 2) return '输入密码'
  return '进入纪念馆'
})

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

/** Default guest chip → go straight to enter (no password). */
function onIdentityClick() {
  localError.value = ''
  if (isGuestSelected.value) {
    step.value = 3
    return
  }
  openPicker()
}

function pickGuest() {
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
  if (isGuestName(person.display_name) || person.role === 'guest') {
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
    if (isGuestSelected.value) {
      await auth.loginAsGuest()
    } else {
      if (!password.value.trim()) {
        localError.value = '请输入密码'
        step.value = 2
        return
      }
      await auth.login(name.value, password.value)
    }
    router.replace(route.query.redirect || '/')
  } catch (e) {
    localError.value = auth.error || zhError(e, '登录失败')
    step.value = isGuestSelected.value ? 1 : 2
  }
}

watch(showPicker, (open) => {
  document.documentElement.classList.toggle('overflow-hidden', open)
})

onMounted(loadNames)
</script>

<template>
  <div
    class="login-screen relative min-h-[100dvh] w-full overflow-hidden text-white"
    data-testid="login-screen"
  >
    <div
      class="absolute inset-0 bg-cover bg-no-repeat"
      style="background-image: url('/login-bg.jpg'); background-position: 28% center"
      aria-hidden="true"
    />
    <div class="absolute inset-0 bg-gradient-to-b from-black/55 via-black/25 to-black/70" aria-hidden="true" />

    <div class="relative z-10 min-h-[100dvh] flex flex-col px-5 pt-[max(2.5rem,env(safe-area-inset-top))] pb-[max(1.5rem,env(safe-area-inset-bottom))]">
      <header class="pt-4 sm:pt-8 text-center shrink-0">
        <h1
          class="font-lishu text-[2.35rem] sm:text-5xl md:text-6xl leading-tight tracking-wide drop-shadow-[0_2px_12px_rgba(0,0,0,0.55)]"
          data-testid="login-title"
        >
          黄志松家族纪念馆
        </h1>
        <p
          class="mt-3 text-base sm:text-lg tracking-[0.2em] text-white/90 font-sans"
          data-testid="login-subtitle"
        >
          1933 -- 2026
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

        <!-- Step 1: default 吊唁贵宾; tap → enter; chevron → family list -->
        <div
          v-if="step === 1"
          class="login-field w-full min-h-[52px] rounded-2xl inline-flex items-stretch overflow-hidden"
          data-testid="login-identity"
        >
          <button
            type="button"
            class="flex-1 min-h-[52px] px-4 text-left text-white"
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

        <!-- Step 2: password (family only) -->
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

        <!-- Step 3: enter memorial -->
        <button
          v-else
          type="button"
          class="w-full min-h-[52px] rounded-2xl bg-cinnabar text-parchment text-lg tracking-widest font-medium disabled:opacity-60 shadow-lg shadow-black/30"
          data-testid="login-submit"
          :disabled="auth.loading"
          @click="onEnter"
        >
          {{ auth.loading ? '进入中…' : '进入纪念馆' }}
        </button>

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
</style>
