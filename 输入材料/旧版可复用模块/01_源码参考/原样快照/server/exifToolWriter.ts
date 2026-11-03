/**
 * EXIF 元数据写入模块 v3.0（ExifTool 版）
 *
 * 核心原则：
 * - 使用 ExifTool 替代 piexifjs 进行底层写入，精度更高
 * - 保留所有业务逻辑（GPS 生成、参数标准化、MakerNote）
 * - ExifTool 直接接受标准 EXIF 标签名，无需手动处理字节序
 * - 支持 JPEG 格式（通过临时文件操作）
 *
 * v3.0 改进：
 * - 使用 ExifTool 替代 piexifjs，MakerNote 精度更高
 * - 支持最新 iPhone/Android 型号的 MakerNote
 * - GPS 精度更高，字段更完整
 * - 无需手动处理 IFD 字节序和有理数格式
 */

import { exiftool, Tags } from 'exiftool-vendored';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import sharp from 'sharp';

// ============================================================
// 类型定义
// ============================================================

interface ExifPreset {
  camera_make?: string;
  camera_model?: string;
  lens_make?: string;
  lens_model?: string;
  lens_max_aperture?: number;
  focal_length?: number;
  focal_length_equiv?: number;
  aperture?: number;
  iso?: number;
  shutter_speed?: string;
  white_balance?: string;
  color_temperature?: number | null;
  metering_mode?: string;
  exposure_mode?: string;
  flash_mode?: string;
  scene_mode?: string;
  color_mode?: string;
  sensor_size?: string;
  sensor_type?: string;
  stabilization?: string;
  image_format?: string;
  color_space?: string;
  color_depth?: number;
  sharpening?: string;
  noise_reduction?: string;
  software?: string;
  author?: string;
  copyright?: string;
  image_width?: number;
  image_height?: number;
  gps_latitude?: number | string | null;
  gps_longitude?: number | string | null;
  gps_altitude?: number | null;
  gps_mode?: string;
  scene_type?: string;
  focal_plane_x_res?: number;
  focal_plane_y_res?: number;
  focal_plane_res_unit?: number;
  maker_note_template?: string;
}

// ============================================================
// 机型传感器参数数据库（与 exifWriter.ts 保持一致）
// ============================================================
interface CameraSpec {
  focalPlaneXRes: number;
  focalPlaneYRes: number;
  pixelWidth: number;
  pixelHeight: number;
  sensorWidth: number;
  sensorHeight: number;
}

