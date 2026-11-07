<script setup>
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { FAMILY_ROSTER } from '../lib/roster'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const name = ref('')
const password = ref('')
const showPicker = ref(false)
const localError = ref('')

const filtered = computed(() => {
  const q = name.value.trim()
  if (!q) return FAMILY_ROSTER
  return FAMILY_ROSTER.filter((p) => p.display_name.includes(q))
})

function pick(person) {
  name.value = person.display_name
  showPicker.value = false
}

async function onSubmit() {
  localError.value = ''
  try {
    await auth.login(name.value, password.value)
    router.replace(route.query.redirect || '/')
  } catch (e) {
    localError.value = auth.error || e.message || '登录失败'
  }
}
</script>

<template>
  <div class="min-h-screen px-4 py-10 flex items-center justify-center">
    <div class="w-full max-w-md">
      <div class="mb-8">
        <h1 class="font-song text-2xl sm:text-3xl text-ink leading-snug">
          黄志松家族记忆档案馆
        </h1>
        <p class="mt-2 text-mute text-base">家族内部珍藏 · 请使用中文姓名登录</p>
      </div>

      <form class="bg-parchment border border-clay p-6 space-y-5" @submit.prevent="onSubmit">
        <div>
          <label class="block text-mute mb-2">家族姓名</label>
          <input
            v-model="name"
            type="text"
            autocomplete="username"
            class="w-full min-h-tap px-4 border border-clay bg-rice outline-none focus:border-cinnabar"
            placeholder="输入或点选姓名，如 黄祥财"
            @focus="showPicker = true"
          />
          <button
            type="button"
            class="mt-2 text-celadon underline underline-offset-4"
            @click="showPicker = !showPicker"
          >
            点选家族姓名
          </button>
          <div
            v-if="showPicker"
            class="mt-3 max-h-48 overflow-auto border border-clay bg-rice divide-y divide-clay"
          >
            <button
              v-for="p in filtered"
              :key="p.email"
              type="button"
              class="w-full text-left px-4 min-h-tap hover:bg-clay/40"
              @click="pick(p)"
            >
              {{ p.display_name }}
              <span class="text-mute text-sm ml-2">{{ p.role === 'admin' ? '管理员' : '成员' }}</span>
            </button>
          </div>
        </div>

        <div>
          <label class="block text-mute mb-2">密码</label>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            lang="en"
            inputmode="latin"
            spellcheck="false"
            class="w-full min-h-tap px-4 border border-clay bg-rice outline-none focus:border-cinnabar"
            placeholder="半角密码，成员默认 hzs1933"
          />
          <p class="mt-2 text-mute text-sm">密码请使用半角英文与数字；中文输入法下注意切换到英文。</p>
        </div>

        <p v-if="localError" class="text-cinnabar">{{ localError }}</p>

        <button
          type="submit"
          class="w-full min-h-tap bg-cinnabar text-parchment font-medium tracking-wide disabled:opacity-60"
          :disabled="auth.loading"
        >
          {{ auth.loading ? '登录中…' : '进入档案馆' }}
        </button>
      </form>
    </div>
  </div>
</template>
