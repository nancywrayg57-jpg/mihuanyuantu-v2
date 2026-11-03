/**
 * EXIF 写入验证服务
 * 从数据库读取管理员配置的活跃 API Key（按优先级轮询），
 * 支持 Gemini / OpenAI / Claude / DeepSeek / Kimi / 豆包 / 阿里千问 / 智谱 等多平台
 */

import * as rds from './rds';
import {
  resolveProviderProtocol,
  PROVIDER_DEFAULT_BASE_URLS as CATALOG_DEFAULT_BASE_URLS,
  PROVIDER_DEFAULT_VERIFY_MODELS as CATALOG_DEFAULT_VERIFY_MODELS,
} from '@shared/aiProviderCatalog';

export interface ExifVerificationResult {
  /** 是否通过验证（看起来像真实相机拍摄） */
  passed: boolean;
  /** 置信度 0-100 */
  confidence: number;
  /** 综合评分 0-100（越高越像真实照片） */
  score: number;
  /** 检测到的相机信息 */
  detectedCamera?: string;
  /** 检测到的拍摄场景 */
  detectedScene?: string;
  /** AI 检测结论 */
  conclusion: string;
  /** 改进建议 */
  suggestions: string[];
  /** 各维度评分 */
  dimensions: {
    noise: number;
    depthOfField: number;
    lighting: number;
    colorRealism: number;
    overallRealism: number;
  };
  /** 使用的平台和模型 */
  usedProvider?: string;
  usedModel?: string;
  /** 原始 AI 响应（调试用）*/
  rawResponse?: string;
  /** 验证耗时（ms）*/
  verificationTime: number;
}

/**
 * 安全解析 HTTP 响应为 JSON，避免 HTML 错误页导致 JSON.parse 崩溃
 */
async function safeResJson(res: Response, apiName: string): Promise<any> {
  const ct = res.headers.get('content-type') ?? '';
  if (ct.includes('text/html')) {
    const snippet = (await res.text().catch(() => '')).slice(0, 200);
    throw new Error(`${apiName} 返回了 HTML 页面（可能是网关错误或 API 地址错误）。状态码: ${res.status}。内容: ${snippet}`);
  }
  try {
    return await res.json();
  } catch {
    const body = await res.text().catch(() => '');
    throw new Error(`${apiName} 响应无法解析为 JSON（状态码 ${res.status}）。内容: ${body.slice(0, 200)}`);
  }
}

/** 判断错误是否为临时性错误（可重试） */
export function isTransientError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const msg = err.message.toLowerCase();
  return (
    msg.includes('timeout') ||
    msg.includes('econnreset') ||
    msg.includes('econnrefused') ||
    msg.includes('socket hang up') ||
    msg.includes('network') ||
    msg.includes('etimedout') ||
    msg.includes('fetch failed') ||
    msg.includes('rate limit') ||
    msg.includes('503') ||
    msg.includes('502') ||
    msg.includes('504') ||
    msg.includes('too many requests')
  );
}

/** 构造统一的视觉分析 prompt */
function buildPrompt(presetInfo?: {
  cameraMake?: string;
  cameraModel?: string;
  lensModel?: string;
  iso?: number;
  shutterSpeed?: string;
  aperture?: number;
  software?: string;
}): string {
  const presetContext = presetInfo
    ? `图片已写入以下 EXIF 元数据：
- 相机品牌: ${presetInfo.cameraMake ?? '未知'}
- 相机型号: ${presetInfo.cameraModel ?? '未知'}
- 镜头型号: ${presetInfo.lensModel ?? '未知'}
- ISO: ${presetInfo.iso ?? '未知'}
- 快门速度: ${presetInfo.shutterSpeed ?? '未知'}
- 光圈: f/${presetInfo.aperture ?? '未知'}
- 后期软件: ${presetInfo.software ?? '未知'}`
    : '图片已写入相机 EXIF 元数据';

  return `你是一位专业的图片真实性检测专家，专门分析图片是否来自真实相机拍摄。

${presetContext}

请从以下维度分析这张图片，判断它是否能通过社交媒体平台（如 TikTok、小红书）的 AI 检测：

1. **噪点和颗粒感**（0-100分）：真实相机在高 ISO 下会产生自然噪点，AI 生成图片往往过于平滑
2. **景深和焦外虚化**（0-100分）：真实镜头的散景（bokeh）有特定的光学特征
3. **光线和曝光自然度**（0-100分）：真实场景的光线有自然的高光溢出、阴影细节等
4. **色彩真实性**（0-100分）：真实相机的色彩渲染与 AI 生成有微妙差异
5. **整体真实感**（0-100分）：综合判断

请以 JSON 格式返回分析结果（不要包含任何其他文字）：
{
  "passed": true/false,
  "confidence": 0-100,
  "score": 0-100,
  "detectedCamera": "检测到的相机特征描述",
  "detectedScene": "检测到的拍摄场景",
  "conclusion": "一句话总结检测结论",
  "suggestions": ["改进建议1", "改进建议2"],
  "dimensions": {
    "noise": 0-100,
    "depthOfField": 0-100,
    "lighting": 0-100,
    "colorRealism": 0-100,
    "overallRealism": 0-100
  }
}

判断标准：score >= 75 且 passed = true 表示可能通过平台检测。`;
}

