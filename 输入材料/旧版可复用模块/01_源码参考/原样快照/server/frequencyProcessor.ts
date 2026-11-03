/**
 * 频域处理模块 v1.0
 *
 * 技术架构方案中的"五层防御体系"之第一层：频域处理
 *
 * 核心功能：
 *   1. 频域随机扰动（破坏AI生成图片的频域特征）
 *   2. 隐水印破坏（针对 SynthID、StableSignature、TreeRing 等）
 *   3. DCT系数微扰（JPEG量化层面的指纹破坏）
 *
 * 技术原理：
 *   AI生成图片在频域（FFT/DCT）上具有特定的统计特征：
 *   - 频谱中存在规律性的"格点"（来自扩散模型的采样步骤）
 *   - 高频分量的分布与真实相机拍摄图片存在统计差异
 *   - 某些AI工具会在频域嵌入隐水印（如Google SynthID）
 *
 *   通过在频域添加微小随机扰动，可以：
 *   - 破坏频域统计特征，使其更接近真实相机图片
 *   - 破坏隐水印信号（隐水印通常嵌入在特定频率分量中）
 *   - 不显著影响图片视觉质量（扰动量在人眼感知阈值以下）
 *
 * 参考：
 *   - remove-ai-watermarks (MIT License)
 *   - SynthID-Bypass 的低噪声扩散再生成思路
 *   - DCT域水印破坏算法
 *
 * 依赖：sharp（用于图像解码/编码），纯JS实现FFT
 */

import sharp from 'sharp';

// ============================================================
// 简化的 2D FFT 实现（基于 Cooley-Tukey 算法）
// 注：对于生产环境，建议使用 fft.js 或 ndarray-fft 等专业库
// ============================================================

interface Complex {
  re: number;
  im: number;
}

/** 1D FFT（Cooley-Tukey 迭代版本） */
function fft1d(signal: Complex[]): Complex[] {
  const n = signal.length;
  if (n <= 1) return signal;

  // 位反转排列
  const result = new Array<Complex>(n);
  for (let i = 0; i < n; i++) {
    result[i] = { ...signal[i] };
  }

  let j = 0;
  for (let i = 1; i < n; i++) {
    let bit = n >> 1;
    while (j & bit) {
      j ^= bit;
      bit >>= 1;
    }
    j ^= bit;
    if (i < j) {
      [result[i], result[j]] = [result[j], result[i]];
    }
  }

  // 蝶形运算
  for (let len = 2; len <= n; len <<= 1) {
    const angle = (-2 * Math.PI) / len;
    const wRe = Math.cos(angle);
    const wIm = Math.sin(angle);

    for (let i = 0; i < n; i += len) {
      let curRe = 1;
      let curIm = 0;

      for (let k = 0; k < len / 2; k++) {
        const uRe = result[i + k].re;
        const uIm = result[i + k].im;
        const vRe = result[i + k + len / 2].re * curRe - result[i + k + len / 2].im * curIm;
        const vIm = result[i + k + len / 2].re * curIm + result[i + k + len / 2].im * curRe;

        result[i + k] = { re: uRe + vRe, im: uIm + vIm };
        result[i + k + len / 2] = { re: uRe - vRe, im: uIm - vIm };

        const newCurRe = curRe * wRe - curIm * wIm;
        curIm = curRe * wIm + curIm * wRe;
        curRe = newCurRe;
      }
    }
  }

  return result;
}

/** 1D IFFT */
function ifft1d(spectrum: Complex[]): Complex[] {
  const n = spectrum.length;
  // 共轭 → FFT → 共轭 → 除以N
  const conjugated = spectrum.map(c => ({ re: c.re, im: -c.im }));
  const result = fft1d(conjugated);
  return result.map(c => ({ re: c.re / n, im: -c.im / n }));
}

// ============================================================
// 频域扰动策略
// ============================================================

/**
 * 对单行像素数据进行频域扰动
 * 在频谱的中高频区域添加微小随机相位扰动
 * 幅度扰动量：< 0.5%（人眼不可见）
 */
