<script setup>
import { computed } from 'vue'
import ArchiveCard from './ArchiveCard.vue'
import { occurredKey } from '../lib/archiveFilters'

const props = defineProps({
  archives: { type: Array, default: () => [] },
  memoryCounts: { type: Object, default: () => ({}) },
})
defineEmits(['deleted', 'updated', 'memory'])

const groups = computed(() => {
  const sorted = [...props.archives].sort((a, b) => {
    const ka = occurredKey(a.occurred_time) || 0
    const kb = occurredKey(b.occurred_time) || 0
    if (ka !== kb) return ka - kb
    return String(a.created || '').localeCompare(String(b.created || ''))
  })
  const map = new Map()
  for (const a of sorted) {
    const key = occurredKey(a.occurred_time)
    const year = key ? String(Math.floor(key / 10000)) : '年代未知'
    if (!map.has(year)) map.set(year, [])
    map.get(year).push(a)
  }
  return [...map.entries()].map(([year, items]) => ({ year, items }))
})
</script>

<template>
  <div class="space-y-10" data-testid="timeline-view">
    <section v-for="g in groups" :key="g.year" class="relative pl-6 border-l-2 border-clay">
      <div
        class="absolute -left-[9px] top-1 w-4 h-4 rounded-full bg-cinnabar border-2 border-parchment"
        aria-hidden="true"
      />
      <h3 class="font-song text-2xl mb-4" data-testid="timeline-year">{{ g.year }}</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <ArchiveCard
          v-for="a in g.items"
          :key="a.id"
          :archive="a"
          :memory-count="memoryCounts[a.id] || 0"
          @deleted="$emit('deleted', $event)"
          @updated="$emit('updated', $event)"
          @memory="$emit('memory', $event)"
        />
      </div>
    </section>
  </div>
</template>