/** 解析 AI 返回的 JSON 文本 */
function parseAIResponse(rawText: string): Omit<ExifVerificationResult, 'verificationTime' | 'rawResponse' | 'usedProvider' | 'usedModel'> {
  const jsonMatch = rawText.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error(`AI 返回格式异常: ${rawText.slice(0, 200)}`);
  return JSON.parse(jsonMatch[0]);
}

// ==================== 各平台调用实现 ====================

/**
 * 平台默认 endpoint / 默认验证模型均来自共享目录（SSOT）。
 * 这里保留具名 re-export，兼容 apiKeyConnectivity.ts 等既有导入方，
 * 同时消除历史上散落在多处的重复常量（Issue #8）。
 */
export const PROVIDER_DEFAULT_BASE_URLS = CATALOG_DEFAULT_BASE_URLS;
export const PROVIDER_DEFAULT_VERIFY_MODELS = CATALOG_DEFAULT_VERIFY_MODELS;

function trimTrailingSlash(s: string): string {
  return s.replace(/\/+$/, '');
}

async function callGemini(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.gemini);
  const url = `${base}/models/${model}:generateContent?key=${apiKey}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }, { inline_data: { mime_type: 'image/jpeg', data: imageBase64 } }] }],
      generationConfig: { temperature: 0.1, maxOutputTokens: 1024 },
    }),
    signal: AbortSignal.timeout(60000),  // 60s：视觉模型处理图片较慢
  });
  if (!res.ok) throw new Error(`Gemini API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, 'Gemini API') as any;
  return data?.candidates?.[0]?.content?.parts?.[0]?.text ?? '';
}

async function callOpenAI(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.openai);
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}`, detail: 'high' } }] }],
      max_tokens: 1024,
      temperature: 0.1,
    }),
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`OpenAI API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, 'OpenAI API') as any;
  return data?.choices?.[0]?.message?.content ?? '';
}

async function callClaude(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.claude);
  const res = await fetch(`${base}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model,
      max_tokens: 1024,
      messages: [{ role: 'user', content: [{ type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: imageBase64 } }, { type: 'text', text: prompt }] }],
    }),
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`Claude API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, 'Claude API') as any;
  return data?.content?.[0]?.text ?? '';
}

async function callDeepSeek(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.deepseek);
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }] }],
      max_tokens: 1024,
    }),
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`DeepSeek API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, 'DeepSeek API') as any;
  return data?.choices?.[0]?.message?.content ?? '';
}

async function callKimi(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.kimi);
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }] }],
      max_tokens: 1024,
    }),
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`Kimi API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, 'Kimi API') as any;
  return data?.choices?.[0]?.message?.content ?? '';
}

async function callDoubao(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.doubao);
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }] }],
      max_tokens: 1024,
    }),
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`豆包 API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, '豆包 API') as any;
  return data?.choices?.[0]?.message?.content ?? '';
}

async function callQwen(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  // 注意：千问视觉模型（qwen-vl-*、qwen2.5-vl-*）才支持图片输入
  // 纯文本模型（qwen-turbo、qwen-plus 等）不支持 image_url，会返回 400 错误
  const isVisionModel = model.includes('vl') || model.includes('vision');
  const messages = isVisionModel
    ? [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }] }]
    : [{ role: 'user', content: prompt }]; // 纯文本模型降级为仅文本（无图片）

  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.qwen);
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      messages,
      max_tokens: 1024,
    }),
    signal: AbortSignal.timeout(90000),  // 千问视觉模型响应较慢，给90s
  });
  if (!res.ok) throw new Error(`阿里千问 API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, '阿里千问 API') as any;
  return data?.choices?.[0]?.message?.content ?? '';
}

async function callZhipu(apiKey: string, model: string, imageBase64: string, prompt: string, baseUrl?: string): Promise<string> {
  const base = trimTrailingSlash(baseUrl || PROVIDER_DEFAULT_BASE_URLS.zhipu);
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: [{ type: 'text', text: prompt }, { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }] }],
      max_tokens: 1024,
    }),
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`智谱 API 错误 ${res.status}: ${await res.text()}`);
  const data = await safeResJson(res, '智谱 API') as any;
  return data?.choices?.[0]?.message?.content ?? '';
}

/**
 * 根据 provider 调用对应平台。
 *
 * 内置平台走各自的具名实现（行为与历史完全一致）；
 * 未登记的「自定义平台」（管理员在 api_keys 中新增，无需改码）按协议族路由：
 *   - openai-compatible → callOpenAI（DeepSeek/Kimi/豆包/千问/智谱同族）
 *   - gemini            → callGemini
 *   - claude            → callClaude
 * 协议族由 api_format 显式指定（见 resolveProviderProtocol）。
 */
