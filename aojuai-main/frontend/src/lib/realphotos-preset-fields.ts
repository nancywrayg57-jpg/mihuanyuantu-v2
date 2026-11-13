/** Device preset form/detail fields aligned to legacy 55-key map + admin copyright ledger.
 * IP-GEO remains excluded. Prototype-only keys (lighting/background/post_processing) removed.
 * Selectable params use options from realphotos-preset-options (legacy UI candidates).
 */

import { PRESET_SELECT_FIELD_KEYS } from '@/lib/realphotos-preset-options'

export type PresetFieldDef = {
  key: string
  label: string
  /** Maps into legacyParameters unless column/top-level */
  group: 'basic' | 'shooting' | 'exif' | 'ai' | 'copyright'
  kind?: 'text' | 'textarea' | 'select'
  options?: { value: string; label: string }[]
  required?: boolean
  /** Bound to row-level column instead of legacyParameters */
  column?:
    | 'code'
    | 'deviceType'
    | 'brand'
    | 'model'
    | 'iso'
    | 'shutter'
    | 'aperture'
    | 'focalLength'
    | 'gpsMode'
    | 'makerNote'
    | 'aiPositivePrompt'
    | 'aiNegativePrompt'
  /** Hide from create/edit form (still may appear in detail when valued) */
  formHidden?: boolean
}

export const PRESET_FORM_TABS: { id: 'basic' | 'shooting' | 'exif' | 'ai' | 'copyright'; label: string }[] = [
  { id: 'basic', label: '基本信息' },
  { id: 'shooting', label: '拍摄参数' },
  { id: 'exif', label: 'EXIF 增强' },
  { id: 'ai', label: 'AI 提示词' },
  { id: 'copyright', label: '版权信息' },
]

export const GPS_COORD_LABELS = {
  latitude: '纬度',
  longitude: '经度',
  altitude: '海拔(m)',
} as const

function withSelectKind(def: PresetFieldDef): PresetFieldDef {
  if (def.kind === 'textarea' || def.kind === 'select') return def
  if (PRESET_SELECT_FIELD_KEYS.has(def.key) || (def.column && PRESET_SELECT_FIELD_KEYS.has(def.column))) {
    return { ...def, kind: 'select' }
  }
  return def
}

