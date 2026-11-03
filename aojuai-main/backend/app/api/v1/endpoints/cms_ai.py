"""
AOJU Backend - CMS AI page generator

POST /api/v1/cms/ai/generate-page

Composes a Puck page document from a natural-language prompt using ONLY the
existing CMS block components (no arbitrary code). If the tenant has an AI
provider configured (via the assistant module) we ask the model for the layout;
otherwise we fall back to a deterministic template so the feature is always
usable. The result is sanitized to known block types before returning.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DBSession, PermissionChecker
from app.core.response import SuccessResponse

router = APIRouter()

# Block contract shared with frontend Puck config (components/cms/puck-config.tsx).
ALLOWED_BLOCKS = {"Hero", "Stats", "Features", "Pricing", "FAQ", "CTA", "RichText"}

BLOCK_SCHEMA_HINT = """
You compose marketing pages using ONLY these block types (Puck components). Output JSON only.
Document shape: {"root":{"props":{}},"zones":{},"content":[ {"type": <BlockType>, "props": {...}} ]}
Block props:
- Hero: { eyebrow, title, subtitle, primaryText, primaryHref, secondaryText, secondaryHref, image }
- Stats: { items: [{ value, label }] }
- Features: { title, subtitle, columns ("2"|"3"), items: [{ icon (one of shield|zap|layout|credit-card|bell|mic|star|sparkles), title, description }] }
- Pricing: { title, subtitle, plans: [{ name, price, period, description, features: [{value}], ctaText, ctaHref, highlighted (bool) }] }
- FAQ: { title, items: [{ question, answer }] }
- CTA: { title, subtitle, buttonText, buttonHref }
- RichText: { content (markdown) }
Compose a coherent landing page (usually Hero, then Features and/or Pricing, then FAQ/CTA).
Write copy in the SAME language as the user's request. Return JSON only, no prose.
"""


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2000)


def _norm_block(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    btype = item.get("type")
    if btype not in ALLOWED_BLOCKS:
        return None
    props = item.get("props")
    return {"type": btype, "props": props if isinstance(props, dict) else {}}


def _sanitize(doc: Any) -> dict[str, Any] | None:
    """Keep only the known Puck shape + allowed block types."""
    if not isinstance(doc, dict):
        return None
    content = doc.get("content")
    if not isinstance(content, list):
        return None
    blocks = [b for b in (_norm_block(x) for x in content) if b]
    if not blocks:
        return None
    return {"root": {"props": {}}, "zones": {}, "content": blocks}


def _template(prompt: str) -> dict[str, Any]:
    """Deterministic fallback: a sensible landing page seeded from the prompt."""
    title = prompt.strip().split("\n")[0][:40] or "你的产品"
    return {
        "root": {"props": {}},
        "zones": {},
        "content": [
            {"type": "Hero", "props": {
                "eyebrow": "AI 生成草稿",
                "title": title,
                "subtitle": prompt.strip()[:160],
                "primaryText": "免费开始", "primaryHref": "/register",
                "secondaryText": "联系我们", "secondaryHref": "/contact", "image": "",
            }},
            {"type": "Features", "props": {
                "title": "核心亮点", "subtitle": "", "columns": "3",
                "items": [
                    {"icon": "zap", "title": "高效", "description": "围绕你的目标快速落地。"},
                    {"icon": "shield", "title": "可靠", "description": "企业级安全与稳定性。"},
                    {"icon": "sparkles", "title": "智能", "description": "AI 驱动的体验。"},
                ],
            }},
            {"type": "CTA", "props": {
                "title": "现在就开始", "subtitle": "几分钟即可上线。",
                "buttonText": "免费创建", "buttonHref": "/register",
            }},
        ],
    }


async def _resolve_provider(db, tenant_id: int) -> dict[str, Any] | None:
    """CMS-scoped AI config (mode=custom) else inherit the system/assistant config."""
    from app.core.provider_settings import build_openai_provider_settings
    from app.domain.assistant.config_service import AssistantConfigService
    from app.domain.cms.service import CmsSiteSettingsService

    ai_cfg = await CmsSiteSettingsService(db).get_ai_config(tenant_id=tenant_id)
    settings = None
    if (ai_cfg.get("mode") or "inherit") == "custom":
        settings = build_openai_provider_settings(
            base_url=ai_cfg.get("baseUrl"),
            api_key=CmsSiteSettingsService.decrypt_ai_key(ai_cfg),
            model=ai_cfg.get("model"),
            temperature=ai_cfg.get("temperature"),
            max_tokens=ai_cfg.get("maxTokens"),
        )
    if not (settings and settings.get("api_key") and settings.get("base_url")):
        settings = await AssistantConfigService(db).get_provider_settings(tenant_id)
    if settings and settings.get("api_key") and settings.get("base_url"):
        return settings
    return None


async def _llm_json(db, tenant_id: int, system: str, user: str) -> dict[str, Any] | None:
    """One-shot LLM call returning parsed JSON, or None if unavailable/failed."""
    try:
        from app.domain.assistant.openai_client import OpenAIClient
        from app.domain.assistant.service import AssistantService

        settings = await _resolve_provider(db, tenant_id)
        if not settings:
            return None
        client = OpenAIClient(
            base_url=settings["base_url"],
            api_key=settings["api_key"],
            model=settings.get("model") or "gpt-4o-mini",
            temperature=0.3,
            max_tokens=4096,
        )
        text, _usage = await client.chat_with_usage(
            [{"role": "system", "content": system}, {"role": "user", "content": user}], stream=False
        )
        return AssistantService._extract_json_object(text)
    except Exception:  # noqa: BLE001
        return None


@router.post("/generate-page")
async def generate_page(
    payload: GenerateRequest,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:create"])),
) -> Any:
    prompt = payload.prompt.strip()
    doc = _sanitize(await _llm_json(db, current_user.tenant_id, BLOCK_SCHEMA_HINT, prompt))
    if doc:
        return SuccessResponse(data={"blocks": doc, "mode": "ai"})
    return SuccessResponse(data={"blocks": _template(prompt), "mode": "template"})


class TranslatePageRequest(BaseModel):
    page_id: int = Field(alias="pageId")
    target_lang: str = Field(alias="targetLang", min_length=2, max_length=12)

    model_config = {"populate_by_name": True}


@router.post("/translate-page")
async def translate_page(
    payload: TranslatePageRequest,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:page:create"])),
) -> Any:
    """Translate a page's block text into target_lang, preserving Puck structure."""
    import json as _json

    from app.domain.cms.service import CmsPageService

    src = await CmsPageService(db).get_for_tenant(payload.page_id, tenant_id=current_user.tenant_id)
    if not src:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Page not found")

    system = (
        "You translate website content JSON. Translate ONLY human-readable string values "
        f"(titles, subtitles, descriptions, button/label text, FAQ Q&A, markdown content) into the target language '{payload.target_lang}'. "
        "Do NOT change the JSON structure, keys, block 'type' values, 'id' fields, URLs/hrefs, icon names, numbers, or non-text props. "
        "Return ONLY the same JSON object, translated."
    )
    user = "Target language: " + payload.target_lang + "\nJSON:\n" + _json.dumps(src.blocks, ensure_ascii=False)
    translated = _sanitize(await _llm_json(db, current_user.tenant_id, system, user))
    if translated:
        return SuccessResponse(data={"blocks": translated, "title": src.title, "slug": src.slug, "mode": "ai"})
    # No provider: hand back the original so the editor can create a copy to edit manually.
    return SuccessResponse(data={"blocks": src.blocks, "title": src.title, "slug": src.slug, "mode": "copy"})


