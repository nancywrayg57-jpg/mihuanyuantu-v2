<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Plus, Pencil } from 'lucide-vue-next'
import pb from '../lib/pb'
import { useAuthStore } from '../stores/auth'
import { zhError } from '../lib/errors'
import { RELATION_OPTIONS, genMemberIdentity } from '../lib/relations'
import { normalizePassword } from '../lib/roster'

const auth = useAuthStore()
const router = useRouter()

const members = ref([])
const loading = ref(true)
const error = ref('')
const formOpen = ref(false)
const editing = ref(null)

const displayName = ref('')
const birthDate = ref('')
const relation = ref('')
const password = ref('')
const saving = ref(false)
const formError = ref('')

async function load() {
  if (!auth.isAdmin) {
    router.replace('/')
    return
  }
  loading.value = true
  error.value = ''
  try {
    const list = await pb.collection('users').getFullList({ sort: 'display_name' })
    members.value = list
  } catch (e) {
    error.value = zhError(e, '加载成员失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  displayName.value = ''
  birthDate.value = ''
  relation.value = ''
  password.value = 'hzs1933'
  formError.value = ''
  formOpen.value = true
}

function openEdit(m) {
  editing.value = m
  displayName.value = m.display_name || ''
  birthDate.value = (m.birth_date || '').slice(0, 10)
  relation.value = m.relation || ''
  password.value = ''
  formError.value = ''
  formOpen.value = true
}

async function save() {
  formError.value = ''
  const name = displayName.value.trim()
  if (!name) {
    formError.value = '请填写姓名'
    return
  }
  if (!relation.value) {
    formError.value = '请选择亲属关系'
    return
  }
  const pwd = normalizePassword(password.value)
  if (!editing.value && (!pwd || pwd.length < 6)) {
    formError.value = '新建成员密码至少 6 位（默认 hzs1933）'
    return
  }
  if (editing.value && pwd && pwd.length < 6) {
    formError.value = '新密码至少 6 位'
    return
  }

  saving.value = true
  try {
    if (editing.value) {
      const payload = {
        display_name: name,
        birth_date: birthDate.value || '',
        relation: relation.value,
      }
      if (pwd) {
        payload.password = pwd
        payload.passwordConfirm = pwd
      }
      await pb.collection('users').update(editing.value.id, payload)
    } else {
      const ids = genMemberIdentity(name)
      await pb.collection('users').create({
        email: ids.email,
        username: ids.username,
        emailVisibility: true,
        password: pwd || 'hzs1933',
        passwordConfirm: pwd || 'hzs1933',
        display_name: name,
        birth_date: birthDate.value || '',
        relation: relation.value,
        role: 'member',
      })
    }
    formOpen.value = false
    await load()
  } catch (e) {
    formError.value = zhError(e, '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen pb-10">
    <header class="border-b border-clay bg-parchment/90 sticky top-0 z-40">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
        <button type="button" class="min-h-tap px-3 border border-clay inline-flex items-center gap-1" @click="router.push('/')">
          <ArrowLeft class="w-5 h-5" /> 返回
        </button>
        <h1 class="font-song text-xl flex-1">家族成员管理</h1>
        <button
          type="button"
          class="min-h-tap px-4 bg-cinnabar text-parchment inline-flex items-center gap-1"
          @click="openCreate"
        >
          <Plus class="w-5 h-5" /> 新增成员
        </button>
      </div>
    </header>

    <main class="max-w-4xl mx-auto px-4 py-6">
      <p v-if="loading" class="text-mute">加载中…</p>
      <p v-else-if="error" class="text-cinnabar">{{ error }}</p>
      <div v-else class="overflow-x-auto border border-clay bg-parchment">
        <table class="w-full text-left min-w-[640px]">
          <thead class="bg-rice text-mute">
            <tr>
              <th class="px-3 py-3 font-medium">姓名</th>
              <th class="px-3 py-3 font-medium">亲属关系</th>
              <th class="px-3 py-3 font-medium">出生年月</th>
              <th class="px-3 py-3 font-medium">角色</th>
              <th class="px-3 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in members" :key="m.id" class="border-t border-clay">
              <td class="px-3 py-3">{{ m.display_name }}</td>
              <td class="px-3 py-3">{{ m.relation || '—' }}</td>
              <td class="px-3 py-3">{{ m.birth_date || '—' }}</td>
              <td class="px-3 py-3">{{ m.role === 'admin' ? '管理员' : '成员' }}</td>
              <td class="px-3 py-3">
                <button
                  type="button"
                  class="inline-flex items-center gap-1 min-h-tap px-3 border border-celadon text-celadon"
                  @click="openEdit(m)"
                >
                  <Pencil class="w-4 h-4" /> 修改
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>

    <div
      v-if="formOpen"
      class="fixed inset-0 z-50 bg-ink/45 flex items-end sm:items-center justify-center p-0 sm:p-6"
      @click.self="formOpen = false"
    >
      <div class="w-full max-w-md bg-parchment border border-clay p-5 space-y-4 max-h-[92vh] overflow-auto">
        <h2 class="font-song text-xl">{{ editing ? '修改成员' : '新增成员' }}</h2>
        <label class="block">
          <span class="text-mute">姓名（必填）</span>
          <input v-model="displayName" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
        </label>
        <label class="block">
          <span class="text-mute">出生年月（选填）</span>
          <input v-model="birthDate" type="date" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice" />
        </label>
        <label class="block">
          <span class="text-mute">亲属关系（必填）</span>
          <select v-model="relation" class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice">
            <option value="" disabled>请选择</option>
            <option v-for="r in RELATION_OPTIONS" :key="r" :value="r">{{ r }}</option>
          </select>
        </label>
        <label class="block">
          <span class="text-mute">{{ editing ? '登录密码（留空则不改）' : '登录密码（默认 hzs1933）' }}</span>
          <input
            v-model="password"
            type="password"
            lang="en"
            inputmode="latin"
            class="mt-1 w-full min-h-tap px-3 border border-clay bg-rice"
            :placeholder="editing ? '不修改请留空' : 'hzs1933'"
          />
        </label>
        <p v-if="formError" class="text-cinnabar">{{ formError }}</p>
        <div class="flex gap-3">
          <button type="button" class="flex-1 min-h-tap border border-clay" @click="formOpen = false">取消</button>
          <button
            type="button"
            class="flex-1 min-h-tap bg-cinnabar text-parchment disabled:opacity-60"
            :disabled="saving"
            @click="save"
          >
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
