<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import MiniPlayer from './components/MiniPlayer.vue'
import UploadQueuePanel from './components/UploadQueuePanel.vue'
import { useA11yStore } from './stores/a11y'
import { useAuthStore } from './stores/auth'

const a11y = useA11yStore()
const auth = useAuthStore()
const route = useRoute()

watch(
  () => [auth.isLoggedIn, route.name],
  () => {
    const loggedIn = !!auth.isLoggedIn && route.name !== 'login'
    a11y.apply({ loggedIn })
  },
  { immediate: true },
)
</script>

<template>
  <router-view />
  <MiniPlayer />
  <UploadQueuePanel />
</template>
