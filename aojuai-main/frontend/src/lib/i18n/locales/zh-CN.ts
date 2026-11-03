/**
 * 核心语言包：zh-CN（基准语言）。
 * 约定见 docs/dev/guide_docs/FRONTEND_I18N_GUIDE.md：
 * - `menu.<中文标题>` 用于翻译后端菜单标题（DB 存中文，键即原文）
 * - 分支/模块的语言包放 locales/<module>.ts，通过 registerLocaleMessages 注册
 */
export const zhCN = {
  'common.loading': '加载中…',
  'common.confirm': '确认',
  'common.cancel': '取消',
  'common.save': '保存',
  'common.search': '搜索',
  'common.refresh': '刷新',
  'common.create': '新建',
  'common.edit': '编辑',
  'common.delete': '删除',
  'common.reset': '重置',
  'common.submit': '提交',
  'common.close': '关闭',
  'common.detail': '详情',
  'common.export': '导出',
  'common.import': '导入',
  'common.actions': '操作',
  'common.status': '状态',
  'common.name': '名称',
  'common.description': '描述',
  'common.createdAt': '创建时间',
  'common.updatedAt': '更新时间',
  'common.enabled': '启用',
  'common.disabled': '禁用',
  'common.all': '全部',
  'common.empty': '暂无数据',
  'common.prevPage': '上一页',
  'common.nextPage': '下一页',
  'common.totalItems': '共 {n} 条',
  'common.expandFilters': '展开筛选',
  'common.collapseFilters': '收起筛选',
  'common.filters': '筛选',

  'nav.title': '导航',
  'nav.searchMenus': '搜索菜单…',
  'nav.searchMenusHint': '搜索菜单 (⌘K)',
  'nav.noMenuMatch': '未找到匹配的菜单',
  'nav.expandSidebar': '展开菜单',
  'nav.collapseSidebar': '收起菜单',
  'nav.loadingMenus': '加载菜单中…',
  'nav.menuLoadFailed': '菜单加载失败：',

  'auth.logout': '退出登录',
  'auth.login': '登录',
  'auth.loggingIn': '登录中…',
  'auth.username': '用户名',
  'auth.password': '密码',
  'auth.usernamePlaceholder': '请输入用户名',
  'auth.register': '注册新账号',

  'role.superuser': '系统管理员',
  'role.tenantAdmin': '租户管理员',
  'role.user': '用户',

  'topbar.menu': '菜单',
  'topbar.targetTenant': '目标租户',
  'topbar.selectTenant': '选择租户',
  'topbar.readonlyDemo': '只读体验',
  'topbar.theme': '主题',
  'topbar.themeLight': '浅色',
  'topbar.themeDark': '深色',
  'topbar.language': '语言',
  'topbar.localeZhCN': '简体中文',
  'topbar.localeEnUS': 'English',
  'topbar.localeEsES': 'Español',

  'assistant.open': 'AI 助手',
} as const

export type CoreMessageKey = keyof typeof zhCN
