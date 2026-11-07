<script setup>
import { computed, ref, watch } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import ArchiveCard from './ArchiveCard.vue'
import { occurredKey } from '../lib/archiveFilters'

const PAGE_SIZE = 10

const props = defineProps({
  archives: { type: Array, default: () => [] },
  memoryCounts: { type: Object, default: () => ({}) },
})
defineEmits(['deleted', 'updated', 'memory'])

const selectedYear = ref('')
const page = ref(1)

watch(
  () => props.archives,
  () => {
    // If current year vanished after filter, go back to year list
    if (selectedYear.value && !yearGroups.value.some((g) => g.year === selectedYear.value)) {
      selectedYear.value = ''
      page.value = 1
    }
  },
)

const yearGroups = computed(() => {
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
  // Newest years first for overview
  return [...map.entries()]
    .map(([year, items]) => ({ year, items, count: items.length }))
    .sort((a, b) => {
      if (a.year === '年代未知') return 1
      if (b.year === '年代未知') return -1
      return Number(b.year) - Number(a.year)
    })
})

const yearItems = computed(() => {
  const g = yearGroups.value.find((x) => x.year === selectedYear.value)
  return g ? g.items : []
})

const totalPages = computed(() => Math.max(1, Math.ceil(yearItems.value.length / PAGE_SIZE)))

const pagedItems = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return yearItems.value.slice(start, start + PAGE_SIZE)
})

function openYear(year) {
  selectedYear.value = year
  page.value = 1
}

function backToYears() {
  selectedYear.value = ''
  page.value = 1
}

function goPage(p) {
  const next = Math.min(totalPages.value, Math.max(1, p))
  page.value = next
}
</script>

<template>
  <div class="space-y-6" data-testid="timeline-view">
    <template v-if="!selectedYear">
      <p class="text-mute text-sm">点击年份查看该年档案</p>
      <ul class="space-y-2" data-testid="timeline-year-list">
        <li v-for="g in yearGroups" :key="g.year">
          <button
            type="button"
            class="w-full min-h-tap px-4 border border-clay bg-parchment flex items-center justify-between gap-3 text-left hover:border-cinnabar"
            data-testid="timeline-year"
            @click="openYear(g.year)"
          >
            <span class="font-song text-xl">{{ g.year }}</span>
            <span class="text-mute text-sm">{{ g.count }} 条</span>
          </button>
        </li>
      </ul>
      <p v-if="!yearGroups.length" class="text-mute py-8 text-center">暂无年表数据</p>
    </template>

    <template v-else>
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
          data-testid="timeline-back"
          @click="backToYears"
        >
          <ChevronLeft class="w-5 h-5" /> 返回年表
        </button>
        <h3 class="font-song text-2xl" data-testid="timeline-year-title">{{ selectedYear }}</h3>
        <span class="text-mute text-sm">共 {{ yearItems.length }} 条</span>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="timeline-year-grid">
        <ArchiveCard
          v-for="a in pagedItems"
          :key="a.id"
          :archive="a"
          :memory-count="memoryCounts[a.id] || 0"
          @deleted="$emit('deleted', $event)"
          @updated="$emit('updated', $event)"
          @memory="$emit('memory', $event)"
        />
      </div>

      <div
        v-if="totalPages > 1"
        class="flex items-center justify-center gap-2 pt-2"
        data-testid="timeline-pagination"
      >
        <button
          type="button"
          class="min-h-tap px-3 border border-clay disabled:opacity-40"
          :disabled="page <= 1"
          @click="goPage(page - 1)"
        >上一页</button>
        <span class="text-mute text-sm">{{ page }} / {{ totalPages }}</span>
        <button
          type="button"
          class="min-h-tap px-3 border border-clay disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="goPage(page + 1)"
        >下一页</button>
      </div>
    </template>
  </div>
</template>
