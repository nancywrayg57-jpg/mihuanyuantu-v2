<script setup>
import { onMounted } from 'vue'
import MiniPlayer from './components/MiniPlayer.vue'
import UploadQueuePanel from './components/UploadQueuePanel.vue'
import { useA11yStore } from './stores/a11y'

const a11y = useA11yStore()
onMounted(() => a11y.apply())
</script>

<template>
  <router-view />
  <MiniPlayer />
  <UploadQueuePanel />
</template>
