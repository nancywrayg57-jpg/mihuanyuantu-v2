<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { useLocaleStore } from '../stores/locale'
import FlagIcon from './FlagIcon.vue'

const locale = useLocaleStore()
const open = ref(false)
const root = ref(null)
const menuStyle = ref({})

function placeMenu() {
  const el = root.value
  if (!el) return
  const r = el.getBoundingClientRect()
  menuStyle.value = {
    position: 'fixed',
    top: `${Math.round(r.bottom + 8)}px`,
    right: `${Math.round(window.innerWidth - r.right)}px`,
    zIndex: 80,
  }
}

async function toggle() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    placeMenu()
  }
}

function pick(code) {
  locale.setOverride(code)
  open.value = false
}

function onDoc(e) {
  if (!root.value) return
  const menu = document.querySelector('[data-testid="lang-switcher-menu"]')
  if (root.value.contains(e.target)) return
  if (menu && menu.contains(e.target)) return
  open.value = false
}

function onResize() {
  if (open.value) placeMenu()
}

onMounted(() => {
  document.addEventListener('click', onDoc)
  window.addEventListener('resize', onResize)
  window.addEventListener('scroll', onResize, true)
})
onUnmounted(() => {
  document.removeEventListener('click', onDoc)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('scroll', onResize, true)
})
</script>

<template>
  <div ref="root" class="relative shrink-0" data-testid="lang-switcher">
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
    <Teleport to="body">
      <div
        v-if="open"
        class="min-w-[11rem] bg-white border border-clay/60 shadow-lg rounded-md py-1"
        data-testid="lang-switcher-menu"
        :style="menuStyle"
      >
        <button
          v-for="opt in locale.LOCALES"
          :key="opt.code"
          type="button"
          class="w-full px-3 py-2.5 flex items-center gap-2.5 text-left hover:bg-rice text-sm"
          :class="opt.code === locale.locale ? 'bg-rice/80' : ''"
          :data-testid="'lang-opt-' + opt.code"
          @click="pick(opt.code)"
        >
          <FlagIcon :code="opt.flag" :size="18" />
          <span>{{ opt.label }}</span>
        </button>
      </div>
    </Teleport>
  </div>
</template>