const CAMERA_SPECS: Record<string, CameraSpec> = {
  'Canon EOS-1D X': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 5184, pixelHeight: 3456, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS-1D X Mark II': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 5472, pixelHeight: 3648, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS-1D X Mark III': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 5472, pixelHeight: 3648, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS 5D Mark IV': { focalPlaneXRes: 3796.99, focalPlaneYRes: 3797.00, pixelWidth: 6720, pixelHeight: 4480, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS 5D Mark III': { focalPlaneXRes: 3479.17, focalPlaneYRes: 3479.17, pixelWidth: 5760, pixelHeight: 3840, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS 6D Mark II': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6240, pixelHeight: 4160, sensorWidth: 35.9, sensorHeight: 24.0 },
  'Canon EOS 90D': { focalPlaneXRes: 5765.00, focalPlaneYRes: 5765.00, pixelWidth: 6960, pixelHeight: 4640, sensorWidth: 22.3, sensorHeight: 14.9 },
  'Canon EOS 850D': { focalPlaneXRes: 5765.00, focalPlaneYRes: 5765.00, pixelWidth: 6000, pixelHeight: 4000, sensorWidth: 22.3, sensorHeight: 14.9 },
  'Canon EOS R5': { focalPlaneXRes: 4016.06, focalPlaneYRes: 4016.06, pixelWidth: 8192, pixelHeight: 5464, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS R6': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 5472, pixelHeight: 3648, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS R6 Mark II': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 5472, pixelHeight: 3648, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Canon EOS R3': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6000, pixelHeight: 4000, sensorWidth: 36.0, sensorHeight: 24.0 },
  'Nikon D850': { focalPlaneXRes: 4016.06, focalPlaneYRes: 4016.06, pixelWidth: 8256, pixelHeight: 5504, sensorWidth: 35.9, sensorHeight: 23.9 },
  'Nikon D780': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6048, pixelHeight: 4024, sensorWidth: 35.9, sensorHeight: 23.9 },
  'Nikon D750': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6016, pixelHeight: 4016, sensorWidth: 35.9, sensorHeight: 24.0 },
  'Nikon D7500': { focalPlaneXRes: 5765.00, focalPlaneYRes: 5765.00, pixelWidth: 5568, pixelHeight: 3712, sensorWidth: 23.5, sensorHeight: 15.7 },
  'Nikon D5600': { focalPlaneXRes: 5765.00, focalPlaneYRes: 5765.00, pixelWidth: 6000, pixelHeight: 4000, sensorWidth: 23.5, sensorHeight: 15.6 },
  'Nikon Z6 II': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6048, pixelHeight: 4024, sensorWidth: 35.9, sensorHeight: 23.9 },
  'Nikon Z7 II': { focalPlaneXRes: 4267.72, focalPlaneYRes: 4267.72, pixelWidth: 8256, pixelHeight: 5504, sensorWidth: 35.9, sensorHeight: 23.9 },
  'Sony A7R IV': { focalPlaneXRes: 4267.72, focalPlaneYRes: 4267.72, pixelWidth: 9504, pixelHeight: 6336, sensorWidth: 35.7, sensorHeight: 23.8 },
  'Sony A7R V': { focalPlaneXRes: 4267.72, focalPlaneYRes: 4267.72, pixelWidth: 9504, pixelHeight: 6336, sensorWidth: 35.7, sensorHeight: 23.8 },
  'Sony A7 IV': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 7008, pixelHeight: 4672, sensorWidth: 35.9, sensorHeight: 23.9 },
  'Sony A7 III': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6000, pixelHeight: 4000, sensorWidth: 35.6, sensorHeight: 23.8 },
  'Sony A9 II': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6000, pixelHeight: 4000, sensorWidth: 35.6, sensorHeight: 23.8 },
  'Sony A6600': { focalPlaneXRes: 6240.00, focalPlaneYRes: 6240.00, pixelWidth: 6000, pixelHeight: 4000, sensorWidth: 23.5, sensorHeight: 15.6 },
  'Pentax K-1 Mark II': { focalPlaneXRes: 3543.31, focalPlaneYRes: 3543.31, pixelWidth: 7360, pixelHeight: 4912, sensorWidth: 35.9, sensorHeight: 24.0 },
  'Pentax K-3 Mark III': { focalPlaneXRes: 5765.00, focalPlaneYRes: 5765.00, pixelWidth: 6192, pixelHeight: 4128, sensorWidth: 23.3, sensorHeight: 15.5 },
  'Pentax K-70': { focalPlaneXRes: 5765.00, focalPlaneYRes: 5765.00, pixelWidth: 6016, pixelHeight: 4000, sensorWidth: 23.5, sensorHeight: 15.6 },
  'Fujifilm X-T4': { focalPlaneXRes: 6240.00, focalPlaneYRes: 6240.00, pixelWidth: 6240, pixelHeight: 4160, sensorWidth: 23.5, sensorHeight: 15.6 },
  'Fujifilm X-T5': { focalPlaneXRes: 7752.00, focalPlaneYRes: 7752.00, pixelWidth: 8240, pixelHeight: 5504, sensorWidth: 23.5, sensorHeight: 15.6 },
  'Fujifilm X-S10': { focalPlaneXRes: 6240.00, focalPlaneYRes: 6240.00, pixelWidth: 6240, pixelHeight: 4160, sensorWidth: 23.5, sensorHeight: 15.6 },
  'Fujifilm GFX 50S II': { focalPlaneXRes: 3200.00, focalPlaneYRes: 3200.00, pixelWidth: 8256, pixelHeight: 6192, sensorWidth: 43.8, sensorHeight: 32.9 },
  'OM System OM-1': { focalPlaneXRes: 9600.00, focalPlaneYRes: 9600.00, pixelWidth: 5184, pixelHeight: 3888, sensorWidth: 17.4, sensorHeight: 13.0 },
  'Olympus OM-D E-M1 Mark III': { focalPlaneXRes: 9600.00, focalPlaneYRes: 9600.00, pixelWidth: 5184, pixelHeight: 3888, sensorWidth: 17.4, sensorHeight: 13.0 },
  'Panasonic Lumix S5 II': { focalPlaneXRes: 3545.83, focalPlaneYRes: 3526.53, pixelWidth: 6000, pixelHeight: 4000, sensorWidth: 35.6, sensorHeight: 23.8 },
  'Panasonic Lumix G9 II': { focalPlaneXRes: 9600.00, focalPlaneYRes: 9600.00, pixelWidth: 5776, pixelHeight: 4336, sensorWidth: 17.3, sensorHeight: 13.0 },
  'Apple iPhone 15 Pro': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 15 Pro Max': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 16': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 16 Pro': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 16 Pro Max': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 14 Pro': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 14': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 13 Pro': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'Apple iPhone 13': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4032, pixelHeight: 3024, sensorWidth: 6.765, sensorHeight: 5.074 },
  'HUAWEI P60 Pro': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4000, pixelHeight: 3000, sensorWidth: 6.4, sensorHeight: 4.8 },
  'HUAWEI Mate 60 Pro': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4000, pixelHeight: 3000, sensorWidth: 6.4, sensorHeight: 4.8 },
  'Samsung Galaxy S24 Ultra': { focalPlaneXRes: 14400.00, focalPlaneYRes: 14400.00, pixelWidth: 4000, pixelHeight: 3000, sensorWidth: 6.4, sensorHeight: 4.8 },
};

