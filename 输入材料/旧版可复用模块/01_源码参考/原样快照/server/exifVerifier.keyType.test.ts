/**
 * Issue #7: EXIF verifier 严格按 key_type='verify' 选择 API KEY，
 * 不得复用 img2img / image_gen / ai_optimize 用途的 KEY。
 *
 * 与 exifVerifier.test.ts 互补：本文件用 vi.spyOn 同时监听其他 key_type
 * 的 rds 函数，断言它们绝不被 verifyExifWithGemini 触达。
 *
 * 所有外部 HTTP 通过 mock fetch 验证，不发出任何真实请求。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as rds from "./rds";
import { verifyExifWithGemini } from "./exifVerifier";

const validVerifyJson = JSON.stringify({
  passed: true,
  confidence: 88,
  score: 91,
  conclusion: "looks real",
  suggestions: [],
  dimensions: {
    noise: 90,
    depthOfField: 85,
    lighting: 92,
    colorRealism: 90,
    overallRealism: 91,
  },
});

describe("exifVerifier 不复用 img2img/image_gen/ai_optimize KEY", () => {
  const originalFetch = global.fetch;
  let getVerifySpy: ReturnType<typeof vi.spyOn>;
  let getImg2ImgSpy: ReturnType<typeof vi.spyOn>;
  let getImageGenSpy: ReturnType<typeof vi.spyOn>;
  let getAiOptimizeSpy: ReturnType<typeof vi.spyOn>;
  let rotateSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    getVerifySpy = vi.spyOn(rds, "getVerifyApiKey");
    getImg2ImgSpy = vi.spyOn(rds, "getImg2ImgApiKey");
    getImageGenSpy = vi.spyOn(rds, "getImageGenApiKey");
    getAiOptimizeSpy = vi.spyOn(rds, "getAiOptimizeApiKey");
    rotateSpy = vi.spyOn(rds, "rotateApiKey");
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
    delete process.env.GEMINI_API_KEY;
  });

  it("成功路径仅访问 getVerifyApiKey，绝不调用其他 key_type 的 getter", async () => {
    getVerifySpy.mockResolvedValue({
      id: 1,
      provider: "gemini",
      key_value: "verify-only-key",
      model_version: "gemini-2.5-flash",
      api_format: "gemini",
      base_url: null,
    } as any);

    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            candidates: [{ content: { parts: [{ text: validVerifyJson }] } }],
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        )
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    await verifyExifWithGemini("ZmFrZS1iYXNlNjQ=");

    expect(getVerifySpy).toHaveBeenCalledTimes(1);
    expect(getImg2ImgSpy).not.toHaveBeenCalled();
    expect(getImageGenSpy).not.toHaveBeenCalled();
    expect(getAiOptimizeSpy).not.toHaveBeenCalled();
    expect(rotateSpy).not.toHaveBeenCalled();
  });

  it("数据库与 GEMINI_API_KEY 同时缺失时抛错，且不读取其他 key_type", async () => {
    getVerifySpy.mockResolvedValue(null);
    // 模拟其他 key_type 是“可用”的：如果代码错误地回退就会被使用
    getImg2ImgSpy.mockResolvedValue({
      id: 2,
      provider: "qwen",
      key_value: "img2img-leak",
      model_version: "qwen-vl-plus",
    } as any);
    getAiOptimizeSpy.mockResolvedValue({
      id: 3,
      provider: "openai",
      key_value: "ai-optimize-leak",
      model_version: "gpt-4o-mini",
    } as any);

    const fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(verifyExifWithGemini("ZmFrZS1iYXNlNjQ=")).rejects.toThrow(
      /Missing verify API key/
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(getImg2ImgSpy).not.toHaveBeenCalled();
    expect(getAiOptimizeSpy).not.toHaveBeenCalled();
  });
});