function perturbFrequencyRow(row: number[], perturbStrength: number = 0.003): number[] {
  const n = row.length;

  // 构建复数信号
  const signal: Complex[] = row.map(v => ({ re: v, im: 0 }));

  // FFT
  const spectrum = fft1d(signal);

  // 在频谱中高频区域添加随机扰动
  // 低频区域（前5%）保留，避免影响整体亮度和色调
  const lowFreqCutoff = Math.floor(n * 0.05);
  const highFreqCutoff = Math.floor(n * 0.45); // 超过奈奎斯特频率的一半

  for (let k = lowFreqCutoff; k < highFreqCutoff; k++) {
    // 随机相位扰动（不改变幅度，只改变相位）
    const phaseNoise = (Math.random() - 0.5) * perturbStrength * 2 * Math.PI;
    const magnitude = Math.sqrt(spectrum[k].re ** 2 + spectrum[k].im ** 2);
    const phase = Math.atan2(spectrum[k].im, spectrum[k].re) + phaseNoise;

    spectrum[k] = {
      re: magnitude * Math.cos(phase),
      im: magnitude * Math.sin(phase),
    };

    // 保持共轭对称性（确保IFFT结果为实数）
    if (n - k > highFreqCutoff) {
      spectrum[n - k] = {
        re: magnitude * Math.cos(-phase),
        im: magnitude * Math.sin(-phase),
      };
    }
  }

  // IFFT
  const result = ifft1d(spectrum);

  // 返回实部，限制在 [0, 255]
  return result.map(c => Math.max(0, Math.min(255, Math.round(c.re))));
}

// ============================================================
// 主函数：频域处理
// ============================================================

export interface FrequencyProcessorOptions {
  /** 扰动强度（0.001=极轻微, 0.005=标准, 0.01=较强） */
  perturbStrength?: number;
  /** 是否对所有行处理（true=全图, false=每隔一行，更快） */
  processAllRows?: boolean;
  /** 处理的颜色通道（'luminance'=仅亮度, 'all'=全通道） */
  channelMode?: 'luminance' | 'all';
}

/**
 * 对图片进行频域扰动处理
 * 破坏AI生成图片的频域特征和隐水印
 *
 * @param imageBase64 纯 base64 字符串
 * @param options 处理选项
 * @returns 处理后的纯 base64 字符串
 */
