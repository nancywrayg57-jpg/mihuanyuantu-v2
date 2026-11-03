/**
 * 上传模拟模块单元测试
 */

import { describe, it, expect, beforeAll } from 'vitest';
import sharp from 'sharp';
import { simulatePlatformUpload, getSupportedPlatforms } from './uploadSimulator';

// ============================================================
// 测试辅助函数
// ============================================================

async function createTestJpeg(
  width = 200,
  height = 200,
  color: { r: number; g: number; b: number } = { r: 120, g: 160, b: 200 }
): Promise<string> {
  const buffer = await sharp({
    create: { width, height, channels: 3, background: color },
  })
    .jpeg({ quality: 95 })
    .toBuffer();
  return buffer.toString('base64');
}

async function isValidJpeg(base64: string): Promise<boolean> {
  try {
    const buffer = Buffer.from(base64, 'base64');
    const metadata = await sharp(buffer).metadata();
    return metadata.format === 'jpeg' && (metadata.width ?? 0) > 0;
  } catch {
    return false;
  }
}

async function getImageSize(base64: string): Promise<{ width: number; height: number }> {
  const buffer = Buffer.from(base64, 'base64');
  const metadata = await sharp(buffer).metadata();
  return { width: metadata.width ?? 0, height: metadata.height ?? 0 };
}

// ============================================================
// 测试用例
// ============================================================

describe('uploadSimulator', () => {
  let testJpeg200x200: string;
  let testJpegLarge: string; // 超过平台最大尺寸的图片

  beforeAll(async () => {
    testJpeg200x200 = await createTestJpeg(200, 200);
    testJpegLarge = await createTestJpeg(2000, 2000, { r: 200, g: 100, b: 50 });
  });

  // ----------------------------------------------------------
  // 基本功能测试
  // ----------------------------------------------------------

  it('通用模式应返回有效的 JPEG', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'generic');
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('小红书模式应返回有效的 JPEG', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'xiaohongshu');
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('TikTok 模式应返回有效的 JPEG', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'tiktok');
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('微信模式应返回有效的 JPEG', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'wechat');
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('Instagram 模式应返回有效的 JPEG', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'instagram');
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('微博模式应返回有效的 JPEG', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'weibo');
    expect(await isValidJpeg(result)).toBe(true);
  });

  it('抖音模式应返回有效的 JPEG', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'douyin');
    expect(await isValidJpeg(result)).toBe(true);
  });

  // ----------------------------------------------------------
  // 尺寸归一化测试
  // ----------------------------------------------------------

  it('200x200 图片在通用模式下尺寸应保持不变', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'generic');
    const size = await getImageSize(result);
    expect(size.width).toBe(200);
    expect(size.height).toBe(200);
  });

  it('2000x2000 图片在微信模式下尺寸应不超过平台配置的 maxWidth/maxHeight', async () => {
    const result = await simulatePlatformUpload(testJpegLarge, 'wechat');
    const size = await getImageSize(result);
    // 微信平台配置为 4096x4096，2000x2000 图片不需要缩放
    expect(size.width).toBeLessThanOrEqual(4096);
    expect(size.height).toBeLessThanOrEqual(4096);
  });

  it('2000x2000 图片在 TikTok 模式下尺寸应不超过平台配置的 maxWidth/maxHeight', async () => {
    const result = await simulatePlatformUpload(testJpegLarge, 'tiktok');
    const size = await getImageSize(result);
    // TikTok 平台配置为 4096x4096，2000x2000 图片不需要缩放
    expect(size.width).toBeLessThanOrEqual(4096);
    expect(size.height).toBeLessThanOrEqual(4096);
  });

  // ----------------------------------------------------------
  // 内容变化测试
  // ----------------------------------------------------------

  it('处理后图片内容应与原始不同（编码参数已改变）', async () => {
    const result = await simulatePlatformUpload(testJpeg200x200, 'wechat');
    // 微信使用较低质量（78），处理后内容应不同
    expect(result).not.toBe(testJpeg200x200);
  });

  // ----------------------------------------------------------
  // getSupportedPlatforms 测试
  // ----------------------------------------------------------

  it('getSupportedPlatforms 应返回7个平台', () => {
    const platforms = getSupportedPlatforms();
    expect(platforms).toHaveLength(7);
  });

  it('getSupportedPlatforms 应包含所有必要字段', () => {
    const platforms = getSupportedPlatforms();
    for (const p of platforms) {
      expect(p.value).toBeTruthy();
      expect(p.label).toBeTruthy();
      expect(p.quality).toBeGreaterThan(0);
      expect(p.maxSize).toMatch(/\d+×\d+/);
    }
  });

  it('getSupportedPlatforms 应包含小红书', () => {
    const platforms = getSupportedPlatforms();
    const xhs = platforms.find(p => p.value === 'xiaohongshu');
    expect(xhs).toBeDefined();
    expect(xhs?.label).toBe('小红书');
  });

  // ----------------------------------------------------------
  // 错误处理测试
  // ----------------------------------------------------------

  it('无效的 base64 输入应返回原始字符串（不抛出异常）', async () => {
    const invalid = 'not_valid_base64_image';
    const result = await simulatePlatformUpload(invalid, 'generic');
    expect(result).toBe(invalid);
  });

  it('空字符串输入应返回空字符串（不抛出异常）', async () => {
    const result = await simulatePlatformUpload('', 'generic');
    expect(result).toBe('');
  });
});
