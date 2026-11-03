/**
 * 样例能力包的语言包。
 *
 * 这是「模块语言包」的参考写法：模块自己维护三份文案、在文件末尾调
 * registerLocaleMessages 注册进核心注册表，**不改核心语言包**。
 * 键一律用 `<模块 code>.` 前缀，避免与别的模块撞键。
 *
 * 缺翻译时的回退链在 registry.ts：当前语言 → zh-CN → 键本身。
 * 所以先把 zh-CN 写全，en/es 可以逐步补。
 */
import { registerLocaleMessages } from '../registry'

const zhCN: Record<string, string> = {
  'sampleItems.action.cancel': '取消',
  'sampleItems.action.confirm': '确定',
  'sampleItems.dialog.createTitle': '新建样例条目',
  'sampleItems.dialog.editTitle': '编辑样例条目',
  'sampleItems.dialog.deleteTitle': '删除样例条目',
  'sampleItems.dialog.deleteConfirm': '确认软删除「{name}」？删除后可由管理员恢复。',
  'sampleItems.title': '样例条目',
  'sampleItems.description': '官方 capability 样例：租户隔离、软删除与按钮权限。',
  'sampleItems.column.code': '编码',
  'sampleItems.column.name': '名称',
  'sampleItems.column.description': '描述',
  'sampleItems.column.actions': '操作',
  'sampleItems.action.refresh': '刷新',
  'sampleItems.action.create': '新建',
  'sampleItems.action.edit': '编辑',
  'sampleItems.action.delete': '删除',
  'sampleItems.prompt.code': '编码（小写字母、数字、_、-）',
  'sampleItems.prompt.name': '名称',
  'sampleItems.prompt.newName': '新名称',
  'sampleItems.empty': '暂无数据',
  'sampleItems.loading': '加载中...',
  'sampleItems.error.load': '加载样例条目失败',
  'sampleItems.error.create': '创建失败',
  'sampleItems.error.update': '更新失败',
  'sampleItems.error.delete': '删除失败',
}

const enUS: Record<string, string> = {
  'sampleItems.action.cancel': 'Cancel',
  'sampleItems.action.confirm': 'Confirm',
  'sampleItems.dialog.createTitle': 'New sample item',
  'sampleItems.dialog.editTitle': 'Edit sample item',
  'sampleItems.dialog.deleteTitle': 'Delete sample item',
  'sampleItems.dialog.deleteConfirm': 'Soft-delete “{name}”? An administrator can restore it later.',
  'sampleItems.title': 'Sample Items',
  'sampleItems.description':
    'Official capability example: tenant isolation, soft delete, and button-level permissions.',
  'sampleItems.column.code': 'Code',
  'sampleItems.column.name': 'Name',
  'sampleItems.column.description': 'Description',
  'sampleItems.column.actions': 'Actions',
  'sampleItems.action.refresh': 'Refresh',
  'sampleItems.action.create': 'New',
  'sampleItems.action.edit': 'Edit',
  'sampleItems.action.delete': 'Delete',
  'sampleItems.prompt.code': 'Code (lowercase letters, digits, _ and -)',
  'sampleItems.prompt.name': 'Name',
  'sampleItems.prompt.newName': 'New name',
  'sampleItems.empty': 'No data',
  'sampleItems.loading': 'Loading...',
  'sampleItems.error.load': 'Failed to load sample items',
  'sampleItems.error.create': 'Create failed',
  'sampleItems.error.update': 'Update failed',
  'sampleItems.error.delete': 'Delete failed',
}

const esES: Record<string, string> = {
  'sampleItems.action.cancel': 'Cancelar',
  'sampleItems.action.confirm': 'Confirmar',
  'sampleItems.dialog.createTitle': 'Nuevo elemento de ejemplo',
  'sampleItems.dialog.editTitle': 'Editar elemento de ejemplo',
  'sampleItems.dialog.deleteTitle': 'Eliminar elemento de ejemplo',
  'sampleItems.dialog.deleteConfirm': '¿Borrado lógico de «{name}»? Un administrador puede restaurarlo.',
  'sampleItems.title': 'Elementos de ejemplo',
  'sampleItems.description':
    'Ejemplo oficial de capability: aislamiento por tenant, borrado lógico y permisos por botón.',
  'sampleItems.column.code': 'Código',
  'sampleItems.column.name': 'Nombre',
  'sampleItems.column.description': 'Descripción',
  'sampleItems.column.actions': 'Acciones',
  'sampleItems.action.refresh': 'Actualizar',
  'sampleItems.action.create': 'Nuevo',
  'sampleItems.action.edit': 'Editar',
  'sampleItems.action.delete': 'Eliminar',
  'sampleItems.prompt.code': 'Código (minúsculas, dígitos, _ y -)',
  'sampleItems.prompt.name': 'Nombre',
  'sampleItems.prompt.newName': 'Nuevo nombre',
  'sampleItems.empty': 'Sin datos',
  'sampleItems.loading': 'Cargando...',
  'sampleItems.error.load': 'Error al cargar los elementos de ejemplo',
  'sampleItems.error.create': 'Error al crear',
  'sampleItems.error.update': 'Error al actualizar',
  'sampleItems.error.delete': 'Error al eliminar',
}

registerLocaleMessages('zh-CN', zhCN)
registerLocaleMessages('en-US', enUS)
registerLocaleMessages('es-ES', esES)