function getCameraSpec(make?: string, model?: string): CameraSpec | null {
  if (!model) return null;
  const fullName = `${make ?? ''} ${model}`.trim();
  if (CAMERA_SPECS[fullName]) return CAMERA_SPECS[fullName];
  if (CAMERA_SPECS[model]) return CAMERA_SPECS[model];
  for (const [key, spec] of Object.entries(CAMERA_SPECS)) {
    if (model.includes(key) || key.includes(model)) return spec;
  }
  return null;
}

// ============================================================
// GPS 随机坐标生成（与 exifWriter.ts 保持一致）
// ============================================================
interface GpsRegion {
  latMin: number; latMax: number;
  lngMin: number; lngMax: number;
  altMin: number; altMax: number;
}

const GPS_REGIONS: Record<string, GpsRegion[]> = {
  landscape: [
    { latMin: 36.0, latMax: 42.0, lngMin: 110.0, lngMax: 120.0, altMin: 500, altMax: 2500 },
    { latMin: 25.0, latMax: 32.0, lngMin: 100.0, lngMax: 110.0, altMin: 1000, altMax: 3500 },
    { latMin: 28.0, latMax: 35.0, lngMin: 80.0, lngMax: 95.0, altMin: 3000, altMax: 5000 },
    { latMin: 44.0, latMax: 49.0, lngMin: -110.0, lngMax: -104.0, altMin: 1500, altMax: 3000 },
    { latMin: 46.0, latMax: 48.0, lngMin: 7.0, lngMax: 10.0, altMin: 800, altMax: 2500 },
    { latMin: 35.0, latMax: 37.5, lngMin: 136.0, lngMax: 139.0, altMin: 200, altMax: 3776 },
    { latMin: -45.0, latMax: -40.0, lngMin: 168.0, lngMax: 172.0, altMin: 100, altMax: 1500 },
  ],
  urban: [
    { latMin: 39.8, latMax: 40.1, lngMin: 116.2, lngMax: 116.6, altMin: 30, altMax: 80 },
    { latMin: 31.1, latMax: 31.4, lngMin: 121.3, lngMax: 121.6, altMin: 5, altMax: 50 },
    { latMin: 22.9, latMax: 23.3, lngMin: 113.1, lngMax: 113.5, altMin: 10, altMax: 60 },
    { latMin: 22.4, latMax: 22.6, lngMin: 113.8, lngMax: 114.2, altMin: 5, altMax: 80 },
    { latMin: 35.6, latMax: 35.8, lngMin: 139.6, lngMax: 139.8, altMin: 10, altMax: 50 },
    { latMin: 51.4, latMax: 51.6, lngMin: -0.2, lngMax: 0.1, altMin: 5, altMax: 30 },
    { latMin: 40.6, latMax: 40.8, lngMin: -74.1, lngMax: -73.9, altMin: 5, altMax: 30 },
  ],
  portrait: [
    { latMin: 31.1, latMax: 31.4, lngMin: 121.3, lngMax: 121.6, altMin: 5, altMax: 50 },
    { latMin: 39.8, latMax: 40.1, lngMin: 116.2, lngMax: 116.6, altMin: 30, altMax: 80 },
    { latMin: 22.9, latMax: 23.3, lngMin: 113.1, lngMax: 113.5, altMin: 10, altMax: 60 },
    { latMin: 35.6, latMax: 35.8, lngMin: 139.6, lngMax: 139.8, altMin: 10, altMax: 50 },
  ],
  indoor: [
    { latMin: 31.1, latMax: 31.4, lngMin: 121.3, lngMax: 121.6, altMin: 5, altMax: 30 },
    { latMin: 39.8, latMax: 40.1, lngMin: 116.2, lngMax: 116.6, altMin: 30, altMax: 60 },
  ],
  food: [
    { latMin: 31.1, latMax: 31.4, lngMin: 121.3, lngMax: 121.6, altMin: 5, altMax: 30 },
    { latMin: 22.9, latMax: 23.3, lngMin: 113.1, lngMax: 113.5, altMin: 10, altMax: 40 },
    { latMin: 35.6, latMax: 35.8, lngMin: 139.6, lngMax: 139.8, altMin: 10, altMax: 50 },
  ],
  sports: [
    { latMin: 39.8, latMax: 40.1, lngMin: 116.2, lngMax: 116.6, altMin: 30, altMax: 80 },
    { latMin: 31.1, latMax: 31.4, lngMin: 121.3, lngMax: 121.6, altMin: 5, altMax: 50 },
    { latMin: 51.4, latMax: 51.6, lngMin: -0.2, lngMax: 0.1, altMin: 5, altMax: 30 },
  ],
  macro: [
    { latMin: 25.0, latMax: 32.0, lngMin: 100.0, lngMax: 110.0, altMin: 500, altMax: 2000 },
    { latMin: 22.9, latMax: 23.3, lngMin: 113.1, lngMax: 113.5, altMin: 10, altMax: 60 },
  ],
};

