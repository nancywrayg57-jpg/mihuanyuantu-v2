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
const cropStageRef = ref(null)
const coverDirty = ref(false)
const blobUrls = ref([])

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
    coverDirty.value = false
    clearPending()
  },
  { immediate: true },
)

function trackBlob(url) {
  if (url) blobUrls.value.push(url)
  return url
}

function clearPending() {
  for (const p of pendingPreviews.value) if (p) URL.revokeObjectURL(p)
  if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
  for (const u of blobUrls.value) {
    try {
      URL.revokeObjectURL(u)
    } catch (_) {}
  }
  blobUrls.value = []
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
  return thumbUrl(pb, props.archive, name, '1200x0') || pb.files.getURL(props.archive, name)
}

/** Fetch PB file as blob URL so canvas crop is not CORS-tainted. */
async function toLocalCropSrc(urlOrName) {
  let url = urlOrName
  if (urlOrName && !/^https?:|^blob:|^data:/i.test(urlOrName)) {
    url = existingUrl(urlOrName)
  }
  if (!url) return ''
  if (url.startsWith('blob:') || url.startsWith('data:')) return url
  try {
    const headers = {}
    if (pb.authStore?.token) headers.Authorization = pb.authStore.token
    const res = await fetch(url, { headers, credentials: 'include' })
    if (!res.ok) throw new Error(`fetch ${res.status}`)
    const blob = await res.blob()
    return trackBlob(URL.createObjectURL(blob))
  } catch (e) {
    // Fallback: still try direct URL (may fail toBlob if tainted)
    return url
  }
}

function setCoverExisting(name) {
  coverName.value = name
  removeCover.value = false
  coverDirty.value = true
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
      coverDirty.value = true
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
    coverDirty.value = true
  } catch (err) {
    error.value = zhError(err, '封面处理失败')
  }
  e.target.value = ''
}

async function openCropForCover() {
  const srcHint = newCoverPreview.value || (coverName.value ? coverName.value : '')
  if (!srcHint) return
  try {
    cropSrc.value = await toLocalCropSrc(srcHint)
    cropTarget.value = 'cover'
    cropOpen.value = true
  } catch (e) {
    error.value = zhError(e, '无法打开裁剪')
  }
}

async function openCropForPending(i) {
  cropSrc.value = pendingPreviews.value[i]
  cropTarget.value = i
  cropOpen.value = true
}

function clearCover() {
  removeCover.value = true
  coverDirty.value = true
  coverName.value = ''
  if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
  newCoverPreview.value = ''
  newCoverFile.value = null
}

async function applyCrop() {
  error.value = ''
  const stage = cropStageRef.value
  if (!stage?.exportBlob) {
    error.value = '裁剪未就绪'
    return
  }
  const blob = await stage.exportBlob(0.92)
  if (!blob || blob.size < 32) {
    error.value = '裁剪失败：请重试（图片可能未加载）'
    return
  }
  const file = new File([blob], `cover-crop-${Date.now()}.jpg`, { type: 'image/jpeg' })
  if (cropTarget.value === 'cover') {
    if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
    newCoverFile.value = file
    newCoverPreview.value = URL.createObjectURL(file)
    coverName.value = ''
    removeCover.value = false
    coverDirty.value = true
  } else if (typeof cropTarget.value === 'number') {
    const i = cropTarget.value
    if (pendingPreviews.value[i]) URL.revokeObjectURL(pendingPreviews.value[i])
    pendingFiles.value[i] = file
    pendingPreviews.value[i] = URL.createObjectURL(file)
    // If this pending image is also the cover source, refresh cover file
    if (newCoverFile.value && i === 0 && pendingFiles.value.length === 1) {
      newCoverFile.value = file
      if (newCoverPreview.value) URL.revokeObjectURL(newCoverPreview.value)
      newCoverPreview.value = URL.createObjectURL(file)
      coverDirty.value = true
    }
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
      // Persist cropped / new cover to server cover_file
      if (newCoverFile.value) {
        const cf = normalizeUploadFile(newCoverFile.value)
        form.append('cover_file', cf, safeUploadFilename(cf, 'jpg') || `cover-${Date.now()}.jpg`)
      } else if (removeCover.value) {
        form.append('cover_file', '')
      } else if (
        pendingFiles.value.length === 1 &&
        mediaNames.value.length === 0 &&
        !coverName.value
      ) {
        const cf = normalizeUploadFile(pendingFiles.value[0])
        form.append('cover_file', cf, 'cover.jpg')
      } else if (coverDirty.value && coverName.value && !newCoverFile.value) {
        // User picked an existing media as cover without cropping — copy that file to cover_file
        try {
          const url = existingUrl(coverName.value)
          const headers = {}
          if (pb.authStore?.token) headers.Authorization = pb.authStore.token
          const res = await fetch(url, { headers, credentials: 'include' })
          if (res.ok) {
            const blob = await res.blob()
            const file = new File([blob], coverName.value || 'cover.jpg', {
              type: blob.type || 'image/jpeg',
            })
            form.append('cover_file', file, safeUploadFilename(file, 'jpg'))
          }
        } catch (_) {}
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
            <span class="text-mute">{{ i18n.t('title') }}</span>
            <input v-model="title" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">{{ i18n.t('occurredTime') }}</span>
            <input v-model="occurredTime" type="date" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">{{ i18n.t('related') }}</span>
            <input v-model="relatedPersons" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">{{ i18n.t('descriptionOptional') }}</span>
            <textarea v-model="description" rows="3" class="mt-1 w-full px-3 py-3 border border-clay bg-rice" />
          </label>

          <div v-if="isImageLike || isLink" class="space-y-3" data-testid="edit-media-section">
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <h3 class="font-song text-lg">{{ i18n.t('imagesCover') }}</h3>
              <label
                v-if="isImageLike"
                class="min-h-tap px-3 border border-clay bg-rice inline-flex items-center cursor-pointer text-sm"
              >
                {{ i18n.t('addImages') }}
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
                  <Star class="w-3 h-3" /> {{ i18n.t('setAsCover') }}
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
                  <Crop class="w-3 h-3" /> {{ i18n.t('crop') }}
                </button>
              </div>
            </div>

            <label class="block">
              <span class="text-mute">{{ isLink ? i18n.t('coverOptional') : i18n.t('changeCover') }}</span>
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
                  <Crop class="w-4 h-4" /> {{ i18n.t('cropCover') }}
                </button>
                <button
                  type="button"
                  class="min-h-tap px-3 border border-cinnabar text-cinnabar text-sm"
                  @click="clearCover"
                >
                  {{ i18n.t('clearCover') }}
                </button>
              </div>
            </div>
            <p class="text-mute text-sm">{{ i18n.t('coverHint') }}</p>
          </div>

          <p v-if="error" class="text-cinnabar" data-testid="edit-error">{{ error }}</p>
          <button
            type="button"
            class="w-full min-h-tap bg-cinnabar text-parchment disabled:opacity-60"
            data-testid="edit-save"
            :disabled="saving"
            @click="save"
          >
            {{ saving ? i18n.t('saving') : i18n.t('save') }}
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
        <h3 class="font-song text-lg">{{ i18n.t('crop') }}</h3>
        <CropStage ref="cropStageRef" :src="cropSrc" />
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
            {{ i18n.t('applyCrop') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
