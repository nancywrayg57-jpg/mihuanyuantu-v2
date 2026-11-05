import {
  bigint,
  decimal,
  float,
  int,
  json,
  mysqlTable,
  text,
  timestamp,
  tinyint,
  varchar,
} from "drizzle-orm/mysql-core";

/**
 * Core user table backing auth flow.
 */
export const users = mysqlTable("users", {
  id: int("id").autoincrement().primaryKey(),
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  /** 用户名（账号密码登录时使用） */
  username: varchar("username", { length: 64 }).unique(),
  /** 密码哈希（bcrypt，账号密码登录时使用） */
  passwordHash: varchar("passwordHash", { length: 255 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: varchar("role", { length: 32 }).default("user").notNull(),
  /** 每月配额（张数） */
  quota: int("quota").default(1000).notNull(),
  /** 本月已使用配额 */
  quotaUsed: int("quotaUsed").default(0).notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
  /** 登录失败次数（达5次锁定15分钟） */
  loginAttempts: int("loginAttempts").default(0).notNull(),
  /** 账号锁定到期时间 */
  lockedUntil: timestamp("lockedUntil"),
  /** 头像 URL */
  avatar: varchar("avatar", { length: 512 }),
  /** 本地显示名称（与 OAuth 解耦） */
  displayName: varchar("display_name", { length: 128 }),
  /** 本地邮箱（与 OAuth 解耦） */
  localEmail: varchar("local_email", { length: 256 }),
  /** 手机号 */
  phone: varchar("phone", { length: 32 }),
  /** 个人简介 */
  bio: text("bio"),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/**
 * 参数预设表 - 存储完整的EXIF/摄影参数预设
 * 分为手机拍摄和单反相机拍摄两大类
 */
export const parameters = mysqlTable("parameters", {
  id: int("id").autoincrement().primaryKey(),
  /** 预设名称 */
  name: varchar("name", { length: 128 }).notNull(),
  /** 描述 */
  description: text("description"),
  /** AI正向提示词（图生图质感增强） */
  aiPositivePrompt: text("ai_positive_prompt"),
  /** AI负向提示词（图生图质感增强） */
  aiNegativePrompt: text("ai_negative_prompt"),
  /** AI图生图强度（0.05-0.30，按设备类型建议范围） */
  aiStrength: float("ai_strength").default(0.15),
  /** 分类：phone=手机拍摄, dslr=单反相机, mirrorless=微单相机, action=运动相机 */
  category: varchar("category", { length: 32 }).notNull().default("phone"),
  /** 是否为系统内置预设 */
  isDefault: tinyint("is_default").default(0).notNull(),
  /** 使用次数 */
  usageCount: int("usage_count").default(0).notNull(),

  // === 一、基础拍摄核心参数 ===
  /** ISO感光度，如 100, 200, 400, 800, 1600, 3200, 6400 */
  iso: int("iso"),
  /** ISO范围，如 "100-6400" */
  isoRange: varchar("iso_range", { length: 32 }),
  /** 快门速度，如 "1/1000", "1/250", "1/60", "1/30" */
  shutterSpeed: varchar("shutter_speed", { length: 32 }),
  /** 光圈值，如 1.4, 1.8, 2.0, 2.8, 4.0, 5.6, 8.0 */
  aperture: float("aperture"),
  /** EV曝光值，如 0, +0.3, -0.7 */
  evValue: float("ev_value"),
  /** 曝光补偿，如 0, +1, -1 */
  exposureCompensation: float("exposure_compensation"),
  /** 焦距（实际），单位mm，如 24, 35, 50, 85, 135 */
  focalLength: float("focal_length"),
  /** 等效焦距（35mm换算），单位mm */
  focalLengthEquiv: float("focal_length_equiv"),
  /** 对焦距离，单位m，如 0.3, 1.0, 5.0 */
  focusDistance: float("focus_distance"),
  /** 白平衡，如 "Auto", "Daylight", "Cloudy", "Tungsten", "Fluorescent", "Custom" */
  whiteBalance: varchar("white_balance", { length: 64 }),
  /** 色温，单位K，如 5500, 6500, 3000 */
  colorTemperature: int("color_temperature"),
  /** 测光模式：evaluative=评价测光, center=中央重点, spot=点测光, partial=局部测光 */
  meteringMode: varchar("metering_mode", { length: 32 }),
  /** 曝光模式：auto=自动, P=程序自动, A=光圈优先, S=快门优先, M=手动 */
  exposureMode: varchar("exposure_mode", { length: 32 }),
  /** 快门类型：mechanical=机械快门, electronic=电子快门, efcs=电子前帘快门 */
  shutterType: varchar("shutter_type", { length: 32 }),
  /** 场景模式，如 "portrait", "landscape", "sports", "night", "macro", "food" */
  sceneMode: varchar("scene_mode", { length: 64 }),
  /** 色彩模式，如 "standard", "vivid", "neutral", "monochrome" */
  colorMode: varchar("color_mode", { length: 32 }),

  // === 二、设备相关参数 ===
  /** 相机品牌，如 "Canon", "Nikon", "Sony", "Apple", "Samsung", "Huawei" */
  cameraMake: varchar("camera_make", { length: 64 }),
  /** 相机型号，如 "Canon EOS R6 Mark II", "iPhone 15 Pro", "HUAWEI P60 Pro" */
  cameraModel: varchar("camera_model", { length: 128 }),
  /** 镜头品牌，如 "Canon", "Nikon", "Sony", "Sigma" */
  lensMake: varchar("lens_make", { length: 64 }),
  /** 镜头型号，如 "RF 50mm F1.8 STM", "FE 24-70mm F2.8 GM" */
  lensModel: varchar("lens_model", { length: 128 }),
  /** 镜头最大光圈，如 1.4, 1.8, 2.8 */
  lensMaxAperture: float("lens_max_aperture"),
  /** 传感器尺寸，如 "Full Frame 36×24mm", "APS-C 23.5×15.6mm", "1/1.28inch" */
  sensorSize: varchar("sensor_size", { length: 64 }),
  /** 传感器类型：CMOS, CCD */
  sensorType: varchar("sensor_type", { length: 32 }).default("CMOS"),
  /** 闪光灯模式：off=关闭, auto=自动, forced=强制, redeye=红眼消除, slow=慢速同步 */
  flashMode: varchar("flash_mode", { length: 32 }),
  /** 防抖模式：none=无, ois=光学防抖, eis=电子防抖, ibis=机身防抖 */
  stabilization: varchar("stabilization", { length: 32 }),

  // === 三、图像属性参数 ===
  /** 图像宽度（像素），如 4032, 5184, 8064 */
  imageWidth: int("image_width"),
  /** 图像高度（像素），如 3024, 3456, 6048 */
  imageHeight: int("image_height"),
  /** 图像格式：JPEG, RAW, HEIC, PNG */
  imageFormat: varchar("image_format", { length: 32 }).default("JPEG"),
  /** 色彩空间：sRGB, AdobeRGB, ProPhotoRGB, DisplayP3 */
  colorSpace: varchar("color_space", { length: 32 }).default("sRGB"),
  /** 色彩深度（位），如 8, 14, 16 */
  colorDepth: int("color_depth").default(8),
  /** 像素密度（DPI），如 72, 96, 300 */
  pixelDensity: int("pixel_density").default(72),
  /** 图像方向：landscape=横向, portrait=纵向 */
  imageOrientation: varchar("image_orientation", { length: 32 }).default("landscape"),
  /** 压缩比，如 8（JPEG质量系数的倒数） */
  compressionRatio: int("compression_ratio"),

  // === 四、拍摄环境参数 ===
  /** 环境光线（lux），如 50000（晴天室外）, 500（室内）, 10（夜晚） */
  ambientLight: int("ambient_light"),
  /** GPS纬度，如 23.1291 */
  gpsLatitude: decimal("gps_latitude", { precision: 10, scale: 6 }),
  /** GPS经度，如 113.2644 */
  gpsLongitude: decimal("gps_longitude", { precision: 10, scale: 6 }),
  /** GPS海拔（米），如 50.0 */
  gpsAltitude: float("gps_altitude"),
  /** GPS生成模式：none=不写入GPS, fixed=使用固定坐标, random_by_scene=按场景随机生成 */
  gpsMode: varchar("gps_mode", { length: 32 }).default("none"),
  /** 场景类型（用于GPS随机生成）：landscape=风景, urban=城市, indoor=室内, beach=海滩, mountain=山地, street=街拍 */
  sceneType: varchar("scene_type", { length: 32 }).default("urban"),

  // === 四点五、传感器FocalPlane参数（用于EXIF FocalPlaneXResolution等字段）===
  /** FocalPlane X方向分辨率（像素/单位），由机型决定，如 Canon EOS-1D X = 3849.21 */
  focalPlaneXRes: float("focal_plane_x_res"),
  /** FocalPlane Y方向分辨率（像素/单位） */
  focalPlaneYRes: float("focal_plane_y_res"),
  /** FocalPlane分辨率单位：2=英寸, 3=厘米 */
  focalPlaneResUnit: int("focal_plane_res_unit").default(3),
  /** MakerNote模板名称，如 "Canon EOS-1D X", "Nikon D850", "Sony A7R V" */
  makerNoteTemplate: varchar("maker_note_template", { length: 128 }),

  // === 五、后期处理参数 ===
  /** 后期软件，如 "Adobe Lightroom 13.0", "Snapseed 2.21", "无" */
  software: varchar("software", { length: 128 }),
  /** 锐化程度（0-100） */
  sharpening: int("sharpening"),
  /** 降噪程度（0-100） */
  noiseReduction: int("noise_reduction"),

  // === 六、版权与归属参数 ===
  /** 作者 */
  author: varchar("author", { length: 128 }),
  /** 版权信息 */
  copyright: varchar("copyright", { length: 256 }),
  /** 图片描述 */
  imageDescription: text("image_description"),
  /** 关键词（逗号分隔） */
  keywords: text("keywords"),

  // === 七、其他参数 ===
  /** 连拍序列（如 "3/10"） */
  burstSequence: varchar("burst_sequence", { length: 16 }),
  /** 文件编号，如 "DSC_1234" */
  fileNumber: varchar("file_number", { length: 32 }),
  /** RAW格式版本，如 "CR3", "NEF", "ARW" */
  rawVersion: varchar("raw_version", { length: 16 }),

  /** 创建者用户ID；null 表示系统内置/管理员公共预设 */
  userId: varchar("user_id", { length: 128 }),
  /** 是否公开：1=公共预设（所有人可见），0=私有预设（仅所有者可见） */
  isPublic: tinyint("is_public").default(1).notNull(),

  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
  deletedAt: timestamp("deleted_at"),
});

export type Parameter = typeof parameters.$inferSelect;
export type InsertParameter = typeof parameters.$inferInsert;

export const userPromptPresets = mysqlTable("user_prompt_presets", {
  id: int("id").autoincrement().primaryKey(),
  userId: varchar("user_id", { length: 128 }).notNull(),
  name: varchar("name", { length: 128 }).notNull(),
  positive: text("positive"),
  negative: text("negative"),
  sortOrder: int("sort_order").default(0),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
});

export type UserPromptPreset = typeof userPromptPresets.$inferSelect;
export type InsertUserPromptPreset = typeof userPromptPresets.$inferInsert;

/**
 * 生成记录表
 */
export const generationRecords = mysqlTable("generation_records", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("user_id"),
  taskId: varchar("task_id", { length: 64 }),
  sourceFile: varchar("source_file", { length: 256 }),
  /** Original image URL preserved for reprocess/retry flows (text2img: the generated image URL) */
  inputImageUrl: text("input_image_url"),
  outputFile: varchar("output_file", { length: 256 }),
  outputUrl: text("output_url"),
  parameterId: int("parameter_id"),
  status: varchar("status", { length: 32 }).default("pending").notNull(),
  detectionResult: varchar("detection_result", { length: 32 }),
  processingTime: int("processing_time"),
  /** AI image generation time in milliseconds */
  aiProcessTimeMs: int("ai_process_time_ms"),
  errorMessage: text("error_message"),
  prompt: text("prompt"),
  apiProvider: varchar("api_provider", { length: 64 }),
  /** AI detection score from last verification (0-1 decimal) */
  detectionScore: decimal("detection_score", { precision: 5, scale: 4 }),
  /** Detection score from the run before the most recent reprocess */
  lastDetectionScore: decimal("last_detection_score", { precision: 5, scale: 4 }),
  /** Number of times this record has been auto-reprocessed */
  autoReprocessCount: tinyint("auto_reprocess_count").default(0),
  /** Matrix publish status */
  matrixPushStatus: varchar("matrix_push_status", { length: 32 }),
  matrixTaskId: varchar("matrix_task_id", { length: 128 }),
  matrixTargetAccountId: varchar("matrix_target_account_id", { length: 128 }),
  publishUrl: text("publish_url"),
  proofImage: text("proof_image"),
  publishErrorReason: text("publish_error_reason"),
  publishedAt: timestamp("published_at"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
  deletedAt: timestamp("deleted_at"),
});

export type GenerationRecord = typeof generationRecords.$inferSelect;

/**
 * 检测结果表
 */
export const detectionResults = mysqlTable("detection_results", {
  id: int("id").autoincrement().primaryKey(),
  generationId: int("generation_id"),
  platform: varchar("platform", { length: 32 }).default("general"),
  result: varchar("result", { length: 32 }).notNull(),
  confidence: float("confidence"),
  aiScore: float("ai_score"),
  issues: text("issues"),
  suggestions: text("suggestions"),
  retryCount: int("retry_count").default(0),
  /** 噪点和颗粒感评分（0-100） */
  noiseScore: float("noise_score"),
  /** 景深和焦外虚化评分（0-100） */
  depthScore: float("depth_score"),
  /** 光线和曝光自然度评分（0-100） */
  lightingScore: float("lighting_score"),
  /** 色彩真实性评分（0-100） */
  colorScore: float("color_score"),
  /** 整体真实感评分（0-100） */
  overallScore: float("overall_score"),
  /** 使用的AI平台 */
  usedProvider: varchar("used_provider", { length: 64 }),
  /** 使用的AI模型版本 */
  usedModel: varchar("used_model", { length: 128 }),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
});

export type DetectionResult = typeof detectionResults.$inferSelect;

/**
 * API密钥表
 */
export const apiKeys = mysqlTable("api_keys", {
  id: int("id").autoincrement().primaryKey(),
  name: varchar("name", { length: 128 }).notNull(),
  provider: varchar("provider", { length: 32 }).default("gemini"),
  /** 模型版本：由管理员配置，不硬编码。如 gemini-2.5-flash、gpt-5、claude-opus-4-6 */
  modelVersion: varchar("model_version", { length: 128 }),
  keyValue: text("key_value").notNull(),
  status: varchar("status", { length: 32 }).default("active"),
  /** 轮询优先级：high=高优先级，medium=中等，low=低优先级/备用 */
  priority: varchar("priority", { length: 32 }).default("medium"),
  /** 备注说明 */
  remark: varchar("remark", { length: 256 }),
  /** 分组名称，例如「审核用KEY」「生图用KEY」 */
  groupName: varchar("group_name", { length: 128 }),
  /** KEY 用途：verify=EXIF验证，img2img=图生图，image_gen=文生图，ai_optimize=提示词优化；兼容遗留 detection/both */
  keyType: varchar("key_type", { length: 32 }).default("verify"),
  /** API 协议格式：dashscope/openai/gemini/custom */
  apiFormat: varchar("api_format", { length: 32 }).default("dashscope"),
  /** 自定义 base URL，留空则使用默认 endpoint */
  baseUrl: varchar("base_url", { length: 256 }),
  /** 连续失败计数（用于熔断/降级） */
  errorCount: int("error_count").default(0),
  usageCount: int("usage_count").default(0),
  dailyLimit: int("daily_limit").default(1000),
  dailyUsed: int("daily_used").default(0),
  lastUsedAt: timestamp("last_used_at"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
  deletedAt: timestamp("deleted_at"),
});

export type ApiKey = typeof apiKeys.$inferSelect;

/**
 * 用户反馈表
 */
export const userFeedback = mysqlTable("user_feedback", {
  id: int("id").autoincrement().primaryKey(),
  userId: int("user_id"),
  type: varchar("type", { length: 32 }).default("general"),
  title: varchar("title", { length: 256 }),
  content: text("content").notNull(),
  email: varchar("email", { length: 320 }),
  rating: int("rating"),
  status: varchar("status", { length: 32 }).default("pending"),
  adminReply: text("admin_reply"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
  deletedAt: timestamp("deleted_at"),
});

export type UserFeedback = typeof userFeedback.$inferSelect;

/**
 * 更新日志表 - 管理员后台可维护的版本更新记录
 */
export const changelog = mysqlTable("changelog", {
  id: int("id").autoincrement().primaryKey(),
  /** 版本号，如 "1.0.1" */
  version: varchar("version", { length: 32 }).notNull(),
  /** 发布日期，如 "2026-04-08" */
  releaseDate: varchar("release_date", { length: 16 }).notNull(),
  /** 版本标题/摘要 */
  title: varchar("title", { length: 256 }),
  /** 变更内容（JSON 数组，每项为一条变更描述） */
  changes: json("changes").notNull().$type<string[]>(),
  /** 是否发布（false=草稿，true=已发布） */
  published: tinyint("published").default(1).notNull(),
  /** 创建者用户ID */
  createdBy: int("created_by"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow().notNull(),
});

export type Changelog = typeof changelog.$inferSelect;
export type InsertChangelog = typeof changelog.$inferInsert;
