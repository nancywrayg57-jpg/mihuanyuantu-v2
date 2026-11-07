<script setup>
import { ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import pb from '../lib/pb'
import { zhError } from '../lib/errors'

const props = defineProps({
  open: { type: Boolean, default: false },
  archive: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const title = ref('')
const occurredTime = ref('')
const relatedPersons = ref('')
const description = ref('')
const saving = ref(false)
const error = ref('')

watch(
  () => [props.open, props.archive],
  () => {
    if (!props.open || !props.archive) return
    title.value = props.archive.title || ''
    occurredTime.value = toDateInput(props.archive.occurred_time)
    relatedPersons.value = props.archive.related_persons || ''
    description.value = props.archive.description || ''
    error.value = ''
  },
  { immediate: true },
)

function toDateInput(value) {
  const s = String(value || '').trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s
  return ''
}

async function save() {
  error.value = ''
  if (!title.value.trim() || !occurredTime.value || !relatedPersons.value.trim()) {
    error.value = '请填写标题、发生时间与关系人'
    return
  }
  saving.value = true
  try {
    const updated = await pb.collection('archives').update(props.archive.id, {
      title: title.value.trim(),
      occurred_time: occurredTime.value,
      related_persons: relatedPersons.value.trim(),
      description: description.value.trim(),
    })
    emit('saved', updated)
    emit('close')
  } catch (e) {
    error.value = zhError(e, '保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && archive"
      class="fixed inset-0 z-50 bg-ink/45 flex items-end sm:items-center justify-center p-0 sm:p-6"
      @click.self="emit('close')"
    >
      <div class="w-full max-w-xl max-h-[92vh] overflow-auto bg-parchment border border-clay">
        <div class="sticky top-0 flex items-center justify-between px-5 py-4 border-b border-clay bg-parchment">
          <h2 class="font-song text-xl">编辑档案</h2>
          <button type="button" class="min-h-tap min-w-[48px] grid place-items-center" @click="emit('close')">
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
            <input
              v-model="occurredTime"
              type="date"
              class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
            />
          </label>
          <label class="block">
            <span class="text-mute">关系人</span>
            <input v-model="relatedPersons" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
          </label>
          <label class="block">
            <span class="text-mute">说明（选填）</span>
            <textarea v-model="description" rows="3" class="mt-1 w-full px-3 py-3 border border-clay bg-rice" />
          </label>
          <p v-if="error" class="text-cinnabar">{{ error }}</p>
          <button
            type="button"
            class="w-full min-h-tap bg-cinnabar text-parchment disabled:opacity-60"
            :disabled="saving"
            @click="save"
          >
            {{ saving ? '保存中…' : '保存修改' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