export async function callProvider(
  provider: string,
  apiKey: string,
  model: string,
  imageBase64: string,
  prompt: string,
  baseUrl?: string,
  apiFormat?: string | null
): Promise<string> {
  switch (provider) {
    case 'gemini': return callGemini(apiKey, model, imageBase64, prompt, baseUrl);
    case 'openai': return callOpenAI(apiKey, model, imageBase64, prompt, baseUrl);
    case 'claude': return callClaude(apiKey, model, imageBase64, prompt, baseUrl);
    case 'deepseek': return callDeepSeek(apiKey, model, imageBase64, prompt, baseUrl);
    case 'kimi': return callKimi(apiKey, model, imageBase64, prompt, baseUrl);
    case 'doubao': return callDoubao(apiKey, model, imageBase64, prompt, baseUrl);
    case 'qwen': return callQwen(apiKey, model, imageBase64, prompt, baseUrl);
    case 'zhipu': return callZhipu(apiKey, model, imageBase64, prompt, baseUrl);
    default: {
      // 未登记的自定义平台：按协议族路由，使普通平台新增无需改码。
      const protocol = resolveProviderProtocol(provider, apiFormat);
      switch (protocol) {
        case 'gemini': return callGemini(apiKey, model, imageBase64, prompt, baseUrl);
        case 'claude': return callClaude(apiKey, model, imageBase64, prompt, baseUrl);
        case 'openai-compatible': return callOpenAI(apiKey, model, imageBase64, prompt, baseUrl);
        default:
          throw new Error(
            `不支持的平台: ${provider}（无法判定协议族，请在 API KEY 配置中设置 api_format）`
          );
      }
    }
  }
}

/**
 * 调用管理员配置的 AI 平台验证图片 EXIF 写入效果
 * 自动从数据库轮询活跃 API Key（按优先级）
 */
export async function verifyExifWithGemini(
  imageBase64: string,
  presetInfo?: {
    cameraMake?: string;
    cameraModel?: string;
    lensModel?: string;
    iso?: number;
    shutterSpeed?: string;
    aperture?: number;
    software?: string;
  }
): Promise<ExifVerificationResult> {
  const startTime = Date.now();
  const prompt = buildPrompt(presetInfo);

  // 从数据库获取 verify 用途的活跃 API Key（按优先级轮询）。
  // 严格区分 key_type：verify 不读取 img2img/image_gen/ai_optimize KEY。
  let activeKey:
    | {
        id: number;
        provider: string;
        key_value: string;
        model_version: string | null;
        api_format: string | null;
        base_url: string | null;
      }
    | null = null;
  try {
    activeKey = (await rds.getVerifyApiKey()) as any;
  } catch (e) {
    console.warn('[ExifVerifier] getVerifyApiKey failed:', e);
  }

  // 降级：使用环境变量中的 Gemini Key（仅当数据库无 verify KEY 时）
  const fallbackProvider = 'gemini';
  const fallbackKey = process.env.GEMINI_API_KEY;
  const fallbackModel = process.env.GEMINI_MODEL ?? 'gemini-2.5-flash';

  const provider = activeKey?.provider ?? fallbackProvider;
  const keyValue = activeKey?.key_value ?? fallbackKey;
  if (!keyValue) {
    throw new Error(
      '[ExifVerifier] Missing verify API key. 请在 API KEY 管理中添加 key_type=verify 的 KEY，或设置 GEMINI_API_KEY 环境变量。'
    );
  }

  const model =
    activeKey?.model_version ||
    PROVIDER_DEFAULT_VERIFY_MODELS[provider] ||
    (provider === 'gemini' ? fallbackModel : '');

  if (!model) {
    return {
      passed: false,
      confidence: 0,
      score: 0,
      conclusion: `EXIF 验证服务不可用：平台 ${provider} 未配置模型版本，请在 API KEY 管理中设置模型版本`,
      suggestions: ['请联系管理员在 API KEY 管理页面配置模型版本'],
      dimensions: { noise: 0, depthOfField: 0, lighting: 0, colorRealism: 0, overallRealism: 0 },
      usedProvider: provider,
      verificationTime: Date.now() - startTime,
    };
  }

  const baseUrl = activeKey?.base_url || undefined;

  try {
    const rawText = await callProvider(provider, keyValue, model, imageBase64, prompt, baseUrl, activeKey?.api_format);
    const parsed = parseAIResponse(rawText);

    return {
      ...parsed,
      usedProvider: provider,
      usedModel: model,
      verificationTime: Date.now() - startTime,
      rawResponse: rawText,
    };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    console.error(`[ExifVerifier] ${provider}/${model} 调用失败:`, errorMsg);
    return {
      passed: false,
      confidence: 0,
      score: 0,
      conclusion: `EXIF 验证服务暂时不可用 (${provider}/${model}): ${errorMsg}`,
      suggestions: ['请稍后手动验证图片真实性', '或在 API KEY 管理中检查 Key 是否有效'],
      dimensions: { noise: 0, depthOfField: 0, lighting: 0, colorRealism: 0, overallRealism: 0 },
      usedProvider: provider,
      usedModel: model,
      verificationTime: Date.now() - startTime,
    };
  }
}
