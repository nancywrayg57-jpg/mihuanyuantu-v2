"""image_processing OpenAPI subset. Key issuance stays outside this subset."""

from __future__ import annotations

from typing import Any

from app.domain.auth.api_key_service import IMAGE_PROCESSING_PREFIXES

PROCESSING_PATHS = tuple(dict.fromkeys(IMAGE_PROCESSING_PREFIXES))


def image_processing_contract(full_schema: dict[str, Any]) -> dict[str, Any]:
    """Keep only paths an image_processing key may call, and name the header."""
    paths = full_schema.get("paths") or {}
    selected = {
        path: spec
        for path, spec in paths.items()
        if any(str(path).startswith(prefix) for prefix in PROCESSING_PATHS)
    }
    return {
        "openapi": full_schema.get("openapi") or "3.1.0",
        "info": {
            "title": "蜜獾原图 image_processing",
            "version": "s5",
            "description": "X-API-Key scope image_processing. 生图、提示词、导入、客服和管理不在此子集。",
        },
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
            }
        },
        "security": [{"ApiKeyAuth": []}],
        "paths": selected,
        "x-error-codes": ["401", "403", "404", "422"],
    }
