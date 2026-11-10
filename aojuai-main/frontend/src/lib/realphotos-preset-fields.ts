/** Device preset form/detail fields aligned to prototype tabs ∩ legacy 55-key map.
 * Copyright / IP-GEO excluded per PRD. Prototype-only keys marked sparse (empty ok, no fake legacy).
 */

export type PresetFieldDef = {
  key: string
  label: string
  /** Maps into legacyParameters unless column/top-level */
  group: 'basic' | 'shooting' | 'exif' | 'ai' | 'copyright_excluded'
  kind?: 'text' | 'textarea' | 'select'
  options?: { value: string; label: string }[]
  required?: boolean
  /** Not in legacy 55-key map / rare — show empty honestly, do not invent */
  sparse?: boolean
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
}

export const PRESET_FORM_TABS: { id: 'basic' | 'shooting' | 'exif' | 'ai' | 'copyright_excluded'; label: string }[] = [
  { id: 'basic', label: '基本信息' },
  { id: 'shooting', label: '拍摄参数' },
  { id: 'exif', label: 'EXIF 增强' },
  { id: 'ai', label: 'AI 提示词' },
  { id: 'copyright_excluded', label: '版权信息' },
]

export const PRESET_FIELD_DEFS: PresetFieldDef[] = [
  // basic
  { key: 'code', label: '预设编号', group: 'basic', column: 'code', required: true },
  { key: 'name', label: '预设名称', group: 'basic' },
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
  { key: 'is_public', label: '可见性（旧版键极少）', group: 'basic', sparse: true },

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
  { key: 'lighting', label: '光线条件（原型有 / 旧版 55 键无）', group: 'shooting', sparse: true },
  { key: 'background', label: '背景（原型有 / 旧版 55 键无）', group: 'shooting', sparse: true },
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
  { key: 'post_processing', label: '后期处理（原型有 / 旧版 55 键无）', group: 'shooting', sparse: true },
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
      { value: 'none', label: '不写入' },
      { value: 'fixed', label: '固定坐标' },
      { value: 'random_by_scene', label: '按场景随机' },
    ],
  },
  { key: 'scene_type', label: 'GPS 场景类型', group: 'exif' },
  { key: 'makerNote', label: 'MakerNote', group: 'exif', column: 'makerNote', kind: 'textarea' },
  { key: 'focal_plane_x_res', label: 'FocalPlane X', group: 'exif' },
  { key: 'focal_plane_y_res', label: 'FocalPlane Y', group: 'exif' },
  { key: 'focal_plane_res_unit', label: 'FocalPlane 单位', group: 'exif' },
  { key: 'burst_sequence', label: '连拍序号', group: 'exif' },
  { key: 'file_number', label: '文件编号', group: 'exif' },
  { key: 'raw_version', label: 'RAW 版本', group: 'exif' },

  // ai
  { key: 'aiPositivePrompt', label: '正向提示词', group: 'ai', column: 'aiPositivePrompt', kind: 'textarea' },
  { key: 'aiNegativePrompt', label: '负向提示词', group: 'ai', column: 'aiNegativePrompt', kind: 'textarea' },
  { key: 'ai_strength', label: 'AI 强度', group: 'ai' },
  { key: 'ai_img2img_strength', label: '图生图强度', group: 'ai' },

  // excluded — display only
  { key: 'author', label: '作者（PRD 排除）', group: 'copyright_excluded', sparse: true },
  { key: 'copyright', label: '版权声明（PRD 排除）', group: 'copyright_excluded', sparse: true },
]

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

export const EXCLUDED_COPYRIGHT_KEYS = ['author', 'copyright', 'ip_geo', 'ipGeo'] as const

export const SPARSE_PROTOTYPE_ONLY_KEYS = ['lighting', 'background', 'post_processing', 'is_public', 'prompt_template_id', 'is_default'] as const
