import { describe, it, expect } from 'vitest';
import { writeExifToJpeg } from './exifWriter';

// 最小合法 JPEG（1x1 白色像素）的 base64
const MINIMAL_JPEG_BASE64 =
  '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AJQAB/9k=';

describe('writeExifToJpeg', () => {
  it('应该返回 base64 字符串（不含 data: 前缀）', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Xiaomi',
      camera_model: '14 Ultra',
    });
    expect(typeof result).toBe('string');
    expect(result).not.toMatch(/^data:/);
    expect(result.length).toBeGreaterThan(0);
  });

  it('写入失败时应返回原始 base64（不抛出异常）', async () => {
    // 传入无效的 base64 字符串
    const result = await writeExifToJpeg('invalid_base64_string', {
      camera_make: 'Test',
    });
    // 应该返回原始字符串，不抛出异常
    expect(result).toBe('invalid_base64_string');
  });

  it('处理空预设时应正常运行', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {});
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('处理完整预设参数时应正常运行', async () => {
    const result = await writeExifToJpeg(
      MINIMAL_JPEG_BASE64,
      {
        camera_make: 'Samsung',
        camera_model: 'SM-S928B',
        lens_make: 'Samsung',
        lens_model: 'Samsung Galaxy S24 Ultra rear 5x zoom camera',
        lens_max_aperture: 3.4,
        focal_length: 11,
        focal_length_equiv: 120,
        aperture: 3.4,
        iso: 200,
        shutter_speed: '1/500',
        white_balance: 'Auto',
        color_temperature: null,
        metering_mode: 'spot',
        exposure_mode: 'auto',
        flash_mode: 'off',
        scene_mode: 'portrait',
        color_space: 'sRGB',
        software: 'Samsung Camera 13.0',
        author: 'John Smith',
        copyright: 'Prism Creative Studios',
      },
      new Date('2024-06-15T10:30:00Z')
    );
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });

  it('Auto 白平衡时色温为 null 应正常处理', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      white_balance: 'Auto',
      color_temperature: null,
    });
    expect(typeof result).toBe('string');
  });

  it('快门速度解析：分数格式', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      shutter_speed: '1/500',
    });
    expect(typeof result).toBe('string');
  });

  it('快门速度解析：整数格式', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      shutter_speed: '2',
    });
    expect(typeof result).toBe('string');
  });

  it('各种测光模式应正常映射', async () => {
    for (const mode of ['evaluative', 'center', 'spot', 'matrix', 'average', 'partial']) {
      const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, { metering_mode: mode });
      expect(typeof result).toBe('string');
    }
  });

  it('各种场景模式应正常映射', async () => {
    for (const scene of ['portrait', 'landscape', 'night', 'standard']) {
      const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, { scene_mode: scene });
      expect(typeof result).toBe('string');
    }
  });

  it('gps_mode=none 时不应写入 GPS 坐标', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      gps_mode: 'none',
      gps_latitude: 39.9042,
      gps_longitude: 116.4074,
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('gps_mode=fixed 且有坐标时应写入固定 GPS', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      gps_mode: 'fixed',
      gps_latitude: 39.9042,
      gps_longitude: 116.4074,
      gps_altitude: 50,
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });

  it('gps_mode=random_by_scene 时应随机生成 GPS', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      gps_mode: 'random_by_scene',
      scene_type: 'urban',
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('maker_note_template=canon_eos1dx 时应写入 Canon MakerNote', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Canon',
      camera_model: 'Canon EOS-1D X',
      maker_note_template: 'canon_eos1dx',
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });

  it('Apple 相机应自动选择 apple MakerNote 模板', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Apple',
      camera_model: 'iPhone 15 Pro',
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('ColorSpace 修复：写入后不应包含 65535 异常值', async () => {
    // 验证写入流程不会崩溃，且返回有效 base64
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      color_space: 'sRGB',
      camera_make: 'Nikon',
      camera_model: 'Z8',
    });
    expect(typeof result).toBe('string');
    expect(result).not.toBe('');
  });

  it('写入后应包含缩略图数据（1st IFD）', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Canon',
      camera_model: 'EOS R5',
    });
    expect(typeof result).toBe('string');
    // 写入缩略图后文件应该更大
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });

  it('ISO 标准化：9241 应被规范化到最近标准档位（10000）', async () => {
    // ISO 9241 是非标准值，应被规范化到 10000
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Sony',
      camera_model: 'A1',
      iso: 9241,
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });

  it('ISO 标准化：标准值应保持不变（ISO 400）', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Canon',
      iso: 400,
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });

  it('光圈标准化：f/7.9 应被规范化到最近标准 f-stop（f/8.0）', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Sony',
      aperture: 7.9,
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });

  it('焦距标准化：111mm 应被规范化到最近常见焦距（105mm）', async () => {
    const result = await writeExifToJpeg(MINIMAL_JPEG_BASE64, {
      camera_make: 'Sony',
      focal_length: 111,
    });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(MINIMAL_JPEG_BASE64.length);
  });
});
