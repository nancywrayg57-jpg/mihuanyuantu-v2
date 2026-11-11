<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Plus, Pencil, Ban, RotateCcw, ScrollText, Search } from 'lucide-vue-next'
import pb from '../lib/pb'
import { useAuthStore } from '../stores/auth'
import { useLocaleStore } from '../stores/locale'
import { zhError } from '../lib/errors'
import { RELATION_OPTIONS, genMemberIdentity } from '../lib/relations'
import { normalizePassword } from '../lib/roster'

const PAGE_SIZE = 10

const auth = useAuthStore()
const router = useRouter()
const i18n = useLocaleStore()

const members = ref([])
const audits = ref([])
const loading = ref(true)
const error = ref('')
const formOpen = ref(false)
const editing = ref(null)
const selected = ref({})
const noticeTitle = ref('')
const noticeBody = ref('')
const noticeMsg = ref('')
const searchQ = ref('')
const page = ref(1)

const displayName = ref('')
const birthDate = ref('')
const relation = ref('')
const password = ref('')
const saving = ref(false)
const formError = ref('')

const filtered = computed(() => {
  const q = searchQ.value.trim().toLowerCase()
  if (!q) return members.value
  return members.value.filter((m) => {
    const hay = [m.display_name, m.relation, m.role, m.disabled ? '停用' : '正常']
      .join(' ')
      .toLowerCase()
    return hay.includes(q)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))

const paged = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return filtered.value.slice(start, start + PAGE_SIZE)
})

watch(searchQ, () => {
  page.value = 1
})

watch(filtered, () => {
  if (page.value > totalPages.value) page.value = totalPages.value
})

function goPage(p) {
  page.value = Math.min(totalPages.value, Math.max(1, p))
}

async function writeAudit(action, target, detail = '') {
  try {
    await pb.collection('audit_logs').create({
      action,
      target,
      detail,
      actor: auth.user.id,
      actor_name: auth.displayName,
    })
  } catch (_) {}
}