function randomFloat(min: number, max: number, decimals: number = 6): number {
  const val = min + Math.random() * (max - min);
  return parseFloat(val.toFixed(decimals));
}

function generateGpsCoords(sceneMode?: string): { lat: number; lng: number; alt: number } | null {
  if (sceneMode?.toLowerCase() === 'indoor' || sceneMode?.toLowerCase() === 'studio') {
    if (Math.random() > 0.5) return null;
  }
  const sceneKey = sceneMode?.toLowerCase() ?? 'landscape';
  const regions = GPS_REGIONS[sceneKey] ?? GPS_REGIONS['landscape'];
  const region = regions[Math.floor(Math.random() * regions.length)];
  return {
    lat: randomFloat(region.latMin, region.latMax, 6),
    lng: randomFloat(region.lngMin, region.lngMax, 6),
    alt: randomFloat(region.altMin, region.altMax, 1),
  };
}

// ============================================================
// 参数标准化函数（与 exifWriter.ts 保持一致）
// ============================================================

export function normalizeISO(iso: number): number {
  const standardISOs = [
    50, 64, 80, 100, 125, 160, 200, 250, 320, 400, 500, 640, 800,
    1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400,
    8000, 10000, 12800, 16000, 20000, 25600, 32000, 40000, 51200,
    64000, 80000, 102400,
  ];
  let closest = standardISOs[0];
  let minDist = Math.abs(Math.log2(iso) - Math.log2(closest));
  for (const std of standardISOs) {
    const dist = Math.abs(Math.log2(iso) - Math.log2(std));
    if (dist < minDist) { minDist = dist; closest = std; }
  }
  return closest;
}

