/**
 * 指纹破坏模块单元测试
 *
 * 测试策略：
 *   1. 使用 sharp 生成最小测试图片（100x100 纯色 JPEG）
 *   2. 验证处理后的图片是有效的 JPEG
 *   3. 验证处理后的图片尺寸与输入一致（几何微扰不改变尺寸）
 *   4. 验证处理后的图片内容与输入不同（指纹破坏有效）
 *   5. 验证错误处理（无效输入时返回原始图片）
 */

import { describe, it, expect, beforeAll } from 'vitest';
import sharp from 'sharp';
import { destroyFingerprints, extractFingerprintOptions } from './fingerprintDestroyer';

// ============================================================
// 测试辅助函数
// ============================================================

/** 生成测试用的 JPEG 图片（带随机噪声纹理，更接近真实图片） */
async function createTestJpeg(
  width = 100,
  height = 100,
  _color: { r: number; g: number; b: number } = { r: 128, g: 128, b: 128 }
): Promise<string> {
  // 生成带随机噪声纹理的图片（模拟真实相机图片）
  const pixels = new Uint8Array(width * height * 3);
  for (let i = 0; i < pixels.length; i++) {
    // 基色 + 随机噪声，使图片内容不单一
    pixels[i] = Math.floor(80 + Math.random() * 120);
  }
  const buffer = await sharp(Buffer.from(pixels), {
    raw: { width, height, channels: 3 },
  })
    .jpeg({ quality: 90 })
    .toBuffer();
  return buffer.toString('base64');
}

/** 验证 base64 字符串是否为有效的 JPEG */
async function isValidJpeg(base64: string): Promise<boolean> {
  try {
    const buffer = Buffer.from(base64, 'base64');
    const metadata = await sharp(buffer).metadata();
    return metadata.format === 'jpeg' && (metadata.width ?? 0) > 0 && (metadata.height ?? 0) > 0;
  } catch {
    return false;
  }
}

/** 获取图片尺寸 */
async function getImageSize(base64: string): Promise<{ width: number; height: number }> {
  const buffer = Buffer.from(base64, 'base64');
  const metadata = await sharp(buffer).metadata();
  return { width: metadata.width ?? 0, height: metadata.height ?? 0 };
}

// ============================================================
// 测试用例
// ============================================================

describe('fingerprintDestroyer', () => {
  let testJpeg100x100: string;
  let testJpeg200x300: string;

  beforeAll(async () => {
    // 生成测试图片
    testJpeg100x100 = await createTestJpeg(100, 100, { r: 200, g: 150, b: 100 });
    testJpeg200x300 = await createTestJpeg(200, 300, { r: 100, g: 180, b: 220 });
  });

  // ----------------------------------------------------------
  // 基本功能测试
  // ----------------------------------------------------------

  it('应返回有效的 JPEG 图片', async () => {
    const result = await destroyFingerprints(testJpeg100x100);
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('处理后图片尺寸应与输入一致（100x100）', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      enableGeometricPerturbation: true,
    });
    const size = await getImageSize(result);
    expect(size.width).toBe(100);
    expect(size.height).toBe(100);
  });

  it('处理后图片尺寸应与输入一致（200x300）', async () => {
    const result = await destroyFingerprints(testJpeg200x300, {
      enableGeometricPerturbation: true,
    });
    const size = await getImageSize(result);
    expect(size.width).toBe(200);
    expect(size.height).toBe(300);
  });

  it('处理后图片内容应与输入不同（指纹破坏有效）', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      pHashDestructionLevel: 2,
      enableDiffusionSpectrumDestruction: true,
      enableColorFingerprintDestruction: true,
      enableGeometricPerturbation: true,
    });
    // 处理后的 base64 应与原始不同（内容已被修改）
    expect(result).not.toBe(testJpeg100x100);
  });

  // ----------------------------------------------------------
  // 各子功能独立测试
  // ----------------------------------------------------------

  it('仅启用感知哈希破坏时应正常工作', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      pHashDestructionLevel: 2,
      enableDiffusionSpectrumDestruction: false,
      enableColorFingerprintDestruction: false,
      enableGeometricPerturbation: false,
    });
    expect(await isValidJpeg(result)).toBe(true);
    expect(result).not.toBe(testJpeg100x100);
  });

  it('仅启用扩散模型频谱指纹破坏时应正常工作', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      pHashDestructionLevel: 0,
      enableDiffusionSpectrumDestruction: true,
      enableColorFingerprintDestruction: false,
      enableGeometricPerturbation: false,
    });
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('仅启用色彩统计指纹破坏时应正常工作', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      pHashDestructionLevel: 0,
      enableDiffusionSpectrumDestruction: false,
      enableColorFingerprintDestruction: true,
      enableGeometricPerturbation: false,
    });
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('仅启用几何微扰时应正常工作且尺寸不变', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      pHashDestructionLevel: 0,
      enableDiffusionSpectrumDestruction: false,
      enableColorFingerprintDestruction: false,
      enableGeometricPerturbation: true,
    });
    expect(await isValidJpeg(result)).toBe(true);
    const size = await getImageSize(result);
    expect(size.width).toBe(100);
    expect(size.height).toBe(100);
  });

  // ----------------------------------------------------------
  // 强度参数测试
  // ----------------------------------------------------------

  it('强力模式（level=3）应正常工作', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      pHashDestructionLevel: 3,
      intensity: 1.5,
    });
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('轻度模式（level=1）应正常工作', async () => {
    const result = await destroyFingerprints(testJpeg100x100, {
      pHashDestructionLevel: 1,
      intensity: 0.5,
    });
    expect(await isValidJpeg(result)).toBe(true);
  });

  // ----------------------------------------------------------
  // extractFingerprintOptions 测试
  // ----------------------------------------------------------

  it('extractFingerprintOptions 应从预设参数中提取正确的选项', () => {
    const preset = { iso: 1600 };
    const options = extractFingerprintOptions(preset);
    expect(options.pHashDestructionLevel).toBe(2);
    expect(options.enableDiffusionSpectrumDestruction).toBe(true);
    expect(options.enableColorFingerprintDestruction).toBe(true);
    expect(options.enableGeometricPerturbation).toBe(true);
    // 高 ISO 应使用更强的强度
    expect(options.intensity).toBeGreaterThan(1.0);
  });

  it('extractFingerprintOptions 低 ISO 应使用较低强度', () => {
    const preset = { iso: 100 };
    const options = extractFingerprintOptions(preset);
    expect(options.intensity).toBeLessThan(1.0);
  });

  // ----------------------------------------------------------
  // 错误处理测试
  // ----------------------------------------------------------

  it('无效的 base64 输入应返回原始字符串（不抛出异常）', async () => {
    const invalidBase64 = 'not_valid_base64_image_data';
    const result = await destroyFingerprints(invalidBase64);
    // 应返回原始字符串（失败时的降级处理）
    expect(result).toBe(invalidBase64);
  });

  it('空字符串输入应返回空字符串（不抛出异常）', async () => {
    const result = await destroyFingerprints('');
    expect(result).toBe('');
  });
});
