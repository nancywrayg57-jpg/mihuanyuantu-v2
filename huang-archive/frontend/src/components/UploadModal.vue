<script setup>
import { computed, ref } from 'vue'
import { X, Image, Video, FileText, Link2, Mic, Boxes } from 'lucide-vue-next'
import pb from '../lib/pb'
import { useAuthStore } from '../stores/auth'
import { zhError } from '../lib/errors'
import { FILE_ACCEPT, UPLOAD_LIMIT_LABELS, validateUploadFiles } from '../lib/uploadLimits'

const props = defineProps({
  open: { type: Boolean, default: false },
  heading: { type: String, default: '上传资料' },
})
const emit = defineEmits(['close', 'uploaded'])

const auth = useAuthStore()

const categories = [
  { key: 'image', label: '图片', icon: Image },
  { key: 'video', label: '视频', icon: Video },
  { key: 'scan', label: '扫描件', icon: FileText },
  { key: 'link', label: '新闻链接', icon: Link2 },
  { key: 'audio', label: '录音', icon: Mic },
  { key: 'other', label: '其他', icon: Boxes },
]

const category = ref('image')
const archiveTitle = ref('')
const occurredTime = ref('')
const relatedPersons = ref('')
const description = ref('')
const externalLink = ref('')
const files = ref([])
const progress = ref(0)
const submitting = ref(false)
const error = ref('')

const isLink = computed(() => category.value === 'link')
const sizeHint = computed(() => {
  if (category.value === 'video') return UPLOAD_LIMIT_LABELS.video
  if (category.value === 'image') return UPLOAD_LIMIT_LABELS.image
  if (category.value === 'scan') return '扫描图片不超过 30MB；PDF 等不超过 100MB'
  if (isLink.value) return '填写可访问的 https 链接即可'
  return UPLOAD_LIMIT_LABELS.other
})

function onFileChange(e) {
  files.value = Array.from(e.target.files || []).slice(0, 9)
  const msg = validateUploadFiles(files.value, category.value)
  error.value = msg || ''
}

async function submit() {
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

  submitting.value = true
  progress.value = 8
  try {
    const form = new FormData()
    form.append('title', archiveTitle.value.trim())
    form.append('category', category.value)
    form.append('occurred_time', occurredTime.value)
    form.append('related_persons', relatedPersons.value.trim())
    form.append('description', description.value.trim())
    form.append('uploader', auth.user.id)
    form.append('uploader_name', auth.displayName)
    form.append('likes_count', '0')
    if (externalLink.value.trim()) form.append('external_link', externalLink.value.trim())
    for (const f of files.value) {
      // Ensure filename is present for MIME sniffing on some mobile browsers
      form.append('media_files', f, f.name || `upload-${Date.now()}`)
    }

    const record = await pb.collection('archives').create(form, {
      requestKey: null,
    })
    progress.value = 100
    emit('uploaded', record)
    reset()
    emit('close')
  } catch (e) {
    console.error('upload failed', e)
    error.value = zhError(e, '上传失败，请检查文件格式与大小后重试')
  } finally {
    submitting.value = false
  }
}

function reset() {
  archiveTitle.value = ''
  occurredTime.value = ''
  relatedPersons.value = ''
  description.value = ''
  externalLink.value = ''
  files.value = []
  progress.value = 0
  error.value = ''
  category.value = 'image'
}

function close() {
  if (submitting.value) return
  emit('close')
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
          <h2 class="font-song text-xl">{{ heading }}</h2>
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
              @click="category = c.key; error = ''; files = []"
            >
              <component :is="c.icon" class="w-6 h-6" />
              <span class="text-sm">{{ c.label }}</span>
            </button>
          </div>

          <label class="block">
            <span class="text-mute">标题</span>
            <input v-model="archiveTitle" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">发生时间</span>
            <input
              v-model="occurredTime"
              type="date"
              class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
            />
          </label>
          <label class="block">
            <span class="text-mute">关系人</span>
            <input
              v-model="relatedPersons"
              class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
              placeholder="如 黄志松、黄纲生"
            />
          </label>
          <label class="block">
            <span class="text-mute">说明（选填）</span>
            <textarea v-model="description" rows="3" class="mt-1 w-full px-3 py-3 border border-clay bg-rice" />
          </label>

          <label v-if="isLink" class="block">
            <span class="text-mute">外部链接</span>
            <input
              v-model="externalLink"
              type="url"
              class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
              placeholder="https://"
            />
          </label>

          <label v-else class="block">
            <span class="text-mute">文件（最多 9 个）</span>
            <input
              type="file"
              multiple
              :accept="FILE_ACCEPT"
              class="mt-1 w-full min-h-tap px-3 py-2 border border-clay bg-rice"
              @change="onFileChange"
            />
            <p class="text-mute text-sm mt-1">{{ sizeHint }}</p>
            <p v-if="files.length" class="text-mute text-sm mt-1">已选 {{ files.length }} 个文件</p>
          </label>

          <div v-if="submitting" class="h-2 bg-clay overflow-hidden">
            <div class="h-full bg-cinnabar transition-all" :style="{ width: progress + '%' }" />
          </div>

          <p v-if="error" class="text-cinnabar" data-testid="upload-error">{{ error }}</p>

          <button
            type="button"
            class="w-full min-h-tap bg-cinnabar text-parchment disabled:opacity-60"
            :disabled="submitting"
            @click="submit"
          >
            {{ submitting ? '上传中…' : '确认上传' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
