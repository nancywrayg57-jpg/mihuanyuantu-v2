<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { LogOut, KeyRound, Upload, Users, Search, Download, Type, Maximize2 } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import pb from '../lib/pb'
import { useAuthStore } from '../stores/auth'
import { useUploadQueueStore } from '../stores/uploadQueue'
import { useA11yStore } from '../stores/a11y'
import { CATEGORY_TABS, uploadLabelFor } from '../lib/roster'
import { filterArchives } from '../lib/archiveFilters'
import { downloadFullBackup } from '../lib/exportArchives'
import { zhError } from '../lib/errors'
import ArchiveCard from '../components/ArchiveCard.vue'
import UploadModal from '../components/UploadModal.vue'
import TimelineView from '../components/TimelineView.vue'

const PAGE_SIZE = 10

const auth = useAuthStore()
const queue = useUploadQueueStore()
const a11y = useA11yStore()
const router = useRouter()

const tab = ref('all')
const viewMode = ref('grid') // grid | timeline
const archives = ref([])
const memoryCounts = ref({})
const loading = ref(true)
const uploadOpen = ref(false)
const pwdOpen = ref(false)
const oldPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const pwdMsg = ref('')
const pwdErr = ref('')
const searchQ = ref('')
const page = ref(1)
const notices = ref([])
const exportMsg = ref('')

const uploadLabel = computed(() =>
  uploadLabelFor(auth.displayName, auth.user?.relation || ''),
)

const filtered = computed(() =>
  filterArchives(archives.value, {
    q: searchQ.value,
    category: tab.value,
  }),
)

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))

const paged = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filtered.value.slice(start, start + PAGE_SIZE)
})

watch([tab, searchQ, viewMode], () => {
  page.value = 1
})

watch(filtered, () => {
  if (page.value > totalPages.value) page.value = totalPages.value
})

function goPage(p) {
  page.value = Math.min(totalPages.value, Math.max(1, p))
}

async function load() {
  loading.value = true
  try {
    const list = await pb.collection('archives').getList(1, 500, { sort: '-created' })
    archives.value = list.items
    const mem = await pb.collection('memories').getFullList({ fields: 'id,archive_id' }).catch(() => [])
    const counts = {}
    for (const m of mem) {
      const id = m.archive_id
      counts[id] = (counts[id] || 0) + 1
    }
    memoryCounts.value = counts
    notices.value = await pb
      .collection('notices')
      .getList(1, 5, { sort: '-created', filter: 'pinned = true' })
      .then((r) => r.items)
      .catch(() => [])
  } finally {
    loading.value = false
  }
}

const exporting = ref(false)
async function doExport() {
  if (!auth.isAdmin) {
    exportMsg.value = '仅管理员可导出备份'
    return
  }
  if (exporting.value) return
  exportMsg.value = ''
  exporting.value = true
  try {
    const counts = await downloadFullBackup({
      onProgress: ({ done, total, label }) => {
        exportMsg.value = `正在打包备份 ${done}/${total}${label ? ` · ${label}` : ''}`
      },
    })
    exportMsg.value = `已导出 ZIP：${counts.archives} 条档案、${counts.files} 个文件（含元数据）`
  } catch (e) {
    exportMsg.value = zhError(e, '导出失败')
  } finally {
    exporting.value = false
  }
}

function onDeleted(id) {
  archives.value = archives.value.filter((a) => a.id !== id)
}

function onUpdated(rec) {
  const i = archives.value.findIndex((a) => a.id === rec.id)
  if (i >= 0) archives.value[i] = { ...archives.value[i], ...rec }
}

function onMemory(rec) {
  const id = rec.archive_id
  if (!id) return
  const delta = rec._deleted ? -1 : 1
  memoryCounts.value = {
    ...memoryCounts.value,
    [id]: Math.max(0, (memoryCounts.value[id] || 0) + delta),
  }
}

function onUploaded(rec) {
  if (!rec?.id) return
  if (archives.value.some((a) => a.id === rec.id)) return
  archives.value.unshift(rec)
}

watch(
  () => queue.items.map((i) => `${i.id}:${i.status}:${i.record?.id || ''}`).join('|'),
  () => {
    for (const it of queue.items) {
      if (it.status === 'done' && it.record?.id) onUploaded(it.record)
    }
  },
)

