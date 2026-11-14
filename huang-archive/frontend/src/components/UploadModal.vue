<script setup>
import { computed, ref } from 'vue'
import { X, Image, Video, FileText, Link2, Mic, Boxes } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { useLocaleStore } from '../stores/locale'
import { useUploadQueueStore } from '../stores/uploadQueue'
import { FILE_ACCEPT, UPLOAD_LIMIT_LABELS, validateUploadFiles } from '../lib/uploadLimits'
import { shouldUseChunked } from '../lib/chunkedUpload'
import { formatDuration, prepareUploadFiles } from '../lib/mediaPrepare'
import { zhError } from '../lib/errors'
import { CATEGORY_I18N_KEYS } from '../lib/i18n'

const props = defineProps({
  open: { type: Boolean, default: false },
  heading: { type: String, default: '' },
})
const emit = defineEmits(['close', 'queued'])

const auth = useAuthStore()
const i18n = useLocaleStore()
const queue = useUploadQueueStore()

const categories = [
  { key: 'image', icon: Image },
  { key: 'video', icon: Video },
  { key: 'scan', icon: FileText },
  { key: 'link', icon: Link2 },
  { key: 'audio', icon: Mic },
  { key: 'other', icon: Boxes },
]
const modalHeading = computed(() => props.heading || i18n.t('uploadHeading'))

const category = ref('image')
const archiveTitle = ref('')
const occurredTime = ref('')
const relatedPersons = ref('')
const description = ref('')
const externalLink = ref('')
const files = ref([])
const previews = ref([]) // { url, name, size }
const coverPreview = ref('')
const coverFile = ref(null)
const durationSec = ref(0)
const prepNotes = ref([])
const preparing = ref(false)
const error = ref('')

const isLink = computed(() => category.value === 'link')
const sizeHint = computed(() => {
  if (category.value === 'video') return UPLOAD_LIMIT_LABELS.video + '；自动提取封面与时长'
  if (category.value === 'image') return UPLOAD_LIMIT_LABELS.image + '；上传前自动压缩'
  if (category.value === 'scan') return '扫描图片自动压缩（≤30MB）；PDF 等不超过 100MB'
  if (isLink.value) return '填写可访问的 https 链接；可选用一张首图/封面（选填）'
  return UPLOAD_LIMIT_LABELS.other + '；超过 1MB 自动分片'
})
const chunkHint = computed(() => {
  if (isLink.value || !files.value.length) return ''
  if (files.value.some((f) => shouldUseChunked(f))) return '已启用分片/断点续传（可关页后续传同名文件）'
  return ''
})

function revokePreviews() {
  for (const p of previews.value) {
    if (p.url) URL.revokeObjectURL(p.url)
  }
  if (coverPreview.value) URL.revokeObjectURL(coverPreview.value)
  previews.value = []
  coverPreview.value = ''
}

async function onFileChange(e) {
  error.value = ''
  prepNotes.value = []
  revokePreviews()
  coverFile.value = null
  durationSec.value = 0
  const raw = Array.from(e.target.files || []).slice(0, 9)
  if (!raw.length) {
    files.value = []
    return
  }
  preparing.value = true
  try {
    const prepared = await prepareUploadFiles(raw, category.value)
    files.value = prepared.files
    coverFile.value = prepared.coverFile
    durationSec.value = prepared.durationSec || 0
    prepNotes.value = prepared.notes || []
    if (prepared.files.length > 1) {
      prepNotes.value = [
        `已选择 ${prepared.files.length} 个文件，将保存为一条档案（可在卡片中左右翻看）`,
        ...prepNotes.value,
      ]
    }
    previews.value = prepared.files.map((f) => ({
      name: f.name,
      size: f.size,
      url: String(f.type).startsWith('image/') ? URL.createObjectURL(f) : '',
    }))
    if (prepared.coverFile) {
      coverPreview.value = URL.createObjectURL(prepared.coverFile)
    }
    const msg = validateUploadFiles(files.value, category.value)
    error.value = msg || ''
  } catch (err) {
    error.value = zhError(err, '文件预处理失败')
    files.value = raw
  } finally {
    preparing.value = false
  }
}

function submit() {
  error.value = ''
  if (!archiveTitle.value.trim() || !occurredTime.value || !relatedPersons.value.trim()) {
    error.value = '请填写标题、发生时间与关系人'
    return
  }
  if (isLink.value) {
    const link = externalLink.value.trim()
    if (!link) {
      error.value = '请填写外部链接'
      return
    }
    if (!/^https?:\/\//i.test(link)) {
      error.value = '链接需以 http:// 或 https:// 开头'
      return
    }
  }
  if (!isLink.value && files.value.length === 0) {
    error.value = '请选择至少一个文件'
    return
  }
  const sizeErr = validateUploadFiles(files.value, category.value)
  if (sizeErr) {
    error.value = sizeErr
    return
  }

  const entry = queue.enqueue({
    title: archiveTitle.value.trim(),
    category: category.value,
    files: isLink.value ? [] : [...files.value],
    coverFile: coverFile.value,
    durationSec: durationSec.value,
    fields: {
      title: archiveTitle.value.trim(),
      category: category.value,
      occurred_time: occurredTime.value,
      related_persons: relatedPersons.value.trim(),
      description: description.value.trim(),
      external_link: externalLink.value.trim(),
      // uploader is set from auth in the upload queue / server hook — do not pass objects
      uploader_name: auth.displayName || '',
      likes_count: '0',
      duration_sec: durationSec.value ? String(durationSec.value) : '',
    },
  })
  emit('queued', entry)
  reset()
  emit('close')
}

