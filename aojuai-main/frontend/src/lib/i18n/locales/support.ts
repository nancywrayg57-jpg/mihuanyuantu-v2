/**
 * 工单能力包的语言包。
 *
 * 模块自己维护三份文案并在文件末尾注册，**不改核心语言包**；键一律用 `support.` 前缀。
 * 例外是 `system.moduleCatalog.support.*`：模块开关列表只翻译 `system./common./auth.`
 * 开头的键，所以能力包的目录显示名必须落在 `system.` 命名空间下——但它仍然由本文件
 * 提供，核心语言包不需要为一个可选包留位置。
 *
 * 分类/状态/优先级只从后端拿**取值**，中文/英文/西语标签全在这里：
 * 服务端返回标签就等于 en/es 界面漏中文。
 */
import { registerLocaleMessages } from '../registry'

const zhCN: Record<string, string> = {
  'system.moduleCatalog.support.label': '工单中心',
  'system.moduleCatalog.support.description':
    '可选工单能力：分类/状态/优先级的工单、回复线程、匿名公开提单，并可选桥接公开站留言。默认关闭。',

  'support.tickets.title': '我的工单',
  'support.tickets.description': '提交问题并跟进处理进展。',
  'support.admin.title': '工单管理',
  'support.admin.description': '处理本租户的全部工单：改状态、指派、公开回复或内部备注。',

  'support.action.refresh': '刷新',
  'support.action.create': '提交工单',
  'support.action.cancel': '取消',
  'support.action.confirm': '确定',
  'support.action.view': '查看',
  'support.action.reply': '回复',
  'support.action.send': '发送',
  'support.action.search': '搜索',
  'support.action.clearFilters': '重置筛选',

  'support.column.ticketNo': '工单号',
  'support.column.subject': '标题',
  'support.column.category': '类型',
  'support.column.status': '状态',
  'support.column.priority': '优先级',
  'support.column.requester': '提交人',
  'support.column.assignee': '处理人',
  'support.column.lastMessageAt': '最后更新',
  'support.column.actions': '操作',

  'support.field.subject': '标题',
  'support.field.description': '问题描述',
  'support.field.category': '类型',
  'support.field.priority': '优先级',
  'support.field.status': '状态',
  'support.field.keyword': '关键词',
  'support.field.internalNote': '内部备注',
  'support.field.reply': '回复内容',

  'support.filter.all': '全部',
  'support.filter.unassignedOnly': '仅未指派',

  'support.category.question': '咨询',
  'support.category.incident': '故障',
  'support.category.billing': '计费',
  'support.category.feature': '需求建议',
  'support.category.other': '其他',

  'support.status.open': '待处理',
  'support.status.pending': '等待用户',
  'support.status.resolved': '已解决',
  'support.status.closed': '已关闭',

  'support.priority.low': '低',
  'support.priority.normal': '普通',
  'support.priority.high': '高',
  'support.priority.urgent': '紧急',

  'support.role.user': '用户',
  'support.role.agent': '客服',
  'support.role.visitor': '访客',
  'support.role.system': '系统',

  'support.summary.total': '全部',
  'support.badge.internal': '内部',
  'support.badge.overdue': '已超时',
  'support.detail.title': '工单详情',
  'support.detail.conversation': '沟通记录',
  'support.detail.anonymous': '匿名访客',
  'support.detail.replyInternal': '作为内部备注',
  'support.detail.changeStatus': '同时改为',
  'support.detail.keepStatus': '不改状态',

  'support.empty': '暂无工单',
  'support.loading': '加载中...',
  'support.error.load': '加载工单失败',
  'support.error.create': '提交工单失败',
  'support.error.reply': '回复失败',
  'support.error.update': '更新工单失败',
}