export function normalizeAperture(fNumber: number): number {
  const standardFStops = [
    1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.5, 2.8, 3.2, 3.5,
    4.0, 4.5, 5.0, 5.6, 6.3, 7.1, 8.0, 9.0, 10, 11, 13, 14, 16, 18, 20, 22,
  ];
  if (!fNumber || !isFinite(fNumber) || fNumber <= 0) return 1.8;
  let closest = standardFStops[0];
  let minDist = Math.abs(Math.log2(fNumber) - Math.log2(closest));
  for (const std of standardFStops) {
    const dist = Math.abs(Math.log2(fNumber) - Math.log2(std));
    if (dist < minDist) { minDist = dist; closest = std; }
  }
  return closest;
}

export function normalizeFocalLength(mm: number): number {
  const commonFocalLengths = [
    8, 10, 12, 14, 15, 16, 17, 18, 20, 21, 24, 28, 35, 40, 50, 55,
    58, 60, 70, 75, 80, 85, 90, 100, 105, 120, 135, 150, 180, 200,
    210, 240, 300, 400, 500, 600, 800, 1000,
  ];
  let closest = commonFocalLengths[0];
  let minDist = Math.abs(Math.log2(mm) - Math.log2(closest));
  for (const std of commonFocalLengths) {
    const dist = Math.abs(Math.log2(mm) - Math.log2(std));
    if (dist < minDist) { minDist = dist; closest = std; }
  }
  return closest;
}

function parseShutterSpeed(shutter: string): string {
  if (!shutter || shutter.trim() === '') return '1/125';
  const shutterClean = shutter.replace(/s$/i, '').trim();
  if (shutterClean.includes('/')) return shutterClean;
  const sec = parseFloat(shutterClean);
  if (!isFinite(sec) || sec <= 0) return '1/125';
  if (sec >= 1) return `${Math.round(sec)}`;
  const den = Math.round(1 / sec);
  return `1/${den}`;
}

function meteringModeToCode(mode?: string): number {
  const map: Record<string, number> = {
    'evaluative': 5, 'center': 2, 'spot': 3, 'matrix': 5, 'average': 1, 'partial': 6,
    'multi': 5, 'multi-segment': 5, 'pattern': 5,
  };
  return map[mode?.toLowerCase() ?? ''] ?? 0;
}

function exposureModeToCode(mode?: string): number {
  const map: Record<string, number> = { 'auto': 0, 'M': 1, 'manual': 1, 'bracket': 2 };
  return map[mode ?? ''] ?? 0;
}

function flashToCode(flash?: string): number {
  if (!flash || flash.toLowerCase() === 'off') return 0;
  if (flash.toLowerCase() === 'on') return 1;
  return 0;
}

// ============================================================
// 主函数：使用 ExifTool 写入 EXIF 到 JPEG
// ============================================================

/**
 * 将 base64 JPEG 字符串写入 EXIF 并返回新的 base64 字符串
 * 使用 ExifTool 进行底层写入，精度更高
 */
