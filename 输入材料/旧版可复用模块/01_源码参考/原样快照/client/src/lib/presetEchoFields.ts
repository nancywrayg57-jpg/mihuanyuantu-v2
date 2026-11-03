/**
 * 参数预设 GPS 模式 / MakerNote 字段回显与保留逻辑（Issue #7）。
 *
 * 这些字段在 数据库 -> tRPC -> 前端 链路里曾因 snake_case / camelCase 映射遗漏而
 * 在列表/详情/编辑渲染时显示为空或“无”。此模块把三处易错的映射逻辑收敛为可单测
 * 的纯函数：
 *   1. resolvePresetEchoFields —— 列表行归一化（同时兼容 snake / camel 来源）；
 *   2. toEditFormEcho         —— 打开编辑对话框时回填表单；
 *   3. toUpdatePayloadEcho    —— 提交更新时按“未改动即保留”语义构造 payload。
 *
 * 约束：不使用 any；GPS 模式与场景类型是有效字符串枚举值（如 "none" / "urban"），
 * 不能用 `|| undefined` 误判为 falsy 而丢失，统一使用 `?? undefined`。
 */

/** 列表接口返回行：GPS / MakerNote 相关字段可能以 snake 或 camel 形式到达。 */
export interface PresetEchoSource {
  gps_mode?: string | null;
  gpsMode?: string | null;
  scene_type?: string | null;
  sceneType?: string | null;
  gps_latitude?: string | number | null;
  gpsLatitude?: string | number | null;
  gps_longitude?: string | number | null;
  gpsLongitude?: string | number | null;
  gps_altitude?: string | number | null;
  gpsAltitude?: string | number | null;
  maker_note_template?: string | null;
  makerNoteTemplate?: string | null;
}

/** 归一化后的回显字段（统一 snake_case，供表格渲染与编辑对话框读取）。 */
export interface PresetEchoFields {
  gps_mode: string;
  scene_type: string;
  gps_latitude: string | number | null;
  gps_longitude: string | number | null;
  gps_altitude: string | number | null;
  maker_note_template: string;
}

/**
 * 归一化列表行的 GPS/MakerNote 字段：优先取 snake_case 原值，回退 camelCase 别名，
 * 最终回退到安全默认值（gps_mode=none / scene_type=urban / maker_note_template=""）。
 */
export function resolvePresetEchoFields(row: PresetEchoSource): PresetEchoFields {
  return {
    gps_mode: row.gps_mode ?? row.gpsMode ?? "none",
    scene_type: row.scene_type ?? row.sceneType ?? "urban",
    gps_latitude: row.gps_latitude ?? row.gpsLatitude ?? null,
    gps_longitude: row.gps_longitude ?? row.gpsLongitude ?? null,
    gps_altitude: row.gps_altitude ?? row.gpsAltitude ?? null,
    maker_note_template: row.maker_note_template ?? row.makerNoteTemplate ?? "",
  };
}

/** 编辑对话框回填所需的预设字段（已由 resolvePresetEchoFields 归一化为 snake_case）。 */
export interface PresetEditSource {
  gps_mode?: string | null;
  scene_type?: string | null;
  gps_latitude?: string | number | null;
  gps_longitude?: string | number | null;
  gps_altitude?: string | number | null;
  maker_note_template?: string | null;
}

/** 编辑表单里的 GPS/MakerNote 字段（全部为受控字符串）。 */
export interface PresetEditFormEcho {
  gps_mode: string;
  scene_type: string;
  gps_latitude: string;
  gps_longitude: string;
  gps_altitude: string;
  maker_note_template: string;
}

/**
 * 打开编辑对话框时，把预设回显到编辑表单：GPS 模式 / 场景类型 / MakerNote 直接回填，
 * 坐标转为字符串以适配受控 Input。保证已有值不会显示为空。
 */
export function toEditFormEcho(preset: PresetEditSource): PresetEditFormEcho {
  return {
    gps_mode: preset.gps_mode ?? "none",
    scene_type: preset.scene_type ?? "urban",
    gps_latitude: String(preset.gps_latitude ?? ""),
    gps_longitude: String(preset.gps_longitude ?? ""),
    gps_altitude: String(preset.gps_altitude ?? ""),
    maker_note_template: preset.maker_note_template ?? "",
  };
}

/** 提交更新时构造的 GPS/MakerNote payload 片段。 */
export interface PresetUpdateEcho {
  gps_mode: string | undefined;
  scene_type: string | undefined;
  gps_latitude: number | undefined;
  gps_longitude: number | undefined;
  gps_altitude: number | undefined;
  maker_note_template: string | undefined;
}

/**
 * 提交更新时构造 payload：GPS 模式 / 场景类型 / MakerNote 用 `?? undefined`
 * （而非 `|| undefined`），确保 "none" / "urban" 等有效枚举值以及用户显式清空
 * （空字符串，后端会转为 null）都能被正确保存，未改动字段保持原值。
 */
export function toUpdatePayloadEcho(form: PresetEditFormEcho): PresetUpdateEcho {
  return {
    gps_mode: form.gps_mode ?? undefined,
    scene_type: form.scene_type ?? undefined,
    gps_latitude: form.gps_latitude ? Number(form.gps_latitude) : undefined,
    gps_longitude: form.gps_longitude ? Number(form.gps_longitude) : undefined,
    gps_altitude: form.gps_altitude ? Number(form.gps_altitude) : undefined,
    maker_note_template: form.maker_note_template ?? undefined,
  };
}
