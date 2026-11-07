<script setup>
import MiniPlayer from './components/MiniPlayer.vue'
import UploadQueuePanel from './components/UploadQueuePanel.vue'
</script>

<template>
  <router-view />
  <MiniPlayer />
  <UploadQueuePanel />
</template>
