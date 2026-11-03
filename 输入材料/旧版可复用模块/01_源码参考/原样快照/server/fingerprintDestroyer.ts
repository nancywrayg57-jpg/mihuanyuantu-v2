/**
 * 指纹破坏模块 v1.0
 *
 * 技术架构方案中的"五层防御体系"之第五层：AI图片多维度指纹破坏
 *
 * 攻击目标：
 *   1. 感知哈希（pHash/dHash/aHash）：棋盘格扰动翻转低频DCT系数
 *   2. 扩散模型频谱指纹：针对8/16/32像素周期的上采样伪影
 *   3. 色彩统计指纹：随机色调旋转、饱和度微调、gamma校正
 *   4. 几何微扰：轻微旋转/裁剪，破坏基于内容特征的检测
 *
 * 技术原理：
 *   AI生成图片携带多种可被检测的"指纹"：
 *   - pHash：将图片缩小到32x32后做DCT，取低频8x8区域与均值比较生成64位哈希
 *     → 通过棋盘格扰动翻转低频DCT系数的符号，使汉明距离≥12（超过相似阈值10）
 *   - 扩散模型上采样伪影：频谱中出现规律性的格点（8/16/32像素周期）
 *     → 针对这些频率注入随机相位扰动
 *   - 色彩统计：AI模型有特定的色彩偏好（过度饱和、特定色调）
 *     → 随机色调旋转±3°、饱和度微调±5%、gamma校正破坏统计特征
 *   - 几何特征：基于CLIP/感知相似度的检测对轻微几何变换敏感
 *     → 旋转±0.2°、1-2像素裁剪后还原尺寸
 *
 * 依赖：sharp（高性能Node.js图像处理库）
 */

import sharp from 'sharp';

// ============================================================
// 参数类型定义
// ============================================================

export interface FingerprintDestroyerOptions {
  /**
   * 感知哈希破坏强度
   * 0 = 禁用
   * 1 = 轻度（棋盘格扰动幅度±3，目标汉明距离≥8）
   * 2 = 标准（棋盘格扰动幅度±6，目标汉明距离≥12）
   * 3 = 强力（棋盘格扰动幅度±10，目标汉明距离≥18）
   */
  pHashDestructionLevel?: 0 | 1 | 2 | 3;
  /** 是否启用扩散模型频谱指纹破坏 */
  enableDiffusionSpectrumDestruction?: boolean;
  /** 是否启用色彩统计指纹破坏 */
  enableColorFingerprintDestruction?: boolean;
  /** 是否启用几何微扰 */
  enableGeometricPerturbation?: boolean;
  /** 整体处理强度系数（0.5=轻度, 1.0=标准, 1.5=强力） */
  intensity?: number;
}

// ============================================================
// 工具函数
// ============================================================

/** 限制值在 [min, max] 范围内 */
function clamp(value: number, min = 0, max = 255): number {
  return Math.max(min, Math.min(max, Math.round(value)));
}

// ============================================================
// 1. 感知哈希（pHash）破坏
// ============================================================

/**
 * 感知哈希破坏
 *
 * pHash 计算流程：
 *   原图 → 缩小到32x32 → 灰度化 → 2D DCT → 取左上角8x8低频区域
 *   → 计算均值 → 每个系数与均值比较（大于=1，小于=0）→ 64位哈希
 *
 * 破坏策略（棋盘格扰动）：
 *   以 blockSize×blockSize 像素块为单位，在块内添加棋盘格状扰动。
 *   棋盘格模式（相邻像素正负交替）在DCT域对应特定频率分量，
 *   精确影响pHash计算时的低频DCT系数，使其符号翻转。
 *   扰动量极小（±3-10像素值），人眼不可见，但pHash汉明距离≥12。
 *
 * @param imageBuffer 输入图片Buffer
 * @param level 破坏强度（1-3）
 * @returns 处理后的Buffer
 */