export async function writeExifToJpeg(
  jpegBase64: string,
  preset: ExifPreset,
  createdAt?: Date
): Promise<string> {
  const now = createdAt ?? new Date();

  // 格式化日期时间（ExifTool 格式：YYYY:MM:DD HH:MM:SS）
  const pad = (n: number) => String(n).padStart(2, '0');
  const dateStr = `${now.getFullYear()}:${pad(now.getMonth() + 1)}:${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const subsecMs = String(Math.floor(Math.random() * 99)).padStart(2, '0');

  console.log(`[ExifToolWriter] 开始写入 EXIF | 设备: ${preset.camera_make ?? '-'} ${preset.camera_model ?? '-'} | ISO: ${preset.iso ?? '-'} | 光圈: f/${preset.aperture ?? '-'} | 快门: ${preset.shutter_speed ?? '-'} | 焦距: ${preset.focal_length ?? '-'}mm | GPS模式: ${preset.gps_mode ?? '-'}`);

  // 创建临时文件
  const tmpDir = os.tmpdir();
  const tmpId = `exif_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const inputFile = path.join(tmpDir, `${tmpId}_input.jpg`);
  const outputFile = path.join(tmpDir, `${tmpId}_output.jpg`);

  try {
    // 将 base64 写入临时文件
    const jpegBuffer = Buffer.from(jpegBase64, 'base64');
    fs.writeFileSync(inputFile, jpegBuffer);

    // 获取相机规格
    const spec = getCameraSpec(preset.camera_make, preset.camera_model);
    const pixelWidth = preset.image_width ?? spec?.pixelWidth ?? 4032;
    const pixelHeight = preset.image_height ?? spec?.pixelHeight ?? 3024;

    // 构建 ExifTool 标签对象
    const tags: Record<string, any> = {};

    // ===== 基础图像信息（0th IFD）=====
    if (preset.camera_make) tags['Make'] = preset.camera_make;
    if (preset.camera_model) tags['Model'] = preset.camera_model;
    if (preset.software) tags['Software'] = preset.software;
    if (preset.author) tags['Artist'] = preset.author;
    if (preset.copyright) tags['Copyright'] = preset.copyright;
    tags['DateTime'] = dateStr;
    tags['Orientation'] = 1;
    tags['XResolution'] = 72;
    tags['YResolution'] = 72;
    tags['ResolutionUnit'] = 2;
    tags['YCbCrPositioning'] = 2;

    // ===== Exif IFD =====
    tags['ExifVersion'] = '0230';
    tags['FlashpixVersion'] = '0100';
    tags['DateTimeOriginal'] = dateStr;
    tags['CreateDate'] = dateStr;
    tags['SubSecTime'] = subsecMs;
    tags['SubSecTimeOriginal'] = subsecMs;
    tags['SubSecTimeDigitized'] = subsecMs;
    tags['ComponentsConfiguration'] = '1 2 3 0';
    tags['ColorSpace'] = (preset.color_space?.toLowerCase() === 'adobergb') ? 65535 : 1;
    tags['ExifImageWidth'] = pixelWidth;
    tags['ExifImageHeight'] = pixelHeight;
    tags['ExposureBiasValue'] = 0;
    tags['CustomRendered'] = 0;
    tags['SensingMethod'] = 2;
    tags['DigitalZoomRatio'] = 0;
    tags['Contrast'] = 0;
    tags['Saturation'] = 0;
    tags['Sharpness'] = 0;
    tags['SubjectDistanceRange'] = 0;

    // 图像唯一 ID
    const uniqueId = `${Date.now().toString(16).toUpperCase().padStart(12, '0')}${Math.floor(Math.random() * 0xFFFFFF).toString(16).toUpperCase().padStart(6, '0')}00000000000000000000`;
    tags['ImageUniqueID'] = uniqueId.slice(0, 32);

    // 传感器物理像素密度
    const focalPlaneXRes = preset.focal_plane_x_res ?? spec?.focalPlaneXRes;
    const focalPlaneYRes = preset.focal_plane_y_res ?? spec?.focalPlaneYRes;
    const focalPlaneUnit = preset.focal_plane_res_unit ?? 2;
    if (focalPlaneXRes && focalPlaneYRes) {
      tags['FocalPlaneXResolution'] = focalPlaneXRes;
      tags['FocalPlaneYResolution'] = focalPlaneYRes;
      tags['FocalPlaneResolutionUnit'] = focalPlaneUnit;
    }

    // ISO
    if (preset.iso) {
      const normalizedISO = normalizeISO(preset.iso);
      if (normalizedISO !== preset.iso) {
        console.log(`[ExifToolWriter] ISO 标准化: ${preset.iso} → ${normalizedISO}`);
      }
      tags['ISO'] = normalizedISO;
    }

    // 快门速度
    if (preset.shutter_speed) {
      const shutterStr = parseShutterSpeed(preset.shutter_speed);
      tags['ExposureTime'] = shutterStr;
      tags['ShutterSpeedValue'] = shutterStr;
    }

    // 光圈
    if (preset.aperture) {
      const normalizedAperture = normalizeAperture(preset.aperture);
      if (Math.abs(normalizedAperture - preset.aperture) > 0.05) {
        console.log(`[ExifToolWriter] 光圈标准化: f/${preset.aperture} → f/${normalizedAperture}`);
      }
      tags['FNumber'] = normalizedAperture;
      tags['ApertureValue'] = normalizedAperture;
    }

    // 焦距
    if (preset.focal_length) {
      const normalizedFocalLength = normalizeFocalLength(preset.focal_length);
      if (Math.abs(normalizedFocalLength - preset.focal_length) > 0.5) {
        console.log(`[ExifToolWriter] 焦距标准化: ${preset.focal_length}mm → ${normalizedFocalLength}mm`);
      }
      tags['FocalLength'] = normalizedFocalLength;
    }
    if (preset.focal_length_equiv) tags['FocalLengthIn35mmFormat'] = Math.round(preset.focal_length_equiv);
    if (preset.lens_model) tags['LensModel'] = preset.lens_model;
    if (preset.lens_make) tags['LensMake'] = preset.lens_make;
    if (preset.lens_max_aperture) tags['MaxApertureValue'] = preset.lens_max_aperture;

    // 测光、白平衡、曝光模式
    tags['MeteringMode'] = meteringModeToCode(preset.metering_mode);
    tags['WhiteBalance'] = (!preset.white_balance || preset.white_balance.toLowerCase() === 'auto') ? 0 : 1;
    tags['ExposureMode'] = exposureModeToCode(preset.exposure_mode);
    tags['Flash'] = flashToCode(preset.flash_mode);

    // 曝光程序
    const expProgramMap: Record<string, number> = {
      'auto': 2, 'M': 1, 'manual': 1, 'A': 3, 'S': 4, 'P': 2,
      'Aperture Priority': 3, 'Shutter Priority': 4, 'Normal program': 2,
    };
    tags['ExposureProgram'] = expProgramMap[preset.exposure_mode ?? 'auto'] ?? 2;

    // 场景类型
    const scene = preset.scene_mode?.toLowerCase() ?? '';
    tags['SceneCaptureType'] = scene === 'portrait' ? 2 : scene === 'landscape' ? 1 : scene === 'night' ? 3 : 0;

    // 光源
    const lightSourceMap: Record<string, number> = {
      'auto': 0, 'daylight': 1, 'fluorescent': 2, 'tungsten': 3,
      'flash': 4, 'shade': 11, 'cloudy': 10,
    };
    tags['LightSource'] = lightSourceMap[preset.white_balance?.toLowerCase() ?? 'auto'] ?? 0;

    // ===== GPS IFD =====
    const gpsMode = preset.gps_mode ?? 'auto';
    let gpsLat: number | null = null;
    let gpsLng: number | null = null;
    let gpsAlt: number | null = null;

    if (gpsMode !== 'none') {
      if (gpsMode === 'fixed' || gpsMode === 'auto') {
        gpsLat = preset.gps_latitude ? parseFloat(String(preset.gps_latitude)) : null;
        gpsLng = preset.gps_longitude ? parseFloat(String(preset.gps_longitude)) : null;
        gpsAlt = preset.gps_altitude ?? null;
      }
      if ((!gpsLat || !gpsLng) && gpsMode !== 'fixed') {
        const generated = generateGpsCoords(preset.scene_type ?? preset.scene_mode);
        if (generated) {
          gpsLat = generated.lat;
          gpsLng = generated.lng;
          gpsAlt = generated.alt;
        }
      }
    }

    if (gpsLat !== null && gpsLng !== null) {
      tags['GPSLatitude'] = Math.abs(gpsLat);
      tags['GPSLatitudeRef'] = gpsLat >= 0 ? 'N' : 'S';
      tags['GPSLongitude'] = Math.abs(gpsLng);
      tags['GPSLongitudeRef'] = gpsLng >= 0 ? 'E' : 'W';
      if (gpsAlt !== null) {
        tags['GPSAltitude'] = Math.abs(gpsAlt);
        tags['GPSAltitudeRef'] = gpsAlt >= 0 ? 0 : 1;
      }
      // GPS 时间戳
      tags['GPSTimeStamp'] = `${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}`;
      tags['GPSDateStamp'] = `${now.getUTCFullYear()}:${pad(now.getUTCMonth() + 1)}:${pad(now.getUTCDate())}`;
      tags['GPSMeasureMode'] = '3';
      tags['GPSImgDirectionRef'] = 'T';
      tags['GPSImgDirection'] = Math.floor(Math.random() * 360);
      tags['GPSSpeedRef'] = 'K';
      tags['GPSSpeed'] = 0;
      tags['GPSProcessingMethod'] = 'GPS';
    }

    // ===== 生成缩略图（1st IFD）=====
    try {
      const thumbBuffer = await sharp(jpegBuffer)
        .resize(160, 120, { fit: 'inside', withoutEnlargement: true })
        .jpeg({ quality: 70 })
        .toBuffer();
      const thumbFile = path.join(tmpDir, `${tmpId}_thumb.jpg`);
      fs.writeFileSync(thumbFile, thumbBuffer);
      tags['ThumbnailImage'] = `@${thumbFile}`;
    } catch (thumbErr) {
      console.warn('[ExifToolWriter] 缩略图生成失败:', thumbErr);
    }

    // ===== 使用 ExifTool 写入所有标签 =====
    // ExifTool 写入时会自动创建 _output.jpg（使用 -o 参数）
    await exiftool.write(inputFile, tags as Tags, [
      '-overwrite_original',
      '-charset', 'UTF8',
      '-m',  // 忽略小错误
    ]);

    // 读取写入后的文件
    const resultBuffer = fs.readFileSync(inputFile);
    const resultBase64 = resultBuffer.toString('base64');

    const inputSize = Math.round(jpegBase64.length * 3 / 4 / 1024);
    const outputSize = Math.round(resultBase64.length * 3 / 4 / 1024);
    console.log(`[ExifToolWriter] EXIF 写入成功 | 时间: ${dateStr}.${subsecMs} | 输入: ${inputSize}KB | 输出: ${outputSize}KB | 标签数: ${Object.keys(tags).length}`);

    return resultBase64;
  } catch (err) {
    console.error('[ExifToolWriter] Failed to write EXIF:', err);
    // 降级到原始 base64（不中断流程）
    return jpegBase64;
  } finally {
    // 清理临时文件
    for (const f of [inputFile, outputFile]) {
      try { if (fs.existsSync(f)) fs.unlinkSync(f); } catch {}
    }
  }
}