const enUS: Record<string, string> = {
  'system.moduleCatalog.support.label': 'Support Desk',
  'system.moduleCatalog.support.description':
    'Optional help-desk capability: tickets with category/status/priority, reply threads, anonymous public submission, and an optional bridge from public-site contact messages. Disabled by default.',

  'support.tickets.title': 'My Tickets',
  'support.tickets.description': 'Raise an issue and follow its progress.',
  'support.admin.title': 'Ticket Management',
  'support.admin.description':
    'Handle every ticket in this tenant: change status, assign, reply publicly or add internal notes.',

  'support.action.refresh': 'Refresh',
  'support.action.create': 'New ticket',
  'support.action.cancel': 'Cancel',
  'support.action.confirm': 'Confirm',
  'support.action.view': 'View',
  'support.action.reply': 'Reply',
  'support.action.send': 'Send',
  'support.action.search': 'Search',
  'support.action.clearFilters': 'Reset filters',

  'support.column.ticketNo': 'Ticket',
  'support.column.subject': 'Subject',
  'support.column.category': 'Category',
  'support.column.status': 'Status',
  'support.column.priority': 'Priority',
  'support.column.requester': 'Requester',
  'support.column.assignee': 'Assignee',
  'support.column.lastMessageAt': 'Last update',
  'support.column.actions': 'Actions',

  'support.field.subject': 'Subject',
  'support.field.description': 'Description',
  'support.field.category': 'Category',
  'support.field.priority': 'Priority',
  'support.field.status': 'Status',
  'support.field.keyword': 'Keyword',
  'support.field.internalNote': 'Internal note',
  'support.field.reply': 'Reply',

  'support.filter.all': 'All',
  'support.filter.unassignedOnly': 'Unassigned only',

  'support.category.question': 'Question',
  'support.category.incident': 'Incident',
  'support.category.billing': 'Billing',
  'support.category.feature': 'Feature request',
  'support.category.other': 'Other',

  'support.status.open': 'Open',
  'support.status.pending': 'Waiting on user',
  'support.status.resolved': 'Resolved',
  'support.status.closed': 'Closed',

  'support.priority.low': 'Low',
  'support.priority.normal': 'Normal',
  'support.priority.high': 'High',
  'support.priority.urgent': 'Urgent',

  'support.role.user': 'User',
  'support.role.agent': 'Agent',
  'support.role.visitor': 'Visitor',
  'support.role.system': 'System',

  'support.summary.total': 'All',
  'support.badge.internal': 'Internal',
  'support.badge.overdue': 'Overdue',
  'support.detail.title': 'Ticket detail',
  'support.detail.conversation': 'Conversation',
  'support.detail.anonymous': 'Anonymous visitor',
  'support.detail.replyInternal': 'Post as internal note',
  'support.detail.changeStatus': 'Also set status to',
  'support.detail.keepStatus': 'Keep status',

  'support.empty': 'No tickets yet',
  'support.loading': 'Loading...',
  'support.error.load': 'Failed to load tickets',
  'support.error.create': 'Failed to create the ticket',
  'support.error.reply': 'Failed to send the reply',
  'support.error.update': 'Failed to update the ticket',
}

const esES: Record<string, string> = {
  'system.moduleCatalog.support.label': 'Centro de soporte',
  'system.moduleCatalog.support.description':
    'Capacidad opcional de soporte: tickets con categoría/estado/prioridad, hilos de respuesta, envío público anónimo y puente opcional desde los mensajes del sitio público. Desactivado por defecto.',

  'support.tickets.title': 'Mis tickets',
  'support.tickets.description': 'Envía una incidencia y sigue su progreso.',
  'support.admin.title': 'Gestión de tickets',
  'support.admin.description':
    'Gestiona todos los tickets del tenant: cambia el estado, asigna, responde públicamente o añade notas internas.',

  'support.action.refresh': 'Actualizar',
  'support.action.create': 'Nuevo ticket',
  'support.action.cancel': 'Cancelar',
  'support.action.confirm': 'Confirmar',
  'support.action.view': 'Ver',
  'support.action.reply': 'Responder',
  'support.action.send': 'Enviar',
  'support.action.search': 'Buscar',
  'support.action.clearFilters': 'Restablecer filtros',

  'support.column.ticketNo': 'Ticket',
  'support.column.subject': 'Asunto',
  'support.column.category': 'Categoría',
  'support.column.status': 'Estado',
  'support.column.priority': 'Prioridad',
  'support.column.requester': 'Solicitante',
  'support.column.assignee': 'Responsable',
  'support.column.lastMessageAt': 'Última actualización',
  'support.column.actions': 'Acciones',

  'support.field.subject': 'Asunto',
  'support.field.description': 'Descripción',
  'support.field.category': 'Categoría',
  'support.field.priority': 'Prioridad',
  'support.field.status': 'Estado',
  'support.field.keyword': 'Palabra clave',
  'support.field.internalNote': 'Nota interna',
  'support.field.reply': 'Respuesta',

  'support.filter.all': 'Todos',
  'support.filter.unassignedOnly': 'Solo sin asignar',

  'support.category.question': 'Consulta',
  'support.category.incident': 'Incidencia',
  'support.category.billing': 'Facturación',
  'support.category.feature': 'Sugerencia',
  'support.category.other': 'Otro',

  'support.status.open': 'Abierto',
  'support.status.pending': 'Esperando al usuario',
  'support.status.resolved': 'Resuelto',
  'support.status.closed': 'Cerrado',

  'support.priority.low': 'Baja',
  'support.priority.normal': 'Normal',
  'support.priority.high': 'Alta',
  'support.priority.urgent': 'Urgente',

  'support.role.user': 'Usuario',
  'support.role.agent': 'Agente',
  'support.role.visitor': 'Visitante',
  'support.role.system': 'Sistema',

  'support.summary.total': 'Todos',
  'support.badge.internal': 'Interna',
  'support.badge.overdue': 'Vencido',
  'support.detail.title': 'Detalle del ticket',
  'support.detail.conversation': 'Conversación',
  'support.detail.anonymous': 'Visitante anónimo',
  'support.detail.replyInternal': 'Publicar como nota interna',
  'support.detail.changeStatus': 'Cambiar también el estado a',
  'support.detail.keepStatus': 'Mantener el estado',

  'support.empty': 'Todavía no hay tickets',
  'support.loading': 'Cargando...',
  'support.error.load': 'Error al cargar los tickets',
  'support.error.create': 'Error al crear el ticket',
  'support.error.reply': 'Error al enviar la respuesta',
  'support.error.update': 'Error al actualizar el ticket',
}

registerLocaleMessages('zh-CN', zhCN)
registerLocaleMessages('en-US', enUS)
registerLocaleMessages('es-ES', esES)