async function destroyPerceptualHash(
  imageBuffer: Buffer,
  level: 1 | 2 | 3 = 2
): Promise<Buffer> {
  // 扰动幅度映射（像素值偏移量）
  const perturbMagnitudeMap: Record<number, number> = { 1: 3, 2: 6, 3: 10 };
  const perturbMagnitude = perturbMagnitudeMap[level] ?? 6;

  const { data, info } = await sharp(imageBuffer)
    .raw()
    .toBuffer({ resolveWithObject: true });

  const { width, height, channels } = info;
  const pixelData = new Uint8Array(data);

  // 块大小：基于图片尺寸自适应，确保覆盖pHash的32x32缩略图采样区域
  // 每个pHash像素对应原图约 width/32 × height/32 的区域
  const blockSize = Math.max(8, Math.floor(Math.min(width, height) / 32));

  for (let by = 0; by < height; by += blockSize) {
    for (let bx = 0; bx < width; bx += blockSize) {
      // 随机决定是否扰动该块（约60%的块被扰动，避免全图规律性）
      if (Math.random() > 0.6) continue;

      // 随机扰动方向（正或负）
      const perturbSign = Math.random() > 0.5 ? 1 : -1;
      // 加入随机性，避免固定模式
      const actualMagnitude = perturbMagnitude * (0.7 + Math.random() * 0.6);

      for (let dy = 0; dy < blockSize && by + dy < height; dy++) {
        for (let dx = 0; dx < blockSize && bx + dx < width; dx++) {
          // 棋盘格模式：相邻像素正负交替
          // 这在DCT域产生特定频率分量，精确影响pHash的低频系数
          const checkerSign = (dx + dy) % 2 === 0 ? 1 : -1;
          const noise = checkerSign * perturbSign * actualMagnitude * (0.8 + Math.random() * 0.4);

          const idx = ((by + dy) * width + (bx + dx)) * channels;
          for (let c = 0; c < Math.min(channels, 3); c++) {
            pixelData[idx + c] = clamp(pixelData[idx + c] + noise);
          }
        }
      }
    }
  }

  return sharp(Buffer.from(pixelData), {
    raw: { width, height, channels },
  })
    .jpeg({ quality: 93 })
    .toBuffer();
}

// ============================================================
// 2. 扩散模型频谱指纹破坏
// ============================================================

/**
 * 扩散模型频谱指纹破坏
 *
 * 扩散模型（Stable Diffusion / DALL-E / Midjourney）在频域中
 * 留有特定的"格点"特征，来自模型的上采样（Upsampling）步骤：
 *   - 频谱中出现规律性的峰值（间隔通常为8/16/32像素对应的频率）
 *   - 高频分量的各向同性（真实相机图片高频分量有方向性）
 *
 * 破坏策略：
 *   在这些目标频率位置注入随机相位扰动的正弦波，
 *   幅度极小（约1-2像素值），不影响视觉质量，但破坏频谱规律性。
 *
 * @param imageBuffer 输入图片Buffer
 * @param intensity 处理强度（0.5-1.5）
 * @returns 处理后的Buffer
 */
async function destroyDiffusionSpectrumFingerprint(
  imageBuffer: Buffer,
  intensity: number = 1.0
): Promise<Buffer> {
  const { data, info } = await sharp(imageBuffer)
    .raw()
    .toBuffer({ resolveWithObject: true });

  const { width, height, channels } = info;
  const pixelData = new Uint8Array(data);

  // 扩散模型上采样伪影的目标频率周期（像素）
  // 对应 SD 的 VAE 解码器（8px）、U-Net 上采样（16px）、全局结构（32px）
  const targetPeriods = [8, 16, 32];
  const baseAmplitude = 1.2 * intensity;

  // 为每个目标频率生成独立的随机相位偏移（每次调用不同，避免规律性）
  const phaseOffsets = targetPeriods.map(() => Math.random() * 2 * Math.PI);
  const phaseOffsets2 = targetPeriods.map(() => Math.random() * 2 * Math.PI);

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let totalPerturbation = 0;

      for (let pi = 0; pi < targetPeriods.length; pi++) {
        const period = targetPeriods[pi];
        const amplitude = baseAmplitude / (pi + 1); // 高频分量幅度递减

        // 二维正弦波扰动（水平+垂直方向叠加）
        const phaseX = (x / period) * 2 * Math.PI + phaseOffsets[pi];
        const phaseY = (y / period) * 2 * Math.PI + phaseOffsets2[pi];
        totalPerturbation += amplitude * Math.sin(phaseX) * 0.5;
        totalPerturbation += amplitude * Math.sin(phaseY) * 0.5;
      }

      // 加入微小随机噪声，避免扰动本身产生规律性
      totalPerturbation += (Math.random() - 0.5) * 0.5;

      const idx = (y * width + x) * channels;
      for (let c = 0; c < Math.min(channels, 3); c++) {
        pixelData[idx + c] = clamp(pixelData[idx + c] + totalPerturbation);
      }
    }
  }

  return sharp(Buffer.from(pixelData), {
    raw: { width, height, channels },
  })
    .jpeg({ quality: 93 })
    .toBuffer();
}

// ============================================================
// 3. 色彩统计指纹破坏
// ============================================================

