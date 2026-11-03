/**
 * 参数预设序列化边界（snake_case 数据库行 → 前端期望的 camelCase）。
 *
 * 背景（Issue #7）：数据库中存在 GPS 模式（gps_mode）与 MakerNote 模板
 * （maker_note_template）等字段，但列表/详情/编辑渲染曾因映射遗漏而显示为空或
 * “无”。此前修复已把这些字段补进内联映射，但映射逻辑内联在 tRPC 路由里、无法
 * 单测，任何后续重构都可能再次静默丢字段。这里把序列化收敛到唯一可测试边界，
 * 保证 snake_case 原值与 camelCase 别名同时存在，杜绝再次“mapping loss”。
 *
 * 约束：不引入数据库 ENUM，值统一按 varchar + 应用层数据字典处理；不使用 any。
 */

/** 数据库原始行（列名为 snake_case），值类型未知，按边界安全读取。 */
export type ParameterDbRow = Record<string, unknown>;

/**
 * 将单条数据库预设行序列化为前端可直接消费的对象。
 *
 * - 通过 `...row` 保留所有原始 snake_case 列（列表表格与编辑对话框直接读取
 *   `gps_mode` / `maker_note_template` 等原始字段）。
 * - 额外补充 camelCase 别名，兼容按 camelCase 读取的调用方。
 * - GPS 模式与 MakerNote 模板是本次重点保障字段，显式映射，禁止遗漏。
 *
 * 泛型透传行的静态类型：既能对 `Record<string, unknown>` 做安全读取（单测场景），
 * 又能保留 mysql RowDataPacket 原有的宽松列类型，不改变既有下游调用方的类型推断。
 */
export function mapParameterRow<Row extends ParameterDbRow>(row: Row) {
  return {
    ...row,
    // 基础拍摄参数
    shutterSpeed: row.shutter_speed,
    shutterType: row.shutter_type,
    evValue: row.ev_value,
    focalLength: row.focal_length,
    focalLengthEquiv: row.focal_length_equiv,
    focusDistance: row.focus_distance,
    whiteBalance: row.white_balance,
    colorTemperature: row.color_temperature,
    meteringMode: row.metering_mode,
    exposureMode: row.exposure_mode,
    exposureCompensation: row.exposure_compensation,
    sceneMode: row.scene_mode,
    // 设备信息
    cameraMake: row.camera_make,
    cameraModel: row.camera_model,
    lensMake: row.lens_make,
    lensModel: row.lens_model,
    lensMaxAperture: row.lens_max_aperture,
    sensorSize: row.sensor_size,
    sensorType: row.sensor_type,
    flashMode: row.flash_mode,
    // 图像属性
    imageWidth: row.image_width,
    imageHeight: row.image_height,
    imageFormat: row.image_format,
    colorSpace: row.color_space,
    colorDepth: row.color_depth,
    pixelDensity: row.pixel_density,
    imageOrientation: row.image_orientation,
    compressionRatio: row.compression_ratio,
    colorMode: row.color_mode,
    // GPS信息（Issue #7 重点保障：模式与坐标必须完整映射）
    gpsLatitude: row.gps_latitude,
    gpsLongitude: row.gps_longitude,
    gpsAltitude: row.gps_altitude,
    gpsMode: row.gps_mode,
    sceneType: row.scene_type,
    // FocalPlane
    focalPlaneXRes: row.focal_plane_x_res,
    focalPlaneYRes: row.focal_plane_y_res,
    focalPlaneResUnit: row.focal_plane_res_unit,
    // MakerNote（Issue #7 重点保障：模板字段必须完整映射）
    makerNoteTemplate: row.maker_note_template,
    // AI提示词
    aiPositivePrompt: row.ai_positive_prompt,
    aiNegativePrompt: row.ai_negative_prompt,
    aiStrength: row.ai_strength,
    // 版权
    imageDescription: row.image_description,
    // IP-GEO
    ip_geo: row.ip_geo,
    // 多租户隔离
    isPublic: row.is_public === 1 || row.is_public === true,
    ownerId: row.user_id,
    // 元数据
    isDefault: row.is_default,
    usageCount: row.usage_count,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}
