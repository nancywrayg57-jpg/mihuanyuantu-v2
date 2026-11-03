/**
 * 前端 GPS 模式 / MakerNote 回显与保留逻辑测试（Issue #7）。
 *
 * 覆盖：列表行归一化（snake / camel 双来源）、编辑对话框回填、提交更新时的
 * “未改动即保留”语义。
 */
import { describe, it, expect } from "vitest";
import {
  resolvePresetEchoFields,
  toEditFormEcho,
  toUpdatePayloadEcho,
} from "./presetEchoFields";

describe("resolvePresetEchoFields - 列表行归一化", () => {
  it("snake_case 来源：保留 gps_mode 与 maker_note_template", () => {
    const out = resolvePresetEchoFields({
      gps_mode: "random_by_scene",
      scene_type: "beach",
      gps_latitude: "23.129100",
      gps_longitude: "113.264400",
      gps_altitude: 50,
      maker_note_template: "Canon EOS R5",
    });
    expect(out.gps_mode).toBe("random_by_scene");
    expect(out.scene_type).toBe("beach");
    expect(out.gps_latitude).toBe("23.129100");
    expect(out.gps_longitude).toBe("113.264400");
    expect(out.gps_altitude).toBe(50);
    expect(out.maker_note_template).toBe("Canon EOS R5");
  });

  it("仅 camelCase 来源：仍能解析出 gps_mode 与 maker_note_template（映射不丢失）", () => {
    const out = resolvePresetEchoFields({
      gpsMode: "fixed",
      sceneType: "urban",
      gpsLatitude: "37.774900",
      gpsLongitude: "-122.419400",
      gpsAltitude: 12,
      makerNoteTemplate: "Nikon D850",
    });
    expect(out.gps_mode).toBe("fixed");
    expect(out.scene_type).toBe("urban");
    expect(out.gps_latitude).toBe("37.774900");
    expect(out.maker_note_template).toBe("Nikon D850");
  });

  it("snake_case 优先于 camelCase 别名", () => {
    const out = resolvePresetEchoFields({
      gps_mode: "fixed",
      gpsMode: "none",
      maker_note_template: "Sony A7R V",
      makerNoteTemplate: "",
    });
    expect(out.gps_mode).toBe("fixed");
    expect(out.maker_note_template).toBe("Sony A7R V");
  });

  it("缺省时回退安全默认值：gps_mode=none / scene_type=urban / maker_note_template=空", () => {
    const out = resolvePresetEchoFields({});
    expect(out.gps_mode).toBe("none");
    expect(out.scene_type).toBe("urban");
    expect(out.gps_latitude).toBeNull();
    expect(out.maker_note_template).toBe("");
  });

  it("legacy 行 gps_mode / maker_note_template 为 null 时回退默认值", () => {
    const out = resolvePresetEchoFields({ gps_mode: null, maker_note_template: null });
    expect(out.gps_mode).toBe("none");
    expect(out.maker_note_template).toBe("");
  });
});

describe("toEditFormEcho - 编辑对话框回填", () => {
  it("已有 GPS 模式与 MakerNote 值应回填到表单（不显示为空）", () => {
    const form = toEditFormEcho({
      gps_mode: "fixed",
      scene_type: "mountain",
      gps_latitude: "23.129100",
      gps_longitude: "113.264400",
      gps_altitude: 50,
      maker_note_template: "Canon EOS R5",
    });
    expect(form.gps_mode).toBe("fixed");
    expect(form.scene_type).toBe("mountain");
    expect(form.gps_latitude).toBe("23.129100");
    expect(form.gps_longitude).toBe("113.264400");
    expect(form.gps_altitude).toBe("50");
    expect(form.maker_note_template).toBe("Canon EOS R5");
  });

  it("坐标统一转为字符串以适配受控输入", () => {
    const form = toEditFormEcho({ gps_latitude: 1.5, gps_longitude: null });
    expect(form.gps_latitude).toBe("1.5");
    expect(form.gps_longitude).toBe("");
  });

  it("缺省预设回退默认值", () => {
    const form = toEditFormEcho({});
    expect(form.gps_mode).toBe("none");
    expect(form.scene_type).toBe("urban");
    expect(form.maker_note_template).toBe("");
  });
});

describe("toUpdatePayloadEcho - 提交更新（未改动即保留）", () => {
  it('有效枚举值 gps_mode="none" 不被误判为 falsy 丢失，随 payload 提交', () => {
    const payload = toUpdatePayloadEcho({
      gps_mode: "none",
      scene_type: "urban",
      gps_latitude: "",
      gps_longitude: "",
      gps_altitude: "",
      maker_note_template: "",
    });
    expect(payload.gps_mode).toBe("none");
    expect(payload.scene_type).toBe("urban");
    // 空坐标不提交（保持后端原值）
    expect(payload.gps_latitude).toBeUndefined();
    expect(payload.gps_longitude).toBeUndefined();
    expect(payload.gps_altitude).toBeUndefined();
    // 空 MakerNote 传空字符串（后端会转 null 清空），而非 undefined
    expect(payload.maker_note_template).toBe("");
  });

  it("完整编辑值应正确转换：坐标转 number，MakerNote 原样保留", () => {
    const payload = toUpdatePayloadEcho({
      gps_mode: "fixed",
      scene_type: "beach",
      gps_latitude: "23.1291",
      gps_longitude: "113.2644",
      gps_altitude: "50",
      maker_note_template: "Nikon D850",
    });
    expect(payload.gps_mode).toBe("fixed");
    expect(payload.gps_latitude).toBe(23.1291);
    expect(payload.gps_longitude).toBe(113.2644);
    expect(payload.gps_altitude).toBe(50);
    expect(payload.maker_note_template).toBe("Nikon D850");
  });

  it("回填后原样提交应保留 GPS 模式与 MakerNote（编辑不改动这两项）", () => {
    const source = {
      gps_mode: "random_by_scene",
      scene_type: "street",
      gps_latitude: "1.23",
      gps_longitude: "4.56",
      gps_altitude: "7",
      maker_note_template: "Sony A7R V",
    };
    const roundTrip = toUpdatePayloadEcho(toEditFormEcho(source));
    expect(roundTrip.gps_mode).toBe("random_by_scene");
    expect(roundTrip.scene_type).toBe("street");
    expect(roundTrip.maker_note_template).toBe("Sony A7R V");
    expect(roundTrip.gps_latitude).toBe(1.23);
  });
});
