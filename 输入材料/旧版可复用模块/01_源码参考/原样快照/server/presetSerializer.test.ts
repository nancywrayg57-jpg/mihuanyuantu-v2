/**
 * 参数预设序列化边界测试（Issue #7）。
 *
 * 重点回归：数据库中存在 GPS 模式（gps_mode）与 MakerNote 模板
 * （maker_note_template）时，序列化后必须同时保留 snake_case 原值与 camelCase
 * 别名，杜绝列表/详情/编辑渲染因映射遗漏而丢字段。
 */
import { describe, it, expect } from "vitest";
import { mapParameterRow, type ParameterDbRow } from "./presetSerializer";

function makeRow(overrides: ParameterDbRow = {}): ParameterDbRow {
  return {
    id: 1,
    name: "Canon 单反预设",
    category: "dslr",
    gps_mode: "random_by_scene",
    scene_type: "urban",
    gps_latitude: "23.129100",
    gps_longitude: "113.264400",
    gps_altitude: 50,
    maker_note_template: "Canon EOS R5",
    camera_make: "Canon",
    camera_model: "EOS R5",
    is_public: 1,
    user_id: 7,
    ...overrides,
  };
}

describe("mapParameterRow - GPS 模式序列化", () => {
  it("保留 gps_mode 原始 snake_case 值（列表表格 / 编辑对话框直接读取）", () => {
    const out = mapParameterRow(makeRow());
    expect(out.gps_mode).toBe("random_by_scene");
  });

  it("补充 gpsMode camelCase 别名（兼容按 camelCase 读取的调用方）", () => {
    const out = mapParameterRow(makeRow());
    expect(out.gpsMode).toBe("random_by_scene");
  });

  it("fixed 模式与坐标一并保留", () => {
    const out = mapParameterRow(
      makeRow({ gps_mode: "fixed", gps_latitude: "37.774900", gps_longitude: "-122.419400" }),
    );
    expect(out.gps_mode).toBe("fixed");
    expect(out.gpsMode).toBe("fixed");
    expect(out.gps_latitude).toBe("37.774900");
    expect(out.gpsLatitude).toBe("37.774900");
    expect(out.gps_longitude).toBe("-122.419400");
    expect(out.gpsLongitude).toBe("-122.419400");
    expect(out.gps_altitude).toBe(50);
    expect(out.gpsAltitude).toBe(50);
  });

  it("场景类型 scene_type 同时映射为 sceneType", () => {
    const out = mapParameterRow(makeRow({ scene_type: "beach" }));
    expect(out.scene_type).toBe("beach");
    expect(out.sceneType).toBe("beach");
  });

  it("legacy 行 gps_mode 为 null 时保持 null，不臆造默认值（默认值由前端归一化决定）", () => {
    const out = mapParameterRow(makeRow({ gps_mode: null }));
    expect(out.gps_mode).toBeNull();
    expect(out.gpsMode).toBeNull();
  });
});

describe("mapParameterRow - MakerNote 序列化", () => {
  it("保留 maker_note_template 原始值（列表 / 编辑回显）", () => {
    const out = mapParameterRow(makeRow());
    expect(out.maker_note_template).toBe("Canon EOS R5");
  });

  it("补充 makerNoteTemplate camelCase 别名", () => {
    const out = mapParameterRow(makeRow());
    expect(out.makerNoteTemplate).toBe("Canon EOS R5");
  });

  it("空 MakerNote（未配置）保持原样，不丢字段", () => {
    const out = mapParameterRow(makeRow({ maker_note_template: null }));
    expect(out.maker_note_template).toBeNull();
    expect(out.makerNoteTemplate).toBeNull();
  });
});

describe("mapParameterRow - 权限与租户边界不受影响", () => {
  it("is_public=1 序列化为 isPublic=true", () => {
    const out = mapParameterRow(makeRow({ is_public: 1 }));
    expect(out.isPublic).toBe(true);
  });

  it("is_public=0 序列化为 isPublic=false（私有预设隔离标记保留）", () => {
    const out = mapParameterRow(makeRow({ is_public: 0 }));
    expect(out.isPublic).toBe(false);
  });

  it("ownerId 来源于 user_id，供前端归属判断", () => {
    const out = mapParameterRow(makeRow({ user_id: 42 }));
    expect(out.ownerId).toBe(42);
  });
});
