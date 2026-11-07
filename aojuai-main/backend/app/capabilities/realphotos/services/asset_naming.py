"""FR-028 list/download filename composition. Does not fetch URLs."""

from __future__ import annotations

import re
import secrets
from typing import Any

_ORDER = ("name", "seller", "sku", "asn", "price", "website", "url")
_SAFE = re.compile(r"[^\w.\-]+", re.UNICODE)


def meta_from_asset(asset: Any) -> dict[str, str]:
    return {
        "name": str(getattr(asset, "meta_name", None) or getattr(asset, "name", None) or "").strip(),
        "seller": str(getattr(asset, "meta_seller", None) or getattr(asset, "seller", None) or "").strip(),
        "sku": str(getattr(asset, "meta_sku", None) or getattr(asset, "sku", None) or "").strip(),
        "asn": str(getattr(asset, "meta_asn", None) or getattr(asset, "asn", None) or "").strip(),
        "price": str(getattr(asset, "meta_price", None) or getattr(asset, "price", None) or "").strip(),
        "website": str(getattr(asset, "meta_website", None) or getattr(asset, "website", None) or "").strip(),
        "url": str(getattr(asset, "meta_url", None) or getattr(asset, "url", None) or "").strip(),
    }


def compose_list_filename(*, meta: dict[str, str], asset_id: int, origin_kind: str) -> dict[str, str]:
    parts = [str(meta.get(key) or "").strip() for key in _ORDER if str(meta.get(key) or "").strip()]
    if parts:
        return {
            "displayName": "_".join(parts),
            "displayNameSource": "metadata",
            "degraded": "false",
        }
    return {
        "displayName": f"{origin_kind or 'asset'}_{int(asset_id)}",
        "displayNameSource": "id_origin",
        "degraded": "true",
    }


def compose_download_basename(*, meta: dict[str, str], asset_id: int, origin_kind: str) -> str:
    sku = str(meta.get("sku") or "").strip()
    asn = str(meta.get("asn") or "").strip()
    if sku and asn:
        base = f"{sku}_{asn}"
    elif sku:
        base = sku
    else:
        composed = compose_list_filename(meta=meta, asset_id=asset_id, origin_kind=origin_kind)
        base = composed["displayName"]
    cleaned = _SAFE.sub("_", base).strip("._") or f"{origin_kind or 'asset'}_{int(asset_id)}"
    return cleaned[:180]


def ensure_sku(*, meta: dict[str, str]) -> str:
    sku = str(meta.get("sku") or "").strip()
    if sku:
        return sku
    return secrets.token_hex(8)
