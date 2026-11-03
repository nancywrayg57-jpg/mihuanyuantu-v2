/**
 * Issue #7: EXIF 验证服务必须按管理员配置的平台 + 模型 + base_url 动态调用，
 * 严格使用 key_type='verify' 的 KEY，不复用 img2img/image_gen/ai_optimize KEY。
 *
 * 所有外部 HTTP 都通过 mock fetch 验证，禁止真实访问 AI 平台。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as rds from "./rds";

const validAiJson = {
  passed: true,
  confidence: 90,
  score: 88,
  detectedCamera: "Canon EOS R6",
  detectedScene: "indoor",
  conclusion: "看起来像真实相机拍摄",
  suggestions: [],
  dimensions: { noise: 85, depthOfField: 80, lighting: 90, colorRealism: 88, overallRealism: 88 },
};

describe("exifVerifier 动态读取 verify KEY 与 base_url", () => {
  const originalFetch = global.fetch;
  let getVerifySpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    getVerifySpy = vi.spyOn(rds, "getVerifyApiKey");
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
    delete process.env.GEMINI_API_KEY;
    delete process.env.GEMINI_MODEL;
  });

  it("数据库中存在 verify KEY 时使用 KEY 配置的 provider/model/base_url，不再读取环境变量", async () => {
    getVerifySpy.mockResolvedValue({
      id: 1,
      provider: "openai",
      key_value: "sk-from-db",
      model_version: "gpt-4o-mini",
      api_format: "openai",
      base_url: "https://corp-proxy.example.com/v1",
    } as any);

    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({ choices: [{ message: { content: JSON.stringify(validAiJson) } }] }),
          { status: 200, headers: { "content-type": "application/json" } }
        )
    );
    global.fetch = fetchMock as unknown as typeof fetch;
    process.env.GEMINI_API_KEY = "fallback-should-not-be-used";

    const { verifyExifWithGemini } = await import("./exifVerifier");
    const result = await verifyExifWithGemini("base64-image");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("https://corp-proxy.example.com/v1/chat/completions");
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer sk-from-db",
    });
    expect(result.usedProvider).toBe("openai");
    expect(result.usedModel).toBe("gpt-4o-mini");
    expect(result.passed).toBe(true);
  });

  it("数据库无 verify KEY 时降级到 GEMINI_API_KEY 环境变量", async () => {
    getVerifySpy.mockResolvedValue(null);
    process.env.GEMINI_API_KEY = "fallback-gemini";

    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            candidates: [{ content: { parts: [{ text: JSON.stringify(validAiJson) }] } }],
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        )
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { verifyExifWithGemini } = await import("./exifVerifier");
    const result = await verifyExifWithGemini("base64-image");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/generativelanguage\.googleapis\.com.+:generateContent\?key=fallback-gemini/);
    expect(result.usedProvider).toBe("gemini");
  });

  it("getVerifyApiKey 抛错时返回降级结果，而不是 throw（保证主流程不中断）", async () => {
    getVerifySpy.mockRejectedValue(new Error("RDS connection refused"));
    process.env.GEMINI_API_KEY = "fallback";

    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            candidates: [{ content: { parts: [{ text: JSON.stringify(validAiJson) }] } }],
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        )
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { verifyExifWithGemini } = await import("./exifVerifier");
    const result = await verifyExifWithGemini("base64-image");
    expect(result.usedProvider).toBe("gemini");
  });
});
