import { describe, it, expect } from "vitest";
import { normalizeISO } from "./exifWriter";

// ─── ISO 校验逻辑测试（导入流程中使用） ───────────────────────────────────

const STANDARD_ISO_VALUES = [
  50, 64, 80, 100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250,
  1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000, 12800, 16000, 20000,
  25600, 32000, 40000, 51200, 64000, 80000, 102400,
];

function isStandardISO(value: number): boolean {
  return STANDARD_ISO_VALUES.includes(value);
}

describe("导入流程 ISO 校验", () => {
  it("标准 ISO 值应通过校验", () => {
    expect(isStandardISO(100)).toBe(true);
    expect(isStandardISO(200)).toBe(true);
    expect(isStandardISO(400)).toBe(true);
    expect(isStandardISO(800)).toBe(true);
    expect(isStandardISO(1600)).toBe(true);
    expect(isStandardISO(3200)).toBe(true);
    expect(isStandardISO(6400)).toBe(true);
    expect(isStandardISO(12800)).toBe(true);
  });

  it("非标准 ISO 值应不通过校验", () => {
    expect(isStandardISO(166)).toBe(false);
    expect(isStandardISO(333)).toBe(false);
    expect(isStandardISO(677)).toBe(false);
    expect(isStandardISO(1234)).toBe(false);
    expect(isStandardISO(0)).toBe(false);
    expect(isStandardISO(-100)).toBe(false);
  });

  it("normalizeISO 应将非标准值修正到最近档位", () => {
    // ISO 166 → 最近标准值 160
    expect(normalizeISO(166)).toBe(160);
    // ISO 677 → 最近标准值 640
    expect(normalizeISO(677)).toBe(640);
    // ISO 333 → 最近标准值 320
    expect(normalizeISO(333)).toBe(320);
    // ISO 1234 → 最近标准值 1250
    expect(normalizeISO(1234)).toBe(1250);
  });

  it("normalizeISO 对标准值应原样返回", () => {
    expect(normalizeISO(100)).toBe(100);
    expect(normalizeISO(400)).toBe(400);
    expect(normalizeISO(1600)).toBe(1600);
    expect(normalizeISO(3200)).toBe(3200);
  });

  it("normalizeISO 对极端值应返回最近边界", () => {
    // 极小值 → 50
    expect(normalizeISO(10)).toBe(50);
    // 极大值 → 102400
    expect(normalizeISO(200000)).toBe(102400);
  });
});

// ─── 预设健康度判断逻辑测试 ───────────────────────────────────────────────

interface PresetHealthCheck {
  iso: number | null;
  iso_range: string | null;
}

function checkPresetHealth(preset: PresetHealthCheck): {
  hasIssues: boolean;
  issues: string[];
} {
  const issues: string[] = [];

  if (!preset.iso_range) {
    issues.push("iso_range 字段缺失");
  }

  if (preset.iso && !isStandardISO(preset.iso)) {
    issues.push(`ISO 值 ${preset.iso} 为非标准值`);
  }

  return {
    hasIssues: issues.length > 0,
    issues,
  };
}

describe("预设健康度检查", () => {
  it("完整合规的预设应无问题", () => {
    const result = checkPresetHealth({ iso: 400, iso_range: "100-6400" });
    expect(result.hasIssues).toBe(false);
    expect(result.issues).toHaveLength(0);
  });

  it("缺少 iso_range 的预设应有问题", () => {
    const result = checkPresetHealth({ iso: 400, iso_range: null });
    expect(result.hasIssues).toBe(true);
    expect(result.issues).toContain("iso_range 字段缺失");
  });

  it("非标准 ISO 值的预设应有问题", () => {
    const result = checkPresetHealth({ iso: 166, iso_range: "100-6400" });
    expect(result.hasIssues).toBe(true);
    expect(result.issues.some((i) => i.includes("166"))).toBe(true);
  });

  it("同时有多个问题的预设应报告所有问题", () => {
    const result = checkPresetHealth({ iso: 677, iso_range: null });
    expect(result.hasIssues).toBe(true);
    expect(result.issues).toHaveLength(2);
  });

  it("ISO 为 null 时不应报告 ISO 问题", () => {
    const result = checkPresetHealth({ iso: null, iso_range: "100-6400" });
    expect(result.hasIssues).toBe(false);
  });
});

// ─── 设备类型数量角标格式化测试 ──────────────────────────────────────────

describe("设备类型数量角标", () => {
  it("有预设数量时应显示角标", () => {
    const categoryCountMap: Record<string, number> = {
      dslr: 12,
      mirrorless: 8,
      phone: 25,
      action: 5,
    };

    const formatLabel = (type: string, label: string) => {
      const count = categoryCountMap[type];
      return count ? `${label} (${count})` : label;
    };

    expect(formatLabel("dslr", "单反")).toBe("单反 (12)");
    expect(formatLabel("mirrorless", "微单")).toBe("微单 (8)");
    expect(formatLabel("phone", "手机")).toBe("手机 (25)");
    expect(formatLabel("action", "运动相机")).toBe("运动相机 (5)");
  });

  it("无预设数量时不应显示角标", () => {
    const categoryCountMap: Record<string, number> = {};

    const formatLabel = (type: string, label: string) => {
      const count = categoryCountMap[type];
      return count ? `${label} (${count})` : label;
    };

    expect(formatLabel("dslr", "单反")).toBe("单反");
    expect(formatLabel("phone", "手机")).toBe("手机");
  });
});
