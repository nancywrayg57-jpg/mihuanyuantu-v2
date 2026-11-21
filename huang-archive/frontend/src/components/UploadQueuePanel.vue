<script setup>
import { X } from 'lucide-vue-next'
import { useUploadQueueStore } from '../stores/uploadQueue'

const queue = useUploadQueueStore()

const statusLabel = {
  queued: '排队中',
  uploading: '上传中',
  done: '完成',
  error: '失败',
  cancelled: '已取消',
}
</script>

<template>
  <div
    v-if="queue.visible.length"
    class="fixed z-[65] left-3 right-3 sm:left-auto sm:right-3 sm:w-96 bottom-3 sm:bottom-24 bg-parchment border border-clay shadow-lg"
    data-testid="upload-queue"
  >
    <div class="flex items-center justify-between px-3 py-2 border-b border-clay">
      <h3 class="font-song">上传队列（{{ queue.pendingCount }}）</h3>
      <button type="button" class="text-sm text-mute" @click="queue.clearFinished()">清除已完成</button>
    </div>
    <ul class="max-h-64 overflow-auto divide-y divide-clay/60">
      <li v-for="it in queue.visible" :key="it.id" class="px-3 py-2 text-sm">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="truncate font-medium">{{ it.title }}</div>
            <div class="text-mute">{{ statusLabel[it.status] || it.status }} · {{ it.category }}</div>
            <p v-if="it.error" class="text-cinnabar mt-1">{{ it.error }}</p>
          </div>
          <button type="button" class="p-1" @click="queue.dismiss(it.id)">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-if="it.status === 'uploading' || it.status === 'queued'" class="mt-2 h-1.5 bg-clay overflow-hidden">
          <div class="h-full bg-cinnabar transition-all" :style="{ width: (it.progress || 0) + '%' }" />
        </div>
      </li>
    </ul>
  </div>
</template>
