<script setup>
import { onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import MiniPlayer from './components/MiniPlayer.vue'
import UploadQueuePanel from './components/UploadQueuePanel.vue'
import { useA11yStore } from './stores/a11y'
import { useAuthStore } from './stores/auth'
import { useLocaleStore } from './stores/locale'

const a11y = useA11yStore()
const auth = useAuthStore()
const locale = useLocaleStore()
const route = useRoute()

onMounted(() => {
  locale.initFromIp()
})

watch(
  () => [auth.isLoggedIn, route.name],
  () => {
    const loggedIn = !!auth.isLoggedIn && route.name !== 'login'
    a11y.apply({ loggedIn })
  },
  { immediate: true },
)

watch(
  () => locale.locale,
  (code) => {
    document.documentElement.lang = code || 'zh'
  },
  { immediate: true },
)
</script>

<template>
  <router-view />
  <MiniPlayer />
  <UploadQueuePanel />
</template>
