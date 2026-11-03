/**
 * 测试预设参数标准化函数（normalizeISO / normalizeAperture / normalizeFocalLength）
 * 以及 SSE 进度推送模块（progressEmitter）
 */
import { describe, expect, it, vi, afterEach } from "vitest";
import { normalizeISO, normalizeAperture, normalizeFocalLength } from "./exifWriter";
import {
  registerProgressClient,
  unregisterProgressClient,
  emitProgress,
  closeProgressClients,
} from "./progressEmitter";
import type { Response } from "express";

// ============================================================
// normalizeISO 测试
// ============================================================
describe("normalizeISO", () => {
  it("标准值不变：ISO 100 → 100", () => {
    expect(normalizeISO(100)).toBe(100);
  });
  it("标准值不变：ISO 3200 → 3200", () => {
    expect(normalizeISO(3200)).toBe(3200);
  });
  it("非标准值 677 → 640（最近标准档位）", () => {
    expect(normalizeISO(677)).toBe(640);
  });
  it("非标准值 9241 → 10000（最近标准档位）", () => {
    // 9241 在对数距离上更接近 10000（log2(9241)≈8.19, log2(10000)≈8.29, log2(8000)≈8.00）
    expect(normalizeISO(9241)).toBe(10000);
  });
  it("边界值 50 → 50", () => {
    expect(normalizeISO(50)).toBe(50);
  });
  it("边界值 102400 → 102400", () => {
    expect(normalizeISO(102400)).toBe(102400);
  });
  it("超出范围的大值 → 102400", () => {
    expect(normalizeISO(200000)).toBe(102400);
  });
});

// ============================================================
// normalizeAperture 测试
// ============================================================
describe("normalizeAperture", () => {
  it("标准值不变：f/2.8 → 2.8", () => {
    expect(normalizeAperture(2.8)).toBeCloseTo(2.8, 1);
  });
  it("标准值不变：f/8.0 → 8.0", () => {
    expect(normalizeAperture(8.0)).toBeCloseTo(8.0, 1);
  });
  it("非标准值 f/9.2 → f/9.0", () => {
    expect(normalizeAperture(9.2)).toBeCloseTo(9.0, 1);
  });
  it("非标准值 f/7.9 → f/8.0", () => {
    expect(normalizeAperture(7.9)).toBeCloseTo(8.0, 1);
  });
  it("非标准值 f/3.7 → f/3.5（最近标准档位）", () => {
    // 3.7 在对数距离上更接近 3.5（log2(3.7)≈1.89, log2(3.5)≈1.81, log2(4.0)=2.0）
    expect(normalizeAperture(3.7)).toBeCloseTo(3.5, 1);
  });
});

// ============================================================
// normalizeFocalLength 测试
// ============================================================
describe("normalizeFocalLength", () => {
  it("标准值不变：50mm → 50", () => {
    expect(normalizeFocalLength(50)).toBe(50);
  });
  it("标准值不变：85mm → 85", () => {
    expect(normalizeFocalLength(85)).toBe(85);
  });
  it("非标准值 111mm → 105mm", () => {
    expect(normalizeFocalLength(111)).toBe(105);
  });
  it("非标准值 33mm → 35mm", () => {
    expect(normalizeFocalLength(33)).toBe(35);
  });
  it("非标准值 22mm → 21mm", () => {
    expect(normalizeFocalLength(22)).toBe(21);
  });
});

// ============================================================
// progressEmitter 测试
// ============================================================
describe("progressEmitter", () => {
  afterEach(() => {
    // 清理每个测试后的残留客户端
    closeProgressClients(1);
    closeProgressClients(2);
  });

  function makeMockRes() {
    const written: string[] = [];
    const ended: boolean[] = [false];
    const res = {
      write: vi.fn((data: string) => { written.push(data); }),
      end: vi.fn(() => { ended[0] = true; }),
    } as unknown as Response;
    return { res, written, ended };
  }

  it("注册客户端后可以接收进度事件", () => {
    const { res, written } = makeMockRes();
    registerProgressClient(1, res);
    emitProgress({ recordId: 1, progress: 50, stage: "处理中" });
    expect(written).toHaveLength(1);
    expect(written[0]).toContain('"progress":50');
    expect(written[0]).toContain('"stage":"处理中"');
  });

  it("注销客户端后不再接收事件", () => {
    const { res, written } = makeMockRes();
    registerProgressClient(1, res);
    unregisterProgressClient(1, res);
    emitProgress({ recordId: 1, progress: 80, stage: "上传中" });
    expect(written).toHaveLength(0);
  });

  it("closeProgressClients 关闭所有连接", () => {
    const { res: res1, ended: ended1 } = makeMockRes();
    const { res: res2, ended: ended2 } = makeMockRes();
    registerProgressClient(2, res1);
    registerProgressClient(2, res2);
    closeProgressClients(2);
    expect(ended1[0]).toBe(true);
    expect(ended2[0]).toBe(true);
  });

  it("多个客户端都能收到同一进度事件", () => {
    const { res: res1, written: w1 } = makeMockRes();
    const { res: res2, written: w2 } = makeMockRes();
    registerProgressClient(1, res1);
    registerProgressClient(1, res2);
    emitProgress({ recordId: 1, progress: 100, stage: "完成", done: true });
    expect(w1).toHaveLength(1);
    expect(w2).toHaveLength(1);
  });

  it("不同 recordId 的事件互不干扰", () => {
    const { res: res1, written: w1 } = makeMockRes();
    const { res: res2, written: w2 } = makeMockRes();
    registerProgressClient(1, res1);
    registerProgressClient(2, res2);
    emitProgress({ recordId: 1, progress: 30, stage: "阶段1" });
    expect(w1).toHaveLength(1);
    expect(w2).toHaveLength(0);
  });
});
