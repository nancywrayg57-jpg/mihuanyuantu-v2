<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { useLocaleStore } from '../stores/locale'
import FlagIcon from './FlagIcon.vue'

const locale = useLocaleStore()
const open = ref(false)
const root = ref(null)

function toggle() {
  open.value = !open.value
}

function pick(code) {
  locale.setOverride(code)
  open.value = false
}

function onDoc(e) {
  if (!root.value) return
  if (!root.value.contains(e.target)) open.value = false
}

onMounted(() => document.addEventListener('click', onDoc))
onUnmounted(() => document.removeEventListener('click', onDoc))
</script>

<template>
  <div ref="root" class="relative" data-testid="lang-switcher">
    <button
      type="button"
      class="min-h-tap px-2 sm:px-3 border border-clay bg-parchment inline-flex items-center gap-1.5 text-sm"
      data-testid="lang-switcher-trigger"
      :aria-expanded="open"
      @click="toggle"
    >
      <FlagIcon :code="locale.localeMeta.flag" :size="18" />
      <span>{{ locale.localeMeta.native }}</span>
      <ChevronDown class="w-4 h-4 text-mute" />
    </button>
    <div
      v-if="open"
      class="absolute right-0 mt-2 z-50 min-w-[11rem] bg-white border border-clay/60 shadow-lg rounded-md py-1"
      data-testid="lang-switcher-menu"
    >
      <div class="absolute -top-1.5 right-5 w-3 h-3 bg-white border-l border-t border-clay/60 rotate-45" />
      <button
        v-for="opt in locale.LOCALES"
        :key="opt.code"
        type="button"
        class="relative w-full px-3 py-2.5 flex items-center gap-2.5 text-left hover:bg-rice text-sm"
        :class="opt.code === locale.locale ? 'bg-rice/80' : ''"
        :data-testid="'lang-opt-' + opt.code"
        @click="pick(opt.code)"
      >
        <FlagIcon :code="opt.flag" :size="18" />
        <span>{{ opt.label }}</span>
      </button>
    </div>
  </div>
</template>
