export const USER_ROLES = ["user", "admin"] as const;

export const GENERATION_STATUSES = ["pending", "processing", "completed", "failed"] as const;
export const GENERATION_DETECTION_RESULTS = ["pass", "fail", "pending"] as const;

export const DETECTION_PLATFORMS = ["tiktok", "xiaohongshu", "instagram", "general"] as const;
export const DETECTION_RESULTS = ["pass", "fail", "warning"] as const;

export const PARAMETER_CATEGORIES = ["phone", "dslr", "mirrorless", "action"] as const;
export const PARAMETER_METERING_MODES = ["evaluative", "center", "spot", "partial"] as const;
export const PARAMETER_EXPOSURE_MODES = ["auto", "P", "A", "S", "M"] as const;
export const PARAMETER_SHUTTER_TYPES = ["mechanical", "electronic", "efcs"] as const;
export const PARAMETER_SENSOR_TYPES = ["CMOS", "CCD"] as const;
export const PARAMETER_FLASH_MODES = ["off", "auto", "forced", "redeye", "slow"] as const;
export const PARAMETER_STABILIZATION_TYPES = ["none", "ois", "eis", "ibis"] as const;
export const PARAMETER_IMAGE_FORMATS = ["JPEG", "RAW", "HEIC", "PNG"] as const;
export const PARAMETER_COLOR_SPACES = ["sRGB", "AdobeRGB", "ProPhotoRGB", "DisplayP3"] as const;
export const PARAMETER_IMAGE_ORIENTATIONS = ["landscape", "portrait"] as const;
export const PARAMETER_GPS_MODES = ["none", "fixed", "random_by_scene"] as const;
export const PARAMETER_SCENE_TYPES = ["landscape", "urban", "indoor", "beach", "mountain", "street"] as const;

// Issue #8：provider 不再是封闭白名单。运行时 provider 为「格式校验的开放字符串」，
// 平台元数据（label / 默认模型 / 协议族 / 默认 endpoint）统一来自
// shared/aiProviderCatalog.ts（AI_PROVIDER_CATALOG，应用层数据字典 SSOT）。
// 下面这份列表仅保留为「内置平台标识」的历史参考，不再作为创建/更新的写入门禁。
export const API_KEY_PROVIDERS = [
  "gemini",
  "openai",
  "claude",
  "deepseek",
  "kimi",
  "doubao",
  "qwen",
  "zhipu",
  "midjourney",
  "other",
] as const;
export const API_KEY_STATUSES = ["active", "inactive", "expired"] as const;
export const API_KEY_PRIORITIES = ["high", "medium", "low"] as const;
// API KEY 用途分组（Issue #7 规范）：
//   verify       = EXIF / 真实性检测
//   img2img      = AI 图生图
//   image_gen    = 文生图 / 图像生成
//   ai_optimize  = AI 提示词优化
//
// 这四个值是当前唯一允许新建 / 写入 / 选择的规范化 key_type。
// 历史遗留值 `detection`（旧 EXIF 检测分组）、`both`（旧的"检测+图生图"混用 KEY）
// 仅保留在 LEGACY_API_KEY_TYPES，用于显示数据库中已存在的存量数据；
// 创建/更新接口和运行时调度均不接受 legacy 值。
export const CANONICAL_API_KEY_TYPES = [
  "verify",
  "img2img",
  "image_gen",
  "ai_optimize",
] as const;
export const LEGACY_API_KEY_TYPES = ["detection", "both"] as const;
/**
 * 全量 key_type 字面量集合，仅用于读取/展示存量数据库行。
 * 新建/更新调用方禁止使用此集合，请改用 CANONICAL_API_KEY_TYPES。
 */
export const API_KEY_TYPES = [
  ...CANONICAL_API_KEY_TYPES,
  ...LEGACY_API_KEY_TYPES,
] as const;

/** 运行时选择 verify 用途 KEY，仅匹配规范化值 verify。 */
export const VERIFY_KEY_TYPES = ["verify"] as const;
/** 运行时选择 img2img 用途 KEY，仅匹配规范化值 img2img。 */
export const IMG2IMG_KEY_TYPES = ["img2img"] as const;
/** 运行时选择 image_gen 用途 KEY，仅匹配规范化值 image_gen。 */
export const IMAGE_GEN_KEY_TYPES = ["image_gen"] as const;
/** 运行时选择 ai_optimize 用途 KEY，仅匹配规范化值 ai_optimize。 */
export const AI_OPTIMIZE_KEY_TYPES = ["ai_optimize"] as const;
export const API_KEY_FORMATS = ["dashscope", "openai", "gemini", "custom"] as const;

export const FEEDBACK_TYPES = ["bug", "feature", "general"] as const;
export const FEEDBACK_STATUSES = ["pending", "processing", "resolved", "closed"] as const;
