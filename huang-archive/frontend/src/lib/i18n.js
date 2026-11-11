/** Lightweight zh / en / ru i18n — no vue-i18n dependency. */

export const LOCALES = [
  { code: 'zh', label: '中文 (中国)', native: '中文', flag: 'cn' },
  { code: 'en', label: 'English', native: 'English', flag: 'us' },
  { code: 'ru', label: 'Русский', native: 'Русский', flag: 'ru' },
]

const dict = {
  zh: {
    siteTitle: '黄志松人生纪念馆',
    welcome: '欢迎',
    upload: '上传',
    members: '成员管理',
    settings: '全局管理',
    logout: '退出',
    searchPlaceholder: '搜索标题、关系人、说明、上传者…',
    cards: '卡片',
    timeline: '年表',
    resultCount: '共 {n} 条',
    pageOf: '第 {page} / {total} 页（每页 {size} 条）',
    loading: '载入中…',
    empty: '没有符合条件的档案',
    newsLink: '新闻链接',
    newsClip: '新闻剪报',
    coverOptional: '首图 / 封面（选填）',
    editArchive: '编辑档案',
    save: '保存',
    cancel: '取消',
    language: '语言',
  },
  en: {
    siteTitle: 'Huang Zhisong Memorial Hall',
    welcome: 'Welcome',
    upload: 'Upload',
    members: 'Members',
    settings: 'Global settings',
    logout: 'Log out',
    searchPlaceholder: 'Search title, people, notes, uploader…',
    cards: 'Cards',
    timeline: 'Timeline',
    resultCount: '{n} items',
    pageOf: 'Page {page} / {total} ({size} per page)',
    loading: 'Loading…',
    empty: 'No matching archives',
    newsLink: 'News link',
    newsClip: 'News clipping',
    coverOptional: 'Cover image (optional)',
    editArchive: 'Edit archive',
    save: 'Save',
    cancel: 'Cancel',
    language: 'Language',
  },
  ru: {
    siteTitle: 'Мемориал Хуан Чжисуна',
    welcome: 'Добро пожаловать',
    upload: 'Загрузить',
    members: 'Члены семьи',
    settings: 'Глобальные настройки',
    logout: 'Выйти',
    searchPlaceholder: 'Поиск по названию, людям, описанию…',
    cards: 'Карточки',
    timeline: 'Хроника',
    resultCount: '{n} записей',
    pageOf: 'Стр. {page} / {total} ({size} на стр.)',
    loading: 'Загрузка…',
    empty: 'Нет подходящих записей',
    newsLink: 'Новостная ссылка',
    newsClip: 'Вырезка',
    coverOptional: 'Обложка (необязательно)',
    editArchive: 'Редактировать',
    save: 'Сохранить',
    cancel: 'Отмена',
    language: 'Язык',
  },
}

export function t(locale, key, vars = {}) {
  const table = dict[locale] || dict.zh
  let s = table[key] ?? dict.zh[key] ?? key
  for (const [k, v] of Object.entries(vars)) {
    s = s.replaceAll(`{${k}}`, String(v))
  }
  return s
}

/** Map ISO country → locale. Default zh. */
export function localeFromCountry(country) {
  const c = String(country || '').toUpperCase()
  if (!c || c === 'XX' || c === 'T1') return 'zh'
  if (['CN', 'TW', 'HK', 'MO', 'SG'].includes(c)) return 'zh'
  if (['RU', 'BY', 'KZ', 'KG', 'UZ', 'TJ', 'AM', 'AZ'].includes(c)) return 'ru'
  return 'en'
}

export function localeFromAcceptLanguage(header) {
  const h = String(header || '').toLowerCase()
  if (h.includes('zh')) return 'zh'
  if (h.includes('ru')) return 'ru'
  if (h.includes('en')) return 'en'
  return 'zh'
}