class TranslatePostRequest(BaseModel):
    post_id: int = Field(alias="postId")
    target_lang: str = Field(alias="targetLang", min_length=2, max_length=12)

    model_config = {"populate_by_name": True}


@router.post("/translate-post")
async def translate_post(
    payload: TranslatePostRequest,
    current_user: CurrentUser,
    db: DBSession,
    _: None = Depends(PermissionChecker(["cms:post:create"])),
) -> Any:
    import json as _json

    from app.domain.cms.service import CmsPostService

    src = await CmsPostService(db).get_for_tenant(payload.post_id, tenant_id=current_user.tenant_id)
    if not src:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Post not found")

    system = (
        f"Translate the blog post fields into '{payload.target_lang}'. Keep markdown formatting in 'body'. "
        "Return ONLY a JSON object with keys: title, excerpt, body (all translated)."
    )
    payload_in = {"title": src.title, "excerpt": src.excerpt or "", "body": src.body or ""}
    user = "Target language: " + payload.target_lang + "\n" + _json.dumps(payload_in, ensure_ascii=False)
    out = await _llm_json(db, current_user.tenant_id, system, user)
    if out and isinstance(out, dict) and out.get("title"):
        return SuccessResponse(
            data={
                "slug": src.slug,
                "title": out.get("title") or src.title,
                "excerpt": out.get("excerpt") or src.excerpt,
                "body": out.get("body") or src.body,
                "tags": src.tags,
                "mode": "ai",
            }
        )
    return SuccessResponse(
        data={"slug": src.slug, "title": src.title, "excerpt": src.excerpt, "body": src.body, "tags": src.tags, "mode": "copy"}
    )
