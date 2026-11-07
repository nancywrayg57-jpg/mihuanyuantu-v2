"""Export offline image_processing OpenAPI subset (ALIGN-GAP G3 / AD-009).

Usage (from aojuai-main/backend):
  python -m scripts.export_image_processing_openapi
  python -m scripts.export_image_processing_openapi --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "contracts" / "realphotos_image_processing.openapi.json"


def _build_contract() -> dict:
    import app.capabilities.realphotos.models  # noqa: F401
    import app.domain  # noqa: F401
    from app.capabilities.realphotos.openapi_contract import image_processing_contract
    from app.domain.auth.api_key_service import IMAGE_PROCESSING_PREFIXES
    from app.main import app as fastapi_app

    contract = image_processing_contract(fastapi_app.openapi())
    contract["x-image-processing-prefixes"] = list(IMAGE_PROCESSING_PREFIXES)
    return contract


def export(path: Path) -> dict:
    contract = _build_contract()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return contract


def check(path: Path) -> int:
    if not path.is_file():
        print(f"MISSING {path}")
        return 2
    fresh = _build_contract()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    if json.dumps(fresh, sort_keys=True) != json.dumps(on_disk, sort_keys=True):
        print("DIFF dirty: re-run export_image_processing_openapi")
        return 1
    prefixes = set(fresh.get("x-image-processing-prefixes") or [])
    for route in (fresh.get("paths") or {}):
        if not any(str(route).startswith(p) for p in prefixes):
            print(f"PATH outside whitelist: {route}")
            return 1
    schemes = ((fresh.get("components") or {}).get("securitySchemes") or {})
    auth = schemes.get("ApiKeyAuth") or {}
    if auth.get("name") != "X-API-Key":
        print("ApiKeyAuth header missing")
        return 1
    print(f"openapi_export=ok openapi_diff=clean paths={len(fresh.get('paths') or {})}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        return check(args.out)
    export(args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
