/**
 * realphotos 能力包语言包（S0 stub）。
 * 模块开关文案走 system.moduleCatalog.realphotos.*；页面文案后续里程碑扩展。
 */
import { registerLocaleMessages } from '../registry'

const zhCN: Record<string, string> = {
  'system.moduleCatalog.realphotos.label': '蜜獾原图',
  'system.moduleCatalog.realphotos.description':
    '电商商家图片资源、相机参数处理与整数积分流水。默认关闭；安装后启用会话、钱包、网关与队列地基。',
  'realphotos.stub.ready': 'S0 地基已就绪，业务界面将在后续里程碑接入。',
}

const enUS: Record<string, string> = {
  'system.moduleCatalog.realphotos.label': 'Honey Badger Photos',
  'system.moduleCatalog.realphotos.description':
    'Merchant image assets, camera-parameter processing, and integer credit ledger. Disabled by default.',
  'realphotos.stub.ready': 'S0 foundation is ready; product UI arrives in later milestones.',
}

const esES: Record<string, string> = {
  'system.moduleCatalog.realphotos.label': 'Fotos Honey Badger',
  'system.moduleCatalog.realphotos.description':
    'Activos de imagen de comerciantes, parámetros de cámara y ledger de créditos enteros. Desactivado por defecto.',
  'realphotos.stub.ready': 'La base S0 está lista; la UI de producto llega en hitos posteriores.',
}

registerLocaleMessages('zh-CN', zhCN)
registerLocaleMessages('en-US', enUS)
registerLocaleMessages('es-ES', esES)