async function savePassword() {
  pwdMsg.value = ''
  pwdErr.value = ''
  try {
    await auth.changePasswordWithOld(oldPwd.value, newPwd.value, confirmPwd.value)
    pwdMsg.value = '密码已更新'
    oldPwd.value = ''
    newPwd.value = ''
    confirmPwd.value = ''
  } catch (e) {
    try {
      if (!oldPwd.value) throw e
      await auth.changePassword(newPwd.value, confirmPwd.value)
      pwdMsg.value = '密码已更新'
      oldPwd.value = ''
      newPwd.value = ''
      confirmPwd.value = ''
    } catch (e2) {
      pwdErr.value = zhError(e2, zhError(e, '修改密码失败'))
    }
  }
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen pb-28">
    <header class="border-b border-clay bg-parchment/90 backdrop-blur sticky top-0 z-40">
      <div class="max-w-6xl mx-auto px-4 py-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="hidden sm:block font-song text-lg sm:text-xl truncate" data-testid="home-brand">
            黄志松人生纪念馆
          </h1>
          <p class="text-ink sm:text-mute text-lg sm:text-sm font-medium sm:font-normal truncate" data-testid="home-welcome">
            欢迎 {{ auth.displayName }}<span class="hidden sm:inline">{{ auth.isAdmin ? '（管理员）' : '' }}</span>
          </p>
        </div>
        <div class="flex items-center gap-2 overflow-x-auto shrink-0">
          <button
            v-if="auth.isAdmin"
            type="button"
            class="min-h-tap px-3 border border-clay inline-flex items-center gap-1 shrink-0"
            @click="router.push('/members')"
          >
            <Users class="w-5 h-5" /> <span class="hidden sm:inline">家族成员管理</span>
          </button>
          <button
            type="button"
            class="min-h-tap px-3 border border-clay inline-flex items-center gap-1 shrink-0"
            data-testid="a11y-font"
            title="放大字号"
            @click="a11y.cycleFont()"
          >
            <Type class="w-5 h-5" /> <span class="hidden sm:inline">字号</span>
          </button>
          <button
            type="button"
            class="min-h-tap px-3 border border-clay inline-flex items-center gap-1 shrink-0"
            data-testid="a11y-tap"
            :title="a11y.largeTap ? '标准按钮' : '大按钮'"
            :aria-pressed="a11y.largeTap"
            @click="a11y.largeTap = !a11y.largeTap"
          >
            <Maximize2 class="w-5 h-5" :class="a11y.largeTap ? 'text-cinnabar' : ''" />
            <span class="sr-only">{{ a11y.largeTap ? '标准按钮' : '大按钮' }}</span>
          </button>
          <button
            v-if="auth.isAdmin"
            type="button"
            class="min-h-tap px-3 border border-clay inline-flex items-center gap-1 shrink-0 disabled:opacity-60"
            data-testid="export-backup"
            :disabled="exporting"
            :title="exporting ? '正在打包…' : '一键导出全部档案与文件（ZIP）'"
            @click="doExport"
          >
            <Download class="w-5 h-5" />
            <span class="hidden sm:inline">{{ exporting ? '打包中…' : '备份导出' }}</span>
          </button>
          <button
            v-if="!auth.isGuest"
            type="button"
            class="min-h-tap px-3 border border-clay inline-flex items-center gap-1 shrink-0"
            data-testid="change-password"
            @click="pwdOpen = true"
          >
            <KeyRound class="w-5 h-5" /> <span class="hidden sm:inline">修改密码</span>
          </button>
          <button
            type="button"
            class="min-h-tap px-3 border border-clay inline-flex items-center gap-1 shrink-0"
            @click="logout"
          >
            <LogOut class="w-5 h-5" /> <span class="hidden sm:inline">退出</span>
          </button>
        </div>
      </div>
      <p v-if="exportMsg" class="max-w-6xl mx-auto px-4 pb-2 text-sm text-celadon">{{ exportMsg }}</p>
    </header>

    <section class="max-w-6xl mx-auto px-4 py-6 space-y-4">
      <div
        v-for="n in notices"
        :key="n.id"
        class="border border-celadon/40 bg-celadon/5 p-4"
        data-testid="notice-banner"
      >
        <h3 class="font-song text-lg">{{ n.title }}</h3>
        <p class="text-ink/90 mt-1 whitespace-pre-wrap">{{ n.body }}</p>
      </div>
      <div class="border border-clay bg-parchment p-5 sm:p-7 relative overflow-hidden" data-testid="home-intro">
        <p class="text-ink/90 max-w-3xl leading-relaxed text-base sm:text-lg">
          本馆由家人共同守护，汇集图片、录像、扫描件、新闻与口述录音，
          使后辈得以回望他的风骨与温度。此处仅为家族内部珍藏空间——每一帧、每一段声音，皆是不可复刻的传承。
        </p>
      </div>
    </section>

    <nav class="sticky top-[65px] z-30 bg-rice/95 backdrop-blur border-y border-clay">
      <div
        class="max-w-6xl mx-auto px-2 flex gap-1 overflow-x-auto"
        data-testid="category-tabs"
      >
        <button
          v-for="t in CATEGORY_TABS"
          :key="t.key"
          type="button"
          class="shrink-0 min-h-tap px-4 border-b-2"
          :class="tab === t.key ? 'border-cinnabar text-cinnabar' : 'border-transparent text-mute'"
          :data-tab="t.key"
          @click="tab = t.key"
        >
          {{ t.label }}
        </button>
      </div>
    </nav>

    <section class="max-w-6xl mx-auto px-4 pt-4 space-y-3" data-testid="search-filters">
      <div class="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
        <label class="relative flex-1">
          <Search class="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
          <input
            v-model="searchQ"
            type="search"
            class="w-full min-h-tap pl-10 pr-3 border border-clay bg-parchment"
            placeholder="搜索标题、关系人、说明、上传者…"
            data-testid="search-input"
          />
        </label>
        <div class="flex border border-clay shrink-0">
          <button
            type="button"
            class="min-h-tap px-3"
            :class="viewMode === 'grid' ? 'bg-cinnabar text-parchment' : 'bg-parchment'"
            data-testid="view-grid"
            @click="viewMode = 'grid'"
          >卡片</button>
          <button
            type="button"
            class="min-h-tap px-3 border-l border-clay"
            :class="viewMode === 'timeline' ? 'bg-cinnabar text-parchment' : 'bg-parchment'"
            data-testid="view-timeline"
            @click="viewMode = 'timeline'"
          >年表</button>
        </div>
      </div>
      <p class="text-mute text-sm" data-testid="result-count">
        共 {{ filtered.length }} 条
        <template v-if="viewMode === 'grid' && filtered.length">
          · 第 {{ page }} / {{ totalPages }} 页（每页 {{ PAGE_SIZE }} 条）
        </template>
      </p>
    </section>

    <main class="max-w-6xl mx-auto px-4 py-6">
      <p v-if="loading" class="text-mute">载入珍藏中…</p>
      <p v-else-if="!filtered.length" class="text-mute py-12 text-center">没有符合条件的档案，欢迎上传或调整筛选。</p>
      <TimelineView
        v-else-if="viewMode === 'timeline'"
        :archives="filtered"
        :memory-counts="memoryCounts"
        @deleted="onDeleted"
        @updated="onUpdated"
        @memory="onMemory"
      />
      <template v-else>
        <div
          class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
          data-testid="archive-grid"
        >
          <ArchiveCard
            v-for="a in paged"
            :key="a.id"
            :archive="a"
            :memory-count="memoryCounts[a.id] || 0"
            @deleted="onDeleted"
            @updated="onUpdated"
            @memory="onMemory"
          />
        </div>
        <div
          v-if="totalPages > 1"
          class="flex items-center justify-center gap-2 pt-6"
          data-testid="list-pagination"
        >
          <button
            type="button"
            class="min-h-tap px-3 border border-clay disabled:opacity-40"
            :disabled="page <= 1"
            data-testid="page-prev"
            @click="goPage(page - 1)"
          >上一页</button>
          <span class="text-mute text-sm">{{ page }} / {{ totalPages }}</span>
          <button
            type="button"
            class="min-h-tap px-3 border border-clay disabled:opacity-40"
            :disabled="page >= totalPages"
            data-testid="page-next"
            @click="goPage(page + 1)"
          >下一页</button>
        </div>
      </template>
    </main>

    <button
      v-if="auth.canUpload"
      type="button"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 min-h-tap px-6 bg-cinnabar text-parchment shadow-lg inline-flex items-center gap-2"
      data-testid="upload-fab"
      @click="uploadOpen = true"
    >
      <Upload class="w-5 h-5" /> {{ uploadLabel }}
    </button>

    <UploadModal
      v-if="auth.canUpload"
      :open="uploadOpen"
      :heading="uploadLabel"
      @close="uploadOpen = false"
    />

    <div
      v-if="pwdOpen"
      class="fixed inset-0 z-50 bg-ink/45 flex items-center justify-center p-4"
      @click.self="pwdOpen = false"
    >
      <div class="bg-parchment border border-clay w-full max-w-md p-6 space-y-4">
        <h3 class="font-song text-xl">修改密码</h3>
        <p class="text-mute text-sm">无需验证码；新密码至少 6 位。</p>
        <input
          v-model="oldPwd"
          type="password"
          class="w-full min-h-tap px-3 border border-clay bg-rice"
          placeholder="当前密码（若系统要求）"
        />
        <input
          v-model="newPwd"
          type="password"
          class="w-full min-h-tap px-3 border border-clay bg-rice"
          placeholder="新密码"
        />
        <input
          v-model="confirmPwd"
          type="password"
          class="w-full min-h-tap px-3 border border-clay bg-rice"
          placeholder="确认新密码"
        />
        <p v-if="pwdErr" class="text-cinnabar">{{ pwdErr }}</p>
        <p v-if="pwdMsg" class="text-celadon">{{ pwdMsg }}</p>
        <div class="flex gap-3">
          <button type="button" class="flex-1 min-h-tap border border-clay" @click="pwdOpen = false">关闭</button>
          <button type="button" class="flex-1 min-h-tap bg-cinnabar text-parchment" @click="savePassword">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>
