<script setup>
import { computed, ref, watch } from 'vue'
import { X, Crop, Star } from 'lucide-vue-next'
import pb from '../lib/pb'
import { zhError } from '../lib/errors'
import { normalizeUploadFile, safeUploadFilename } from '../lib/chunkedUpload'
import { prepareUploadFiles, thumbUrl } from '../lib/mediaPrepare'
import { useLocaleStore } from '../stores/locale'
import CropStage from './CropStage.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  archive: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])
const i18n = useLocaleStore()

const title = ref('')
const occurredTime = ref('')
const relatedPersons = ref('')
const description = ref('')
const saving = ref(false)
const error = ref('')
const mediaNames = ref([])
const coverName = ref('')
const pendingFiles = ref([])
const pendingPreviews = ref([])
const removeCover = ref(false)
const newCoverFile = ref(null)
const newCoverPreview = ref('')
const cropOpen = ref(false)
const cropSrc = ref('')
const cropTarget = ref(null)
const cropCanvas = ref(null)

const isLink = computed(() => props.archive?.category === 'link')
const isImageLike = computed(() => ['image', 'scan'].includes(props.archive?.category))

watch(
  () => [props.open, props.archive],
  () => {
    if (!props.open || !props.archive) return
    title.value = props.archive.title || ''
    occurredTime.value = toDateInput(props.archive.occurred_time)
    relatedPersons.value = props.archive.related_persons || ''
    description.value = props.archive.description || ''
    const mf = props.archive.media_files
    mediaNames.value = Array.isArray(mf) ? [...mf] : mf ? [mf] : []
    const cf = props.archive.cover_file
    coverName.value = Array.isArray(cf) ? cf[0] || '' : cf || ''
    error.value = ''
    removeCover.value = false
    clearPending()
  },
  { immediate: true },
)

function clearPending() {
  for (const p of pendingPreviews.value) if (p) URL.revokeObjectURL(p)
  if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
  pendingFiles.value = []
  pendingPreviews.value = []
  newCoverFile.value = null
  newCoverPreview.value = ''
}

function toDateInput(value) {
  const s = String(value || '').trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s
  return ''
}

function existingUrl(name) {
  if (!props.archive || !name) return ''
  return thumbUrl(pb, props.archive, name, '600x0') || pb.files.getURL(props.archive, name)
}

function setCoverExisting(name) {
  coverName.value = name
  removeCover.value = false
  if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
  newCoverFile.value = null
  newCoverPreview.value = ''
}

async function onAddFiles(e) {
  const raw = Array.from(e.target.files || []).slice(0, Math.max(0, 9 - mediaNames.value.length))
  if (!raw.length) return
  try {
    const prepared = await prepareUploadFiles(raw, props.archive.category === 'scan' ? 'scan' : 'image')
    for (const f of prepared.files) {
      pendingFiles.value.push(f)
      pendingPreviews.value.push(URL.createObjectURL(f))
    }
    if (
      mediaNames.value.length + pendingFiles.value.length === 1 &&
      !coverName.value &&
      !newCoverFile.value
    ) {
      newCoverFile.value = pendingFiles.value[0]
      newCoverPreview.value = URL.createObjectURL(pendingFiles.value[0])
      removeCover.value = false
    }
  } catch (err) {
    error.value = zhError(err, '图片处理失败')
  }
  e.target.value = ''
}

async function onCoverPick(e) {
  const raw = e.target.files?.[0]
  if (!raw) return
  try {
    const prepared = await prepareUploadFiles([raw], 'image')
    if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
    newCoverFile.value = prepared.files[0] || raw
    newCoverPreview.value = URL.createObjectURL(newCoverFile.value)
    removeCover.value = false
    coverName.value = ''
  } catch (err) {
    error.value = zhError(err, '封面处理失败')
  }
  e.target.value = ''
}