function reset() {
  archiveTitle.value = ''
  occurredTime.value = ''
  relatedPersons.value = ''
  description.value = ''
  externalLink.value = ''
  files.value = []
  revokePreviews()
  coverFile.value = null
  durationSec.value = 0
  prepNotes.value = []
  error.value = ''
  category.value = 'image'
}

function close() {
  emit('close')
}

function onCategory(key) {
  category.value = key
  error.value = ''
  files.value = []
  revokePreviews()
  coverFile.value = null
  durationSec.value = 0
  prepNotes.value = []
}

async function onLinkCoverChange(e) {
  error.value = ''
  if (coverPreview.value) URL.revokeObjectURL(coverPreview.value)
  coverPreview.value = ''
  coverFile.value = null
  const raw = e.target.files?.[0]
  if (!raw) return
  preparing.value = true
  try {
    const prepared = await prepareUploadFiles([raw], 'image')
    coverFile.value = prepared.files[0] || raw
    coverPreview.value = URL.createObjectURL(coverFile.value)
    prepNotes.value = prepared.notes?.length ? prepared.notes : ['已选择新闻首图']
  } catch (err) {
    error.value = zhError(err, '首图处理失败')
  } finally {
    preparing.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 bg-ink/45 flex items-end sm:items-center justify-center p-0 sm:p-6"
      @click.self="close"
    >
      <div class="w-full max-w-xl max-h-[92vh] overflow-auto bg-parchment border border-clay">
        <div class="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-clay bg-parchment">
          <h2 class="font-song text-xl">{{ modalHeading }}</h2>
          <button type="button" class="min-h-tap min-w-[48px] grid place-items-center" @click="close">
            <X class="w-6 h-6" />
          </button>
        </div>

        <div class="p-5 space-y-5">
          <div class="grid grid-cols-3 gap-2">
            <button
              v-for="c in categories"
              :key="c.key"
              type="button"
              class="min-h-tap border px-2 py-3 flex flex-col items-center gap-1"
              :class="category === c.key ? 'border-cinnabar bg-cinnabar/5 text-cinnabar' : 'border-clay'"
              @click="onCategory(c.key)"
            >
              <component :is="c.icon" class="w-6 h-6" />
              <span class="text-sm">{{ i18n.t(CATEGORY_I18N_KEYS[c.key]) }}</span>
            </button>
          </div>

          <label class="block">
            <span class="text-mute">{{ i18n.t('title') }}</span>
            <input v-model="archiveTitle" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">{{ i18n.t('occurredTime') }}</span>
            <input
              v-model="occurredTime"
              type="date"
              class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
            />
          </label>
          <label class="block">
            <span class="text-mute">{{ i18n.t('related') }}</span>
            <input
              v-model="relatedPersons"
              class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
              placeholder="如 黄志松、黄纲生"
            />
          </label>
          <label class="block">
            <span class="text-mute">{{ i18n.t('descriptionOptional') }}</span>
            <textarea v-model="description" rows="3" class="mt-1 w-full px-3 py-3 border border-clay bg-rice" />
          </label>

          <label v-if="isLink" class="block">
            <span class="text-mute">{{ i18n.t('newsLink') }}</span>
            <input
              v-model="externalLink"
              type="url"
              class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
              placeholder="https://"
              data-testid="upload-external-link"
            />
          </label>

          <label v-if="isLink" class="block">
            <span class="text-mute">{{ i18n.t('coverOptional') }}</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/*"
              class="mt-1 w-full min-h-tap px-3 py-2 border border-clay bg-rice"
              data-testid="upload-link-cover"
              @change="onLinkCoverChange"
            />
            <p class="text-mute text-sm mt-1">{{ sizeHint }}</p>
          </label>

          <label v-else class="block">
            <span class="text-mute">文件（最多 9 个）</span>
            <input
              type="file"
              multiple
              :accept="FILE_ACCEPT"
              class="mt-1 w-full min-h-tap px-3 py-2 border border-clay bg-rice"
              data-testid="upload-files"
              @change="onFileChange"
            />
            <p class="text-mute text-sm mt-1">{{ sizeHint }}</p>
            <p v-if="preparing" class="text-celadon text-sm mt-1">正在压缩/提取封面…</p>
            <p v-if="chunkHint" class="text-celadon text-sm mt-1">{{ chunkHint }}</p>
            <ul v-if="prepNotes.length" class="text-mute text-sm mt-1 space-y-0.5" data-testid="prep-notes">
              <li v-for="(n, i) in prepNotes" :key="i">{{ n }}</li>
            </ul>
          </label>

          <div
            v-if="coverPreview || previews.length"
            class="grid grid-cols-3 gap-2"
            data-testid="upload-previews"
          >
            <div v-if="coverPreview" class="relative aspect-square border border-clay bg-rice overflow-hidden">
              <img :src="coverPreview" alt="封面" class="w-full h-full object-cover" />
              <span class="absolute bottom-1 left-1 text-xs bg-ink/70 text-parchment px-1">
                封面{{ durationSec ? ` · ${formatDuration(durationSec)}` : '' }}
              </span>
            </div>
            <div
              v-for="(p, i) in previews"
              :key="i"
              class="relative aspect-square border border-clay bg-rice overflow-hidden flex items-center justify-center text-mute text-xs p-1"
            >
              <img v-if="p.url" :src="p.url" :alt="p.name" class="w-full h-full object-cover" />
              <span v-else class="text-center break-all">{{ p.name }}</span>
            </div>
          </div>

          <p v-if="error" class="text-cinnabar" data-testid="upload-error">{{ error }}</p>

          <button
            type="button"
            class="w-full min-h-tap bg-cinnabar text-parchment disabled:opacity-60"
            data-testid="upload-submit"
            :disabled="preparing"
            @click="submit"
          >
            加入上传队列
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
