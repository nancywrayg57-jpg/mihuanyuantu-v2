<script setup>
import { computed, ref, watch } from 'vue'
import { Heart, MessageCircle, Trash2, ExternalLink, Pencil, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import pb from '../lib/pb'
import { useAuthStore } from '../stores/auth'
import { zhError } from '../lib/errors'
import VoiceRecorder from './VoiceRecorder.vue'
import EditArchiveModal from './EditArchiveModal.vue'
import VideoPlayer from './VideoPlayer.vue'
import { coverOrThumbUrl, formatDuration, thumbUrl } from '../lib/mediaPrepare'

const props = defineProps({
  archive: { type: Object, required: true },
  memoryCount: { type: Number, default: 0 },
})
const emit = defineEmits(['deleted', 'updated', 'memory'])

const auth = useAuthStore()
const liked = ref(false)
const likeId = ref('')
const likes = ref(props.archive.likes_count || 0)
const showMemories = ref(false)
const memories = ref([])
const textContent = ref('')
const busy = ref(false)
const confirmDelete = ref(false)
const editOpen = ref(false)
const actionError = ref('')

watch(
  () => props.archive.likes_count,
  (v) => {
    likes.value = v || 0
  },
)

const uploaderId = computed(() => {
  const u = props.archive.uploader
  return typeof u === 'string' ? u : u?.id || ''
})

const canEdit = computed(
  () => auth.isAdmin || (!!auth.user?.id && uploaderId.value === auth.user.id),
)

const files = computed(() => {
  const raw = props.archive.media_files
  return Array.isArray(raw) ? raw.filter(Boolean) : raw ? [raw] : []
})
const slide = ref(0)
const lightboxOpen = ref(false)
const lightboxIndex = ref(0)
watch(
  () => props.archive.id,
  () => {
    slide.value = 0
    lightboxOpen.value = false
    lightboxIndex.value = 0
  },
)
watch(files, (list) => {
  if (slide.value >= list.length) slide.value = Math.max(0, list.length - 1)
  if (lightboxIndex.value >= list.length) lightboxIndex.value = Math.max(0, list.length - 1)
})

function openLightbox(index = slide.value) {
  const i = Math.max(0, Math.min(Number(index) || 0, Math.max(0, imageUrls.value.length - 1)))
  lightboxIndex.value = i
  slide.value = i
  lightboxOpen.value = true
}
function closeLightbox() {
  lightboxOpen.value = false
}
function lightboxPrev() {
  if (!imageUrls.value.length) return
  lightboxIndex.value = (lightboxIndex.value - 1 + imageUrls.value.length) % imageUrls.value.length
  slide.value = lightboxIndex.value
}
function lightboxNext() {
  if (!imageUrls.value.length) return
  lightboxIndex.value = (lightboxIndex.value + 1) % imageUrls.value.length
  slide.value = lightboxIndex.value
}
const firstFile = computed(() => files.value[0] || '')
const activeFile = computed(() => files.value[slide.value] || firstFile.value || '')
const fileUrl = computed(() =>
  activeFile.value ? pb.files.getURL(props.archive, activeFile.value) : '',
)
const listCoverUrl = computed(() => coverOrThumbUrl(pb, props.archive))
const isPdf = computed(() => String(firstFile.value).toLowerCase().endsWith('.pdf'))
const isVideo = computed(() => props.archive.category === 'video')
const isAudio = computed(() => props.archive.category === 'audio')
const isImageLike = computed(() => ['image', 'scan'].includes(props.archive.category))
const isLink = computed(() => props.archive.category === 'link')
const imageUrls = computed(() =>
  files.value.map((name) => ({
    name,
    url: thumbUrl(pb, props.archive, name, '600x0') || pb.files.getURL(props.archive, name),
    full: pb.files.getURL(props.archive, name),
  })),
)
const multiCount = computed(() => (isImageLike.value ? files.value.length : 0))
const durationLabel = computed(() => {
  const d = Number(props.archive.duration_sec || 0)
  return d > 0 ? formatDuration(d) : ''
})
const showListCover = computed(
  () => isImageLike.value || (isVideo.value && !!listCoverUrl.value) || (isAudio.value && !!listCoverUrl.value),
)

function prevSlide() {
  if (!files.value.length) return
  slide.value = (slide.value - 1 + files.value.length) % files.value.length
}
function nextSlide() {
  if (!files.value.length) return
  slide.value = (slide.value + 1) % files.value.length
}

async function checkLiked() {
  try {
    const list = await pb.collection('archive_likes').getList(1, 1, {
      filter: `archive_id="${props.archive.id}" && user_id="${auth.user.id}"`,
    })
    if (list.items[0]) {
      liked.value = true
      likeId.value = list.items[0].id
    }
  } catch (_) {}
}

checkLiked()

async function toggleLike() {
  if (busy.value) return
  busy.value = true
  actionError.value = ''
  try {
    if (liked.value && likeId.value) {
      await pb.collection('archive_likes').delete(likeId.value)
      liked.value = false
      likeId.value = ''
      likes.value = Math.max(0, likes.value - 1)
    } else {
      const rec = await pb.collection('archive_likes').create({
        archive_id: props.archive.id,
        user_id: auth.user.id,
      })
      liked.value = true
      likeId.value = rec.id
      likes.value += 1
    }
    // likes_count is maintained by PocketBase hook — do not PATCH archives here
    emit('updated', { ...props.archive, likes_count: likes.value })
  } catch (e) {
    actionError.value = zhError(e, '点赞失败，请稍后重试')
  } finally {
    busy.value = false
  }
}

async function loadMemories() {
  actionError.value = ''
  try {
    showMemories.value = true
    const list = await pb.collection('memories').getList(1, 50, {
      filter: `archive_id="${props.archive.id}"`,
      sort: '-created',
    })
    memories.value = list.items
  } catch (e) {
    actionError.value = zhError(e, '加载留言失败')
  }
}

async function postText() {
  if (!textContent.value.trim()) return
  actionError.value = ''
  try {
    const rec = await pb.collection('memories').create({
      archive_id: props.archive.id,
      author: auth.user.id,
      author_name: auth.displayName,
      content_type: 'text',
      text_content: textContent.value.trim(),
    })
    textContent.value = ''
    memories.value.unshift(rec)
    emit('memory', rec)
  } catch (e) {
    actionError.value = zhError(e, '发布留言失败')
  }
}

async function postVoice({ blob, duration }) {
  actionError.value = ''
  try {
    const form = new FormData()
    form.append('archive_id', props.archive.id)
    form.append('author', auth.user.id)
    form.append('author_name', auth.displayName)
    form.append('content_type', 'voice')
    form.append('voice_duration', String(duration || 0))
    const ext = blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'
    form.append('voice_file', blob, `voice.${ext}`)
    const rec = await pb.collection('memories').create(form)
    memories.value.unshift(rec)
    emit('memory', rec)
  } catch (e) {
    actionError.value = zhError(e, '发布语音失败')
  }
}

async function doDelete() {
  actionError.value = ''
  try {
    await pb.collection('archives').delete(props.archive.id)
    confirmDelete.value = false
    emit('deleted', props.archive.id)
  } catch (e) {
    actionError.value = zhError(e, '删除失败')
    confirmDelete.value = false
  }
}

function askDelete() {
  confirmDelete.value = true
}

function onEdited(rec) {
  emit('updated', rec)
}

function voiceUrl(m) {
  const name = Array.isArray(m.voice_file) ? m.voice_file[0] : m.voice_file
  return name ? pb.files.getURL(m, name) : ''
}

/** Admin: any; member/guest: own comments only. */
function canDeleteMemory(m) {
  if (!auth.user?.id) return false
  if (auth.isAdmin) return true
  const authorId = typeof m.author === 'string' ? m.author : m.author?.id
  return !!authorId && authorId === auth.user.id
}

async function deleteMemory(m) {
  if (!canDeleteMemory(m) || busy.value) return
  if (!window.confirm('确认删除这条追忆留言？')) return
  busy.value = true
  actionError.value = ''
  try {
    await pb.collection('memories').delete(m.id)
    memories.value = memories.value.filter((x) => x.id !== m.id)
    emit('memory', { ...m, _deleted: true, archive_id: m.archive_id || props.archive.id })
  } catch (e) {
    actionError.value = zhError(e, '删除留言失败')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <article class="bg-parchment border border-clay overflow-hidden flex flex-col">
    <div class="aspect-[4/3] bg-rice relative overflow-hidden">
      <template v-if="isLink">
        <a
          :href="archive.external_link"
          target="_blank"
          rel="noopener"
          class="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center hover:bg-clay/20"
        >
          <ExternalLink class="w-10 h-10 text-celadon" />
          <span class="font-song text-lg">新闻剪报</span>
          <span class="text-mute text-sm break-all line-clamp-3">{{ archive.external_link }}</span>
        </a>
      </template>
      <template v-else-if="isPdf">
        <a :href="fileUrl" target="_blank" class="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#f3ebe0]">
          <div class="w-20 h-28 border-2 border-cinnabar/40 bg-parchment shadow-sm flex items-center justify-center font-song text-cinnabar">
            PDF
          </div>
          <span class="text-mute">复古卷宗封面</span>
        </a>
      </template>
      <template v-else-if="isVideo">
        <div class="absolute inset-0">
          <VideoPlayer :archive="archive" />
          <span
            v-if="durationLabel"
            class="absolute bottom-2 left-2 z-10 text-xs bg-ink/70 text-parchment px-1.5 py-0.5"
            data-testid="video-duration"
          >{{ durationLabel }}</span>
        </div>
      </template>
      <template v-else-if="isAudio && fileUrl">
        <div class="absolute inset-0 flex flex-col justify-end p-4 gap-3">
          <img
            v-if="listCoverUrl"
            :src="listCoverUrl"
            alt=""
            class="absolute inset-0 w-full h-full object-cover opacity-40"
          />
          <div class="vinyl-bar h-16 rounded-sm opacity-90 relative" />
          <audio :src="fileUrl" controls class="w-full relative" />
          <span
            v-if="durationLabel"
            class="absolute top-2 right-2 text-xs bg-ink/70 text-parchment px-1.5 py-0.5"
          >{{ durationLabel }}</span>
        </div>
      </template>
      <template v-else-if="isImageLike && imageUrls.length">
        <button
          type="button"
          class="block w-full h-full p-0 border-0 cursor-zoom-in"
          data-testid="archive-thumb-link"
          @click="openLightbox(slide)"
        >
          <img
            :src="imageUrls[slide]?.url || listCoverUrl || fileUrl"
            :alt="`${archive.title}（${slide + 1}/${imageUrls.length}）`"
            class="w-full h-full object-cover pointer-events-none"
            loading="lazy"
            data-testid="archive-thumb"
          />
        </button>
        <div
          v-if="multiCount > 1"
          class="absolute top-2 right-2 z-10 text-xs bg-ink/75 text-parchment px-2 py-0.5"
          data-testid="archive-multi-badge"
        >
          {{ slide + 1 }}/{{ multiCount }} 张
        </div>
        <div v-if="multiCount > 1" class="absolute inset-y-0 left-0 right-0 z-10 flex items-center justify-between px-1 pointer-events-none">
          <button
            type="button"
            class="pointer-events-auto min-h-tap min-w-[44px] grid place-items-center bg-ink/45 text-parchment"
            data-testid="archive-prev"
            aria-label="上一张"
            @click.stop="prevSlide"
          >
            <ChevronLeft class="w-6 h-6" />
          </button>
          <button
            type="button"
            class="pointer-events-auto min-h-tap min-w-[44px] grid place-items-center bg-ink/45 text-parchment"
            data-testid="archive-next"
            aria-label="下一张"
            @click.stop="nextSlide"
          >
            <ChevronRight class="w-6 h-6" />
          </button>
        </div>
        <div
          v-if="multiCount > 1"
          class="absolute bottom-2 left-2 right-2 z-10 flex gap-1 overflow-x-auto pointer-events-auto"
          data-testid="archive-thumbs"
        >
          <button
            v-for="(img, i) in imageUrls"
            :key="img.name"
            type="button"
            class="shrink-0 w-10 h-10 border-2 overflow-hidden"
            :class="i === slide ? 'border-cinnabar' : 'border-parchment/80'"
            @click.stop="slide = i"
          >
            <img :src="img.url" :alt="`缩略图 ${i + 1}`" class="w-full h-full object-cover" />
          </button>
        </div>
      </template>
      <template v-else>
        <div class="absolute inset-0 grid place-items-center text-mute">暂无预览</div>
      </template>
    </div>

    <div class="p-4 flex-1 flex flex-col gap-3">
      <h3 class="font-song text-xl leading-snug">{{ archive.title }}</h3>
      <dl class="text-sm text-mute space-y-1">
        <div>时间：{{ archive.occurred_time }}</div>
        <div>关系人：{{ archive.related_persons }}</div>
        <div>上传：{{ archive.uploader_name || '—' }}</div>
      </dl>
      <p v-if="archive.description" class="text-ink/90">{{ archive.description }}</p>
      <p v-if="actionError" class="text-cinnabar text-sm">{{ actionError }}</p>

      <div class="mt-auto flex flex-wrap items-center gap-2 pt-2">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 min-h-tap px-3 border border-clay"
          :class="liked ? 'text-cinnabar' : ''"
          @click="toggleLike"
        >
          <Heart class="w-5 h-5" :fill="liked ? 'currentColor' : 'none'" />
          {{ likes }}
        </button>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 min-h-tap px-3 border border-clay"
          @click="loadMemories"
        >
          <MessageCircle class="w-5 h-5" />
          {{ memoryCount }}
        </button>
        <button
          v-if="canEdit"
          type="button"
          data-testid="edit-archive"
          class="inline-flex items-center gap-1.5 min-h-tap px-3 border border-celadon text-celadon"
          @click="editOpen = true"
        >
          <Pencil class="w-5 h-5" /> 编辑
        </button>
        <button
          v-if="auth.isAdmin"
          type="button"
          data-testid="delete-archive"
          class="ml-auto inline-flex items-center gap-1.5 min-h-tap px-3 border border-cinnabar text-cinnabar"
          @click="askDelete"
        >
          <Trash2 class="w-5 h-5" /> 删除
        </button>
      </div>

      <div v-if="showMemories" class="border-t border-clay pt-3 space-y-3">
        <div class="space-y-2 max-h-48 overflow-auto">
          <div v-for="m in memories" :key="m.id" class="text-sm border border-clay/70 p-2 bg-rice">
            <div class="flex items-start justify-between gap-2 text-mute mb-1">
              <span>{{ m.author_name }} · {{ m.content_type === 'voice' ? '语音' : '文字' }}</span>
              <button
                v-if="canDeleteMemory(m)"
                type="button"
                class="shrink-0 text-cinnabar underline underline-offset-2"
                data-testid="delete-memory"
                @click="deleteMemory(m)"
              >
                删除
              </button>
            </div>
            <p v-if="m.content_type === 'text'">{{ m.text_content }}</p>
            <audio v-else-if="voiceUrl(m)" :src="voiceUrl(m)" controls class="w-full" />
          </div>
          <p v-if="!memories.length" class="text-mute">暂无追忆，来写一句吧</p>
        </div>
        <textarea
          v-model="textContent"
          rows="2"
          class="w-full px-3 py-2 border border-clay bg-rice"
          placeholder="写下对这段记忆的追忆…"
        />
        <button type="button" class="min-h-tap px-4 bg-celadon text-parchment" @click="postText">
          发布文字追忆
        </button>
        <VoiceRecorder @publish="postVoice" />
      </div>
    </div>

    <EditArchiveModal :open="editOpen" :archive="archive" @close="editOpen = false" @saved="onEdited" />

    <div
      v-if="confirmDelete"
      class="fixed inset-0 z-[60] bg-ink/50 flex items-center justify-center p-4"
      data-testid="delete-confirm-dialog"
    >
      <div class="bg-parchment border border-clay max-w-md w-full p-6 space-y-4">
        <p class="font-song text-lg leading-relaxed">
          确认要永久删除这条珍贵的家族记忆吗？此操作不可恢复。
        </p>
        <div class="flex gap-3">
          <button type="button" class="flex-1 min-h-tap border border-clay" @click="confirmDelete = false">
            取消
          </button>
          <button
            type="button"
            data-testid="confirm-delete"
            class="flex-1 min-h-tap bg-cinnabar text-parchment"
            @click="doDelete"
          >
            确认删除
          </button>
        </div>
      </div>
    </div>

    <!-- In-app lightbox: opens at the clicked slide; prev/next flip without off-by-one jump -->
    <div
      v-if="lightboxOpen && imageUrls.length"
      class="fixed inset-0 z-[70] bg-ink/90 flex flex-col"
      data-testid="image-lightbox"
      @click.self="closeLightbox"
    >
      <div class="flex items-center justify-between px-4 py-3 text-parchment">
        <span data-testid="lightbox-index">{{ lightboxIndex + 1 }} / {{ imageUrls.length }}</span>
        <button
          type="button"
          class="min-h-tap px-4 border border-parchment/40"
          data-testid="lightbox-close"
          @click="closeLightbox"
        >关闭</button>
      </div>
      <div class="flex-1 relative flex items-center justify-center px-12 pb-6">
        <button
          v-if="imageUrls.length > 1"
          type="button"
          class="absolute left-2 z-10 min-h-tap min-w-[48px] grid place-items-center bg-parchment/15 text-parchment"
          data-testid="lightbox-prev"
          aria-label="上一张"
          @click.stop="lightboxPrev"
        >
          <ChevronLeft class="w-8 h-8" />
        </button>
        <img
          :src="imageUrls[lightboxIndex]?.full || imageUrls[lightboxIndex]?.url"
          :alt="`${archive.title} 大图 ${lightboxIndex + 1}`"
          class="max-h-full max-w-full object-contain"
          data-testid="lightbox-image"
          @click.stop
        />
        <button
          v-if="imageUrls.length > 1"
          type="button"
          class="absolute right-2 z-10 min-h-tap min-w-[48px] grid place-items-center bg-parchment/15 text-parchment"
          data-testid="lightbox-next"
          aria-label="下一张"
          @click.stop="lightboxNext"
        >
          <ChevronRight class="w-8 h-8" />
        </button>
      </div>
    </div>
  </article>
</template>