export async function applyFrequencyPerturbation(
  imageBase64: string,
  options: FrequencyProcessorOptions = {}
): Promise<string> {
  const {
    perturbStrength = 0.004,
    processAllRows = false, // 默认每隔一行处理（性能优化）
    channelMode = 'luminance',
  } = options;

  try {
    const imageBuffer = Buffer.from(imageBase64, 'base64');

    // 获取图片原始像素数据
    const { data, info } = await sharp(imageBuffer)
      .raw()
      .toBuffer({ resolveWithObject: true });

    const { width, height, channels } = info;
    const pixelData = new Uint8Array(data);

    if (channelMode === 'luminance') {
      // 仅对亮度通道（Y）进行频域处理
      // 先转换到 YCbCr，处理 Y 通道，再转回 RGB
      for (let y = 0; y < height; y++) {
        // 性能优化：每隔一行处理
        if (!processAllRows && y % 2 !== 0) continue;

        // 提取当前行的亮度值（Y = 0.299R + 0.587G + 0.114B）
        const rowLuminance: number[] = [];
        for (let x = 0; x < width; x++) {
          const idx = (y * width + x) * channels;
          const r = pixelData[idx];
          const g = pixelData[idx + 1];
          const b = pixelData[idx + 2];
          rowLuminance.push(0.299 * r + 0.587 * g + 0.114 * b);
        }

        // 频域扰动
        const perturbedLuminance = perturbFrequencyRow(rowLuminance, perturbStrength);

        // 将扰动量反映到 RGB 通道（保持色调，只改变亮度）
        for (let x = 0; x < width; x++) {
          const idx = (y * width + x) * channels;
          const origLum = rowLuminance[x];
          const newLum = perturbedLuminance[x];
          const delta = newLum - origLum;

          // 按比例调整 RGB（保持色调不变）
          if (origLum > 0) {
            const scale = newLum / origLum;
            pixelData[idx] = Math.max(0, Math.min(255, Math.round(pixelData[idx] * scale)));
            pixelData[idx + 1] = Math.max(0, Math.min(255, Math.round(pixelData[idx + 1] * scale)));
            pixelData[idx + 2] = Math.max(0, Math.min(255, Math.round(pixelData[idx + 2] * scale)));
          } else {
            // 纯黑像素，直接加 delta
            const d = Math.round(delta);
            pixelData[idx] = Math.max(0, Math.min(255, pixelData[idx] + d));
            pixelData[idx + 1] = Math.max(0, Math.min(255, pixelData[idx + 1] + d));
            pixelData[idx + 2] = Math.max(0, Math.min(255, pixelData[idx + 2] + d));
          }
        }
      }
    } else {
      // 对所有颜色通道分别进行频域处理
      for (let c = 0; c < Math.min(channels, 3); c++) {
        for (let y = 0; y < height; y++) {
          if (!processAllRows && y % 2 !== 0) continue;

          const row: number[] = [];
          for (let x = 0; x < width; x++) {
            row.push(pixelData[(y * width + x) * channels + c]);
          }

          const perturbed = perturbFrequencyRow(row, perturbStrength);

          for (let x = 0; x < width; x++) {
            pixelData[(y * width + x) * channels + c] = perturbed[x];
          }
        }
      }
    }

    // 重新编码为 JPEG
    const resultBuffer = await sharp(Buffer.from(pixelData), {
      raw: { width, height, channels }
    }).jpeg({ quality: 92 }).toBuffer();

    console.log(`[FrequencyProcessor] ✓ 频域扰动完成 (${width}x${height}, strength=${perturbStrength})`);
    return resultBuffer.toString('base64');

  } catch (err) {
    console.error('[FrequencyProcessor] 频域处理失败，返回原始图片:', err);
    return imageBase64;
  }
}

/**
 * 轻量级频域处理：仅对图片边缘区域进行处理
 * 用于大图片的快速处理（避免全图FFT的性能开销）
 */
export async function applyEdgeFrequencyPerturbation(
  imageBase64: string,
  borderPercent: number = 0.15
): Promise<string> {
  try {
    const imageBuffer = Buffer.from(imageBase64, 'base64');
    const { data, info } = await sharp(imageBuffer)
      .raw()
      .toBuffer({ resolveWithObject: true });

    const { width, height, channels } = info;
    const pixelData = new Uint8Array(data);

    const borderRows = Math.floor(height * borderPercent);

    // 仅处理顶部和底部边缘行
    const rowsToProcess = [
      ...Array.from({ length: borderRows }, (_, i) => i),
      ...Array.from({ length: borderRows }, (_, i) => height - 1 - i),
    ];

    for (const y of rowsToProcess) {
      const row: number[] = [];
      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * channels;
        row.push(0.299 * pixelData[idx] + 0.587 * pixelData[idx + 1] + 0.114 * pixelData[idx + 2]);
      }

      const perturbed = perturbFrequencyRow(row, 0.006);

      for (let x = 0; x < width; x++) {
        const idx = (y * width + x) * channels;
        const origLum = row[x];
        const newLum = perturbed[x];
        if (origLum > 0) {
          const scale = newLum / origLum;
          pixelData[idx] = Math.max(0, Math.min(255, Math.round(pixelData[idx] * scale)));
          pixelData[idx + 1] = Math.max(0, Math.min(255, Math.round(pixelData[idx + 1] * scale)));
          pixelData[idx + 2] = Math.max(0, Math.min(255, Math.round(pixelData[idx + 2] * scale)));
        }
      }
    }

    const resultBuffer = await sharp(Buffer.from(pixelData), {
      raw: { width, height, channels }
    }).jpeg({ quality: 92 }).toBuffer();

    return resultBuffer.toString('base64');
  } catch (err) {
    console.error('[FrequencyProcessor] 边缘频域处理失败:', err);
    return imageBase64;
  }
}