const RAW_PRESET_FIELD_DEFS: PresetFieldDef[] = [
  // basic — 展示用「预设名称」；内部 code 仅编辑时只读隐藏（API 主键）
  { key: 'name', label: '预设名称', group: 'basic', required: true },
  { key: 'code', label: '内部编码', group: 'basic', column: 'code', formHidden: true },
  { key: 'description', label: '描述', group: 'basic', kind: 'textarea' },
  {
    key: 'deviceType',
    label: '设备类别',
    group: 'basic',
    column: 'deviceType',
    kind: 'select',
    required: true,
    options: [
      { value: 'phone', label: '手机' },
      { value: 'dslr', label: '单反' },
      { value: 'mirrorless', label: '无反' },
      { value: 'action', label: '运动相机' },
    ],
  },
  { key: 'brand', label: '品牌', group: 'basic', column: 'brand', required: true },
  { key: 'model', label: '型号', group: 'basic', column: 'model', required: true },
  { key: 'is_public', label: '可见性', group: 'basic' },

  // shooting — core + legacy
  { key: 'iso', label: 'ISO', group: 'shooting', column: 'iso', required: true },
  { key: 'shutter', label: '快门', group: 'shooting', column: 'shutter', required: true },
  { key: 'aperture', label: '光圈', group: 'shooting', column: 'aperture', required: true },
  { key: 'focalLength', label: '焦距', group: 'shooting', column: 'focalLength', required: true },
  { key: 'focal_length_equiv', label: '等效焦距', group: 'shooting' },
  { key: 'ev_value', label: 'EV 值', group: 'shooting' },
  { key: 'white_balance', label: '白平衡', group: 'shooting' },
  { key: 'metering_mode', label: '测光模式', group: 'shooting' },
  { key: 'exposure_mode', label: '曝光模式', group: 'shooting' },
  { key: 'iso_range', label: 'ISO 范围', group: 'shooting' },
  { key: 'shutter_type', label: '快门类型', group: 'shooting' },
  { key: 'exposure_compensation', label: '曝光补偿', group: 'shooting' },
  { key: 'focus_distance', label: '对焦距离', group: 'shooting' },
  { key: 'color_temperature', label: '色温 (K)', group: 'shooting' },
  { key: 'scene_mode', label: '场景模式', group: 'shooting' },
  { key: 'color_mode', label: '色彩模式', group: 'shooting' },
  { key: 'lens_make', label: '镜头品牌', group: 'shooting' },
  { key: 'lens_model', label: '镜头型号', group: 'shooting' },
  { key: 'sensor_size', label: '传感器尺寸', group: 'shooting' },
  { key: 'sensor_type', label: '传感器类型', group: 'shooting' },
  { key: 'stabilization', label: '防抖', group: 'shooting' },
  { key: 'lens_max_aperture', label: '镜头最大光圈', group: 'shooting' },
  { key: 'flash_mode', label: '闪光模式', group: 'shooting' },
  { key: 'ambient_light', label: '环境光', group: 'shooting' },
  { key: 'image_width', label: '图像宽度', group: 'shooting' },
  { key: 'image_height', label: '图像高度', group: 'shooting' },
  { key: 'color_depth', label: '色深', group: 'shooting' },
  { key: 'image_format', label: '图像格式', group: 'shooting' },
  { key: 'color_space', label: '色彩空间', group: 'shooting' },
  { key: 'software', label: '软件', group: 'shooting' },
  { key: 'pixel_density', label: '像素密度', group: 'shooting' },
  { key: 'image_orientation', label: '图像方向', group: 'shooting' },
  { key: 'compression_ratio', label: '压缩比', group: 'shooting' },
  { key: 'sharpening', label: '锐化', group: 'shooting' },
  { key: 'noise_reduction', label: '降噪', group: 'shooting' },
  { key: 'image_description', label: '图像描述', group: 'shooting' },
  { key: 'keywords', label: '关键词', group: 'shooting' },

  // exif
  {
    key: 'gpsMode',
    label: 'GPS 模式',
    group: 'exif',
    column: 'gpsMode',
    kind: 'select',
    options: [
      { value: 'none', label: '不写入 GPS' },
      { value: 'fixed', label: '固定坐标（手动填写）' },
      { value: 'random_by_scene', label: '按场景随机生成' },
    ],
  },
  { key: 'scene_type', label: 'GPS 场景类型', group: 'exif' },
  { key: 'makerNote', label: 'MakerNote', group: 'exif', column: 'makerNote' },
  { key: 'focal_plane_x_res', label: '焦平面 X 分辨率', group: 'exif' },
  { key: 'focal_plane_y_res', label: '焦平面 Y 分辨率', group: 'exif' },
  { key: 'focal_plane_res_unit', label: '焦平面分辨率单位', group: 'exif' },
  { key: 'burst_sequence', label: '连拍序号', group: 'exif' },
  { key: 'file_number', label: '文件编号', group: 'exif' },
  { key: 'raw_version', label: 'RAW 版本', group: 'exif' },

  // ai
  { key: 'aiPositivePrompt', label: '正向提示词', group: 'ai', column: 'aiPositivePrompt', kind: 'textarea' },
  { key: 'aiNegativePrompt', label: '负向提示词', group: 'ai', column: 'aiNegativePrompt', kind: 'textarea' },
  { key: 'ai_strength', label: 'AI 强度', group: 'ai' },
  { key: 'ai_img2img_strength', label: '图生图强度', group: 'ai' },

  // copyright — admin ledger (IP-GEO still excluded)
  { key: 'author', label: '作者', group: 'copyright' },
  { key: 'copyright', label: '版权声明', group: 'copyright', kind: 'textarea' },
]

export const PRESET_FIELD_DEFS: PresetFieldDef[] = RAW_PRESET_FIELD_DEFS.map(withSelectKind)

/** Legacy parameter keys that sync into row columns on save */
export const LEGACY_TO_COLUMN: Record<string, string> = {
  camera_make: 'brand',
  camera_model: 'model',
  iso: 'iso',
  shutter_speed: 'shutter',
  aperture: 'aperture',
  focal_length: 'focalLength',
  gps_mode: 'gpsMode',
  maker_note_template: 'makerNote',
  ai_positive_prompt: 'aiPositivePrompt',
  ai_negative_prompt: 'aiNegativePrompt',
}

/** Still stripped on save / never shown as form fields */
export const EXCLUDED_IP_GEO_KEYS = ['ip_geo', 'ipGeo'] as const

/** @deprecated use EXCLUDED_IP_GEO_KEYS; author/copyright now editable in admin ledger */
export const EXCLUDED_COPYRIGHT_KEYS = ['ip_geo', 'ipGeo'] as const

export const REMOVED_PROTOTYPE_ONLY_KEYS = ['lighting', 'background', 'post_processing'] as const

export function presetDisplayName(preset: {
  name?: string | null
  code?: string
  brand?: string
  model?: string
  legacyParameters?: Record<string, unknown> | null
}): string {
  const fromTop = String(preset.name || '').trim()
  if (fromTop) return fromTop
  const fromLegacy = String(preset.legacyParameters?.name || '').trim()
  if (fromLegacy) return fromLegacy
  const brand = String(preset.brand || '').trim()
  const model = String(preset.model || '').trim()
  if (brand || model) return [brand, model].filter(Boolean).join(' ')
  return String(preset.code || '').trim() || '未命名预设'
}