function openCropForCover() {
  const src = newCoverPreview.value || (coverName.value ? existingUrl(coverName.value) : '')
  if (!src) return
  cropSrc.value = src
  cropTarget.value = 'cover'
  cropOpen.value = true
}

function openCropForPending(i) {
  cropSrc.value = pendingPreviews.value[i]
  cropTarget.value = i
  cropOpen.value = true
}

function clearCover() {
  removeCover.value = true
  coverName.value = ''
  if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
  newCoverPreview.value = ''
  newCoverFile.value = null
}

async function applyCrop() {
  const canvas = cropCanvas.value
  if (!canvas) return
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92))
  if (!blob) return
  const file = new File([blob], 'crop.jpg', { type: 'image/jpeg' })
  if (cropTarget.value === 'cover') {
    if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
    newCoverFile.value = file
    newCoverPreview.value = URL.createObjectURL(file)
    coverName.value = ''
    removeCover.value = false
  } else if (typeof cropTarget.value === 'number') {
    const i = cropTarget.value
    if (pendingPreviews.value[i]) URL.revokeObjectURL(pendingPreviews.value[i])
    pendingFiles.value[i] = file
    pendingPreviews.value[i] = URL.createObjectURL(file)
  }
  cropOpen.value = false
}

async function save() {
  error.value = ''
  if (!title.value.trim() || !occurredTime.value || !relatedPersons.value.trim()) {
    error.value = '请填写标题、发生时间与关系人'
    return
  }
  saving.value = true
  try {
    const form = new FormData()
    form.append('title', title.value.trim())
    form.append('occurred_time', occurredTime.value)
    form.append('related_persons', relatedPersons.value.trim())
    form.append('description', description.value.trim())

    if (isImageLike.value || isLink.value) {
      if (newCoverFile.value) {
        const cf = normalizeUploadFile(newCoverFile.value)
        form.append('cover_file', cf, safeUploadFilename(cf, 'jpg') || 'cover.jpg')
      } else if (removeCover.value) {
        form.append('cover_file', '')
      } else if (
        pendingFiles.value.length === 1 &&
        mediaNames.value.length === 0 &&
        !coverName.value
      ) {
        const cf = normalizeUploadFile(pendingFiles.value[0])
        form.append('cover_file', cf, 'cover.jpg')
      }
    }

    for (const f of pendingFiles.value) {
      const nf = normalizeUploadFile(f)
      form.append('media_files+', nf, nf.name || `img-${Date.now()}.jpg`)
    }

    const updated = await pb.collection('archives').update(props.archive.id, form)
    emit('saved', updated)
    emit('close')
  } catch (e) {
    error.value = zhError(e, '保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

function close() {
  clearPending()
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && archive"
      class="fixed inset-0 z-50 bg-ink/45 flex items-end sm:items-center justify-center p-0 sm:p-6"
      data-testid="edit-archive-modal"
      @click.self="close"
    >
      <div class="w-full max-w-xl max-h-[92vh] overflow-auto bg-parchment border border-clay">
        <div class="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-clay bg-parchment z-10">
          <h2 class="font-song text-xl">{{ i18n.t('editArchive') }}</h2>
          <button type="button" class="min-h-tap min-w-[48px] grid place-items-center" @click="close">
            <X class="w-6 h-6" />
          </button>
        </div>
        <div class="p-5 space-y-4">
          <label class="block">
            <span class="text-mute">标题</span>
            <input v-model="title" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">发生时间</span>
            <input v-model="occurredTime" type="date" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">关系人</span>
            <input v-model="relatedPersons" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">说明（选填）</span>
            <textarea v-model="description" rows="3" class="mt-1 w-full px-3 py-3 border border-clay bg-rice" />
          </label>

          <div v-if="isImageLike || isLink" class="space-y-3" data-testid="edit-media-section">
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <h3 class="font-song text-lg">图片 / 封面</h3>
              <label
                v-if="isImageLike"
                class="min-h-tap px-3 border border-clay bg-rice inline-flex items-center cursor-pointer text-sm"
              >
                添加图片
                <input type="file" accept="image/*" multiple class="hidden" data-testid="edit-add-images" @change="onAddFiles" />
              </label>
            </div>

            <div class="grid grid-cols-3 gap-2">
              <div
                v-for="name in mediaNames"
                :key="name"
                class="relative aspect-square border border-clay bg-rice overflow-hidden"
              >
                <img :src="existingUrl(name)" :alt="name" class="w-full h-full object-cover" />
                <button
                  type="button"
                  class="absolute top-1 right-1 text-xs px-1.5 py-0.5 text-parchment inline-flex items-center gap-0.5"
                  :class="coverName === name && !newCoverFile ? 'bg-cinnabar' : 'bg-ink/75'"
                  data-testid="set-cover-existing"
                  @click="setCoverExisting(name)"
                >
                  <Star class="w-3 h-3" /> 封面
                </button>
              </div>
              <div
                v-for="(prev, i) in pendingPreviews"
                :key="'p' + i"
                class="relative aspect-square border border-celadon bg-rice overflow-hidden"
              >
                <img :src="prev" alt="新图" class="w-full h-full object-cover" />
                <button
                  type="button"
                  class="absolute bottom-1 left-1 text-xs px-1.5 py-0.5 bg-ink/75 text-parchment inline-flex items-center gap-0.5"
                  data-testid="crop-pending"
                  @click="openCropForPending(i)"
                >
                  <Crop class="w-3 h-3" /> 裁剪
                </button>
              </div>
            </div>

            <label class="block">
              <span class="text-mute">{{ isLink ? '首图 / 封面（选填）' : '更换封面（选填）' }}</span>
              <input
                type="file"
                accept="image/*"
                class="mt-1 w-full min-h-tap px-3 py-2 border border-clay bg-rice"
                data-testid="edit-cover-input"
                @change="onCoverPick"
              />
            </label>
            <div v-if="newCoverPreview || (coverName && !removeCover)" class="flex items-center gap-3">
              <img
                :src="newCoverPreview || existingUrl(coverName)"
                alt="封面预览"
                class="w-24 h-24 object-cover border border-clay"
                data-testid="edit-cover-preview"
              />
              <div class="flex flex-col gap-2">
                <button
                  type="button"
                  class="min-h-tap px-3 border border-clay inline-flex items-center gap-1 text-sm"
                  data-testid="crop-cover"
                  @click="openCropForCover"
                >
                  <Crop class="w-4 h-4" /> 裁剪封面
                </button>
                <button
                  type="button"
                  class="min-h-tap px-3 border border-cinnabar text-cinnabar text-sm"
                  @click="clearCover"
                >
                  清除封面
                </button>
              </div>
            </div>
            <p class="text-mute text-sm">单张图片时自动设为封面；可点「封面」指定默认首图。</p>
          </div>

          <p v-if="error" class="text-cinnabar">{{ error }}</p>
          <button
            type="button"
            class="w-full min-h-tap bg-cinnabar text-parchment disabled:opacity-60"
            data-testid="edit-save"
            :disabled="saving"
            @click="save"
          >
            {{ saving ? '保存中…' : i18n.t('save') }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="cropOpen"
      class="fixed inset-0 z-[60] bg-ink/70 flex items-center justify-center p-4"
      data-testid="crop-editor"
      @click.self="cropOpen = false"
    >
      <div class="bg-parchment border border-clay p-4 max-w-lg w-full space-y-3">
        <h3 class="font-song text-lg">裁剪</h3>
        <CropStage :src="cropSrc" @ready="(c) => (cropCanvas = c)" />
        <div class="flex gap-2">
          <button type="button" class="flex-1 min-h-tap border border-clay" @click="cropOpen = false">
            {{ i18n.t('cancel') }}
          </button>
          <button
            type="button"
            class="flex-1 min-h-tap bg-cinnabar text-parchment"
            data-testid="crop-apply"
            @click="applyCrop"
          >
            应用裁剪
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