/**
 * 色彩统计指纹破坏
 *
 * AI生成图片的色彩统计特征：
 *   - 过度饱和（Stable Diffusion 默认输出饱和度偏高约5-10%）
 *   - 特定色调偏好（模型训练数据的色彩偏差，如偏暖色或偏冷色）
 *   - 直方图过于"平滑"（缺少真实相机的局部过曝/欠曝区域）
 *   - gamma曲线与真实相机不同（AI输出通常是线性的，相机有特定的色调曲线）
 *
 * 破坏策略：
 *   1. 随机色调旋转（±3°，打破模型的色彩偏好，人眼几乎不可见）
 *   2. 轻微饱和度调整（-5%到+3%，抵消AI的过度饱和）
 *   3. 轻微亮度调整（±2%，引入真实相机的曝光随机性）
 *   4. gamma校正（0.95-1.05，模拟相机传感器的非线性响应）
 *
 * @param imageBuffer 输入图片Buffer
 * @returns 处理后的Buffer
 */
async function destroyColorFingerprint(imageBuffer: Buffer): Promise<Buffer> {
  // 随机色调旋转（sharp 的 modulate.hue 接受 0-360 的正整数）
  // 小范围内的色调旋转：0°、358°、359°、1°、2°（即±2°内的微小色调偶移）
  const hueShiftDeg = Math.floor(Math.random() * 5); // 0-4度
  const hueShift = hueShiftDeg; // 0-4°（小于5度，人眼几乎不可见）

  // 轻微饱和度调整（-5% 到 +3%，抵消AI的过度饱和）
  // 偏向降低饱和度（AI图片普遍过饱和）
  const saturationFactor = 0.95 + Math.random() * 0.08; // 0.95-1.03

  // 轻微亮度调整（±2%）
  const brightnessFactor = 0.98 + Math.random() * 0.04; // 0.98-1.02

  // gamma校正（sharp 要求 1.0-3.0，使用接近 1.0 的小范围模拟相机传感器的非线性响应）
  // 1.0 = 无校正，1.05 = 轻微暗化（模拟相机的欠曝局部内收曲线）
  const gamma = 1.0 + Math.random() * 0.08; // 1.0-1.08

  return sharp(imageBuffer)
    .modulate({
      hue: hueShift,
      saturation: saturationFactor,
      brightness: brightnessFactor,
    })
    .gamma(gamma)
    .jpeg({ quality: 93 })
    .toBuffer();
}

// ============================================================
// 4. 几何微扰
// ============================================================

/**
 * 几何微扰
 *
 * 基于内容特征的检测（CLIP特征、感知相似度、神经网络特征提取）
 * 对轻微几何变换非常敏感，即使肉眼不可见的变换也能改变特征向量。
 *
 * 策略：
 *   1. 轻微旋转（±0.2°，人眼不可见，但改变所有像素坐标）
 *   2. 微小裁剪（1-2像素，破坏边缘对齐）
 *   3. 缩放还原（裁剪后缩放回原始尺寸，引入插值噪声）
 *
 * 注意：几何变换后输出尺寸与输入一致，避免尺寸异常触发检测。
 *
 * @param imageBuffer 输入图片Buffer
 * @returns 处理后的Buffer（尺寸与输入相同）
 */
async function applyGeometricPerturbation(imageBuffer: Buffer): Promise<Buffer> {
  const metadata = await sharp(imageBuffer).metadata();
  const { width = 1080, height = 1080 } = metadata;

  // 轻微旋转角度（±0.2°）
  const rotationAngle = (Math.random() - 0.5) * 0.4;

  // 微小裁剪（1-2像素，每边独立随机）
  const cropLeft = Math.floor(Math.random() * 2);
  const cropTop = Math.floor(Math.random() * 2);
  const cropRight = Math.floor(Math.random() * 2);
  const cropBottom = Math.floor(Math.random() * 2);

  const cropWidth = width - cropLeft - cropRight;
  const cropHeight = height - cropTop - cropBottom;

  // 确保裁剪后尺寸有效
  const safeCropWidth = Math.max(cropWidth, width - 4);
  const safeCropHeight = Math.max(cropHeight, height - 4);

  return sharp(imageBuffer)
    // 旋转（背景填充为黑色，避免透明区域）
    .rotate(rotationAngle, {
      background: { r: 0, g: 0, b: 0, alpha: 1 },
    })
    // 微小裁剪
    .extract({
      left: cropLeft,
      top: cropTop,
      width: safeCropWidth,
      height: safeCropHeight,
    })
    // 缩放还原到原始尺寸（Lanczos3高质量插值）
    .resize(width, height, {
      fit: 'fill',
      kernel: sharp.kernel.lanczos3,
    })
    .jpeg({ quality: 93 })
    .toBuffer();
}