async function load() {
  if (!auth.isAdmin) {
    router.replace('/')
    return
  }
  loading.value = true
  error.value = ''
  try {
    const list = await pb.collection('users').getFullList({ sort: 'display_name' })
    members.value = list.filter((m) => m.role !== 'guest' && m.display_name !== '吊唁贵宾')
    audits.value = await pb
      .collection('audit_logs')
      .getList(1, 30, { sort: '-created' })
      .then((r) => r.items)
      .catch(() => [])
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
      await writeAudit(pwd ? 'reset_password' : 'update_member', name)
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
        disabled: false,
      })
      await writeAudit('create_member', name)
    }
    formOpen.value = false
    await load()
  } catch (e) {
    formError.value = zhError(e, '保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleDisabled(m) {
  if (m.role === 'admin') return
  const next = !m.disabled
  try {
    await pb.collection('users').update(m.id, { disabled: next })
    await writeAudit(next ? 'disable_member' : 'enable_member', m.display_name)
    await load()
  } catch (e) {
    error.value = zhError(e, '更新停用状态失败')
  }
}

async function batchReset() {
  const ids = Object.keys(selected.value).filter((id) => selected.value[id])
  if (!ids.length) {
    error.value = '请先勾选要重置密码的成员'
    return
  }
  error.value = ''
  for (const id of ids) {
    const m = members.value.find((x) => x.id === id)
    if (!m || m.role === 'admin') continue
    try {
      await pb.collection('users').update(id, { password: 'hzs1933', passwordConfirm: 'hzs1933' })
      await writeAudit('batch_reset_password', m.display_name, 'hzs1933')
    } catch (e) {
      error.value = zhError(e, `重置 ${m.display_name} 失败`)
      return
    }
  }
  selected.value = {}
  await load()
}

async function publishNotice() {
  noticeMsg.value = ''
  if (!noticeTitle.value.trim() || !noticeBody.value.trim()) {
    noticeMsg.value = '请填写标题与正文'
    return
  }
  try {
    await pb.collection('notices').create({
      title: noticeTitle.value.trim(),
      body: noticeBody.value.trim(),
      pinned: true,
    })
    await writeAudit('publish_notice', noticeTitle.value.trim())
    noticeTitle.value = ''
    noticeBody.value = ''
    noticeMsg.value = '已发布更新摘要'
  } catch (e) {
    noticeMsg.value = zhError(e, '发布失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen pb-10" data-testid="members-page">
    <header class="border-b border-clay bg-parchment/90 sticky top-0 z-40">
      <div class="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3 flex-wrap">
        <button
          type="button"
          class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
          @click="router.push('/')"
        >
          <ArrowLeft class="w-5 h-5" /> 返回
        </button>
        <h1 class="font-song text-xl flex-1">{{ i18n.t('members') }}</h1>
        <button
          type="button"
          class="min-h-tap px-3 border border-clay inline-flex items-center gap-1"
          data-testid="batch-reset"
          @click="batchReset"
        >
          <RotateCcw class="w-5 h-5" /> <span class="hidden sm:inline">批量重置密码</span>
        </button>
        <button
          type="button"
          class="min-h-tap px-4 bg-cinnabar text-parchment inline-flex items-center gap-1"
          data-testid="member-create"
          @click="openCreate"
        >
          <Plus class="w-5 h-5" /> 新增成员
        </button>
      </div>
    </header>

    <main class="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <section class="space-y-3" data-testid="members-search-filters">
        <label class="relative block">
          <Search class="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
          <input
            v-model="searchQ"
            type="search"
            class="w-full min-h-tap pl-10 pr-3 border border-clay bg-parchment"
            placeholder="搜索姓名、亲属关系、状态…"
            data-testid="members-search-input"
          />
        </label>
        <p class="text-mute text-sm" data-testid="members-result-count">
          共 {{ filtered.length }} 人
          <template v-if="filtered.length">
            · 第 {{ page }} / {{ totalPages }} 页（每页 {{ PAGE_SIZE }} 条）
          </template>
        </p>
      </section>

      <p v-if="loading" class="text-mute">加载中…</p>
      <p v-else-if="error" class="text-cinnabar">{{ error }}</p>
      <template v-else>
        <!-- Desktop table -->
        <div class="hidden sm:block overflow-x-auto border border-clay bg-parchment" data-testid="members-table">
          <table class="w-full text-left min-w-[720px]">
            <thead class="bg-rice text-mute">
              <tr>
                <th class="px-3 py-3 font-medium">选</th>
                <th class="px-3 py-3 font-medium">姓名</th>
                <th class="px-3 py-3 font-medium">亲属关系</th>
                <th class="px-3 py-3 font-medium">状态</th>
                <th class="px-3 py-3 font-medium">角色</th>
                <th class="px-3 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in paged" :key="m.id" class="border-t border-clay">
                <td class="px-3 py-3">
                  <input
                    v-if="m.role !== 'admin'"
                    v-model="selected[m.id]"
                    type="checkbox"
                    class="w-5 h-5"
                    :data-testid="'sel-' + m.id"
                  />
                </td>
                <td class="px-3 py-3">{{ m.display_name }}</td>
                <td class="px-3 py-3">{{ m.relation || '—' }}</td>
                <td class="px-3 py-3">{{ m.disabled ? '已停用' : '正常' }}</td>
                <td class="px-3 py-3">{{ m.role === 'admin' ? '管理员' : '成员' }}</td>
                <td class="px-3 py-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    class="inline-flex items-center gap-1 min-h-tap px-3 border border-celadon text-celadon"
                    @click="openEdit(m)"
                  >
                    <Pencil class="w-4 h-4" /> 修改
                  </button>
                  <button
                    v-if="m.role !== 'admin'"
                    type="button"
                    class="inline-flex items-center gap-1 min-h-tap px-3 border border-cinnabar text-cinnabar"
                    data-testid="toggle-disabled"
                    @click="toggleDisabled(m)"
                  >
                    <Ban class="w-4 h-4" /> {{ m.disabled ? '启用' : '停用' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Mobile list -->
        <div class="sm:hidden space-y-3" data-testid="members-mobile-list">
          <article
            v-for="m in paged"
            :key="m.id"
            class="border border-clay bg-parchment p-4 space-y-3"
          >
            <div class="flex items-start gap-3">
              <input
                v-if="m.role !== 'admin'"
                v-model="selected[m.id]"
                type="checkbox"
                class="w-5 h-5 mt-1"
                :data-testid="'sel-m-' + m.id"
              />
              <div class="flex-1 min-w-0">
                <h3 class="font-song text-lg truncate">{{ m.display_name }}</h3>
                <p class="text-mute text-sm mt-0.5">
                  {{ m.relation || '—' }} · {{ m.disabled ? '已停用' : '正常' }} ·
                  {{ m.role === 'admin' ? '管理员' : '成员' }}
                </p>
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                type="button"
                class="inline-flex items-center gap-1 min-h-tap px-3 border border-celadon text-celadon"
                @click="openEdit(m)"
              >
                <Pencil class="w-4 h-4" /> 修改
              </button>
              <button
                v-if="m.role !== 'admin'"
                type="button"
                class="inline-flex items-center gap-1 min-h-tap px-3 border border-cinnabar text-cinnabar"
                @click="toggleDisabled(m)"
              >
                <Ban class="w-4 h-4" /> {{ m.disabled ? '启用' : '停用' }}
              </button>
            </div>
          </article>
          <p v-if="!paged.length" class="text-mute text-center py-8">没有符合条件的成员</p>
        </div>

        <div
          v-if="totalPages > 1"
          class="flex items-center justify-center gap-2"
          data-testid="members-pagination"
        >
          <button
            type="button"
            class="min-h-tap px-3 border border-clay disabled:opacity-40"
            :disabled="page <= 1"
            data-testid="members-page-prev"
            @click="goPage(page - 1)"
          >
            上一页
          </button>
          <span class="text-mute text-sm">{{ page }} / {{ totalPages }}</span>
          <button
            type="button"
            class="min-h-tap px-3 border border-clay disabled:opacity-40"
            :disabled="page >= totalPages"
            data-testid="members-page-next"
            @click="goPage(page + 1)"
          >
            下一页
          </button>
        </div>
      </template>

      <section class="border border-clay bg-parchment p-4 space-y-3" data-testid="notice-admin">
        <h2 class="font-song text-xl inline-flex items-center gap-2">
          <ScrollText class="w-5 h-5" /> 发布更新摘要
        </h2>
        <input
          v-model="noticeTitle"
          class="w-full min-h-tap px-3 border border-clay bg-rice"
          placeholder="标题"
          data-testid="notice-title"
        />
        <textarea
          v-model="noticeBody"
          rows="3"
          class="w-full px-3 py-2 border border-clay bg-rice"
          placeholder="正文"
          data-testid="notice-body"
        />
        <button
          type="button"
          class="min-h-tap px-4 bg-celadon text-parchment"
          data-testid="notice-publish"
          @click="publishNotice"
        >
          发布
        </button>
        <p v-if="noticeMsg" class="text-sm">{{ noticeMsg }}</p>
      </section>

      <section class="border border-clay bg-parchment p-4" data-testid="audit-log">
        <h2 class="font-song text-xl mb-3">操作审计</h2>
        <ul class="space-y-2 text-sm max-h-64 overflow-auto">
          <li v-for="a in audits" :key="a.id" class="border-b border-clay/60 py-2">
            <span class="text-mute">{{ a.created }}</span>
            · {{ a.actor_name || '—' }} · <strong>{{ a.action }}</strong>
            · {{ a.target }}
            <span v-if="a.detail" class="text-mute">（{{ a.detail }}）</span>
          </li>
          <li v-if="!audits.length" class="text-mute">暂无审计记录</li>
        </ul>
      </section>
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
          <button type="button" class="flex-1 min-h-tap border border-clay" @click="formOpen = false">
            取消
          </button>
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
