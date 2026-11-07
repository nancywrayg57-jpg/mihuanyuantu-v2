<script setup>
import { computed, onMounted, ref } from 'vue'
import { LogOut, KeyRound, Upload } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import pb from '../lib/pb'
import { useAuthStore } from '../stores/auth'
import { CATEGORY_TABS, uploadLabelFor } from '../lib/roster'
import { zhError } from '../lib/errors'
import ArchiveCard from '../components/ArchiveCard.vue'
import UploadModal from '../components/UploadModal.vue'

const auth = useAuthStore()
const router = useRouter()

const tab = ref('all')
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

const uploadLabel = computed(() => uploadLabelFor(auth.displayName))

const filtered = computed(() => {
  if (tab.value === 'all') return archives.value
  return archives.value.filter((a) => a.category === tab.value)
})

async function load() {
  loading.value = true
  try {
    const list = await pb.collection('archives').getList(1, 200, { sort: '-created' })
    archives.value = list.items
    const mem = await pb.collection('memories').getFullList({ fields: 'id,archive_id' }).catch(() => [])
    const counts = {}
    for (const m of mem) {
      const id = m.archive_id
      counts[id] = (counts[id] || 0) + 1
    }
    memoryCounts.value = counts
  } finally {
    loading.value = false
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
  memoryCounts.value = {
    ...memoryCounts.value,
    [id]: (memoryCounts.value[id] || 0) + 1,
  }
}

function onUploaded(rec) {
  archives.value.unshift(rec)
}

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
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="font-song text-lg sm:text-xl truncate">黄志松家族记忆档案馆</h1>
          <p class="text-mute text-sm truncate">欢迎，{{ auth.displayName }}{{ auth.isAdmin ? '（管理员）' : '' }}</p>
        </div>
        <button
          type="button"
          class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
          @click="pwdOpen = true"
        >
          <KeyRound class="w-5 h-5" /> <span class="hidden sm:inline">修改密码</span>
        </button>
        <button
          type="button"
          class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
          @click="logout"
        >
          <LogOut class="w-5 h-5" /> <span class="hidden sm:inline">退出</span>
        </button>
      </div>
    </header>

    <section class="max-w-6xl mx-auto px-4 py-6">
      <div class="border border-clay bg-parchment p-5 sm:p-7 relative overflow-hidden">
        <h2 class="font-song text-xl sm:text-2xl mb-3 leading-relaxed">
          抟土化金，九秩风霜承勤俭，祥开四世享期颐
        </h2>
        <p class="text-ink/90 max-w-3xl leading-relaxed">
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

    <main class="max-w-6xl mx-auto px-4 py-6">
      <p v-if="loading" class="text-mute">载入珍藏中…</p>
      <p v-else-if="!filtered.length" class="text-mute py-12 text-center">此分类暂无档案，欢迎上传。</p>
      <div
        v-else
        class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
      >
        <ArchiveCard
          v-for="a in filtered"
          :key="a.id"
          :archive="a"
          :memory-count="memoryCounts[a.id] || 0"
          @deleted="onDeleted"
          @updated="onUpdated"
          @memory="onMemory"
        />
      </div>
    </main>

    <button
      type="button"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 min-h-tap px-6 bg-cinnabar text-parchment shadow-lg inline-flex items-center gap-2"
      @click="uploadOpen = true"
    >
      <Upload class="w-5 h-5" /> {{ uploadLabel }}
    </button>

    <UploadModal :open="uploadOpen" :heading="uploadLabel" @close="uploadOpen = false" @uploaded="onUploaded" />

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