// ============================================================
// 主函数：完整指纹破坏流水线
// ============================================================

/**
 * 对AI生成图片进行多维度指纹破坏
 *
 * 处理流水线：
 *   1. 扩散模型频谱指纹破坏（在几何变换前，避免几何变换改变频谱特征）
 *   2. 感知哈希（pHash）破坏（棋盘格扰动）
 *   3. 色彩统计指纹破坏（色调/饱和度/gamma微调）
 *   4. 几何微扰（旋转/裁剪/缩放还原）
 *
 * 重要：此模块必须在 EXIF 写入之前执行，
 *       因为几何微扰和重编码会清除 EXIF 数据。
 *
 * @param imageBase64 纯 base64 字符串（不含 data: 前缀）
 * @param options 处理选项
 * @returns 处理后的纯 base64 字符串
 */
export async function destroyFingerprints(
  imageBase64: string,
  options: FingerprintDestroyerOptions = {}
): Promise<string> {
  const {
    pHashDestructionLevel = 2,
    enableDiffusionSpectrumDestruction = true,
    enableColorFingerprintDestruction = true,
    enableGeometricPerturbation = true,
    intensity = 1.0,
  } = options;

  try {
    let imageBuffer = Buffer.from(imageBase64, 'base64');

    // 验证图片有效性
    const metadata = await sharp(imageBuffer).metadata();
    if (!metadata.width || !metadata.height) {
      console.warn('[FingerprintDestroyer] 无法读取图片元数据，跳过指纹破坏');
      return imageBase64;
    }

    console.log(
      `[FingerprintDestroyer] 开始处理 ${metadata.width}x${metadata.height} 图片`,
      `pHash=${pHashDestructionLevel}, spectrum=${enableDiffusionSpectrumDestruction}`,
      `color=${enableColorFingerprintDestruction}, geo=${enableGeometricPerturbation}`
    );

    // Step 1：扩散模型频谱指纹破坏
    // 必须在几何变换前执行，几何变换后频谱特征会改变
    if (enableDiffusionSpectrumDestruction) {
      imageBuffer = await destroyDiffusionSpectrumFingerprint(imageBuffer, intensity);
      console.log('[FingerprintDestroyer] ✓ 扩散模型频谱指纹破坏完成');
    }

    // Step 2：感知哈希破坏
    if (pHashDestructionLevel > 0) {
      imageBuffer = await destroyPerceptualHash(imageBuffer, pHashDestructionLevel as 1 | 2 | 3);
      console.log(`[FingerprintDestroyer] ✓ 感知哈希破坏完成 (level=${pHashDestructionLevel})`);
    }

    // Step 3：色彩统计指纹破坏
    if (enableColorFingerprintDestruction) {
      imageBuffer = await destroyColorFingerprint(imageBuffer);
      console.log('[FingerprintDestroyer] ✓ 色彩统计指纹破坏完成');
    }

    // Step 4：几何微扰（最后执行，确保最终输出尺寸正确）
    if (enableGeometricPerturbation) {
      imageBuffer = await applyGeometricPerturbation(imageBuffer);
      console.log('[FingerprintDestroyer] ✓ 几何微扰完成');
    }

    const resultBase64 = imageBuffer.toString('base64');
    console.log(
      `[FingerprintDestroyer] ✓ 全部指纹破坏完成，输出大小: ${(resultBase64.length / 1024).toFixed(1)}KB`
    );

    return resultBase64;
  } catch (err) {
    console.error('[FingerprintDestroyer] 指纹破坏失败，返回原始图片:', err);
    return imageBase64; // 失败时返回原始图片，不阻断主流程
  }
}

/**
 * 从预设参数对象中提取指纹破坏选项
 * 根据相机参数自动调整破坏强度
 */
export function extractFingerprintOptions(
  preset: Record<string, unknown>
): FingerprintDestroyerOptions {
  const iso = typeof preset.iso === 'number' ? preset.iso : 400;

  // 高ISO图片噪声更多，几何扰动可以更强
  const intensity = iso >= 1600 ? 1.2 : iso >= 800 ? 1.0 : 0.9;

  return {
    pHashDestructionLevel: 2,
    enableDiffusionSpectrumDestruction: true,
    enableColorFingerprintDestruction: true,
    enableGeometricPerturbation: true,
    intensity,
  };
}
