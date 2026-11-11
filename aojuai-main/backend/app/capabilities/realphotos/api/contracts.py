"""FR-033：对外 image_processing OpenAPI 制品可达（鉴权下载仓内版本化 JSON）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, PermissionChecker
from app.capabilities.realphotos.permissions import GATEWAY_READ, WORKSPACE_READ
from app.core.response import SuccessResponse

router = APIRouter(prefix="/contracts")

# .../backend/app/capabilities/realphotos/api/contracts.py → parents[4] == backend/
_CONTRACT_PATH = (
    Path(__file__).resolve().parents[4] / "contracts" / "realphotos_image_processing.openapi.json"
)


def _load_contract() -> dict[str, Any]:
    raw = _CONTRACT_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("openapi contract is not an object")
    return data


@router.get("/image-processing.openapi.json")
async def download_image_processing_openapi(
    current_user: CurrentUser,
    _: None = Depends(PermissionChecker([WORKSPACE_READ, GATEWAY_READ])),
) -> JSONResponse:
    """商家登录后可下载/查看本平台 image_processing OpenAPI 制品。"""
    _ = current_user
    data = _load_contract()
    return JSONResponse(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="realphotos_image_processing.openapi.json"',
            "X-OpenAPI-Version": str((data.get("info") or {}).get("version") or ""),
            "X-OpenAPI-Scope": "image_processing",
            "X-OpenAPI-Auth": "X-API-Key",
        },
    )


@router.get("/image-processing")
async def image_processing_contract_meta(
    current_user: CurrentUser,
    _: None = Depends(PermissionChecker([WORKSPACE_READ, GATEWAY_READ])),
) -> dict[str, Any]:
    _ = current_user
    data = _load_contract()
    info = data.get("info") or {}
    return SuccessResponse(
        data={
            "title": info.get("title"),
            "version": info.get("version"),
            "description": info.get("description"),
            "authHeader": "X-API-Key",
            "scope": "image_processing",
            "downloadPath": "/api/v1/realphotos/contracts/image-processing.openapi.json",
            "artifactRelativePath": "aojuai-main/backend/contracts/realphotos_image_processing.openapi.json",
        }
    )
