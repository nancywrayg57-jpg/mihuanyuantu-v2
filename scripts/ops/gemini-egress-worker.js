/**
 * Gemini egress worker (Cloudflare). Deploy only if a durable allowed-region proxy
 * is needed and no VM is available.
 *
 * Why: the production host (Alibaba HK) gets `FAILED_PRECONDITION User location is
 * not supported` from generativelanguage.googleapis.com. A Worker runs on
 * Cloudflare's edge (allowed regions) and forwards a single allowlisted path shape.
 *
 * Contract expected by the app (backend/app/capabilities/realphotos/services/gemini_detector.py):
 *   POST {base_url}/models/{model}:generateContent
 *   header: x-goog-api-key: <GEMINI_API_KEY>
 *   body:   Gemini native JSON
 * So set the final_detection contract base_url (or GEMINI_API_BASE) to:
 *   https://<worker>.<account>.workers.dev/v1beta
 *
 * Security:
 * - only POST .../models/*:generateContent is forwarded;
 * - the caller must present the real Gemini key, and only its SHA-256 is stored in
 *   the Worker secret ALLOWED_KEY_SHA256 (no plaintext key in the Worker);
 * - nothing else is proxied, no arbitrary URLs.
 *
 * Deploy:
 *   wrangler secret put ALLOWED_KEY_SHA256      # sha256 of the Gemini key, hex
 *   wrangler deploy
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method !== "POST") {
      return json({ error: "method_not_allowed" }, 405);
    }
    if (!/^\/v1beta\/models\/[A-Za-z0-9._-]+:generateContent$/.test(url.pathname)) {
      return json({ error: "path_not_allowed" }, 403);
    }

    const key = request.headers.get("x-goog-api-key") || "";
    if (!key || !env.ALLOWED_KEY_SHA256) {
      return json({ error: "unauthorized" }, 401);
    }

    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(key));
    const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
    if (hex !== String(env.ALLOWED_KEY_SHA256).toLowerCase()) {
      return json({ error: "forbidden" }, 403);
    }

    const upstream = "https://generativelanguage.googleapis.com" + url.pathname;
    const body = await request.arrayBuffer();

    let resp;
    try {
      resp = await fetch(upstream, {
        method: "POST",
        headers: { "content-type": "application/json", "x-goog-api-key": key },
        body,
      });
    } catch (err) {
      return json({ error: "upstream_unreachable" }, 502);
    }

    return new Response(resp.body, {
      status: resp.status,
      headers: {
        "content-type": resp.headers.get("content-type") || "application/json",
        "cache-control": "no-store",
      },
    });
  },
};

function json(payload, status) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}
