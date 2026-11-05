"""Collect mounted HTTP paths across FastAPI include_router styles.

FastAPI ≤0.135 flattens `include_router` into `APIRoute` entries with full paths.
FastAPI ≥0.162 keeps an `_IncludedRouter` wrapper (`path` is absent); tests that
only read `route.path` then see `{''}` even though registration succeeded.
"""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute


def collect_router_paths(router: Any) -> set[str]:
    """Return absolute paths visible under ``router`` (recursive includes)."""

    paths: set[str] = set()

    def walk(node: Any, prefix: str = "") -> None:
        if hasattr(node, "original_router") and hasattr(node, "include_context"):
            ctx = node.include_context
            nested_prefix = f"{prefix.rstrip('/')}{getattr(ctx, 'prefix', '') or ''}"
            walk(node.original_router, nested_prefix)
            return

        routes = getattr(node, "routes", None)
        if not routes:
            return

        for route in routes:
            if isinstance(route, APIRoute):
                path = route.path or ""
                if prefix:
                    paths.add(f"{prefix.rstrip('/')}{path}")
                else:
                    paths.add(path)
                continue
            if hasattr(route, "original_router") and hasattr(route, "include_context"):
                ctx = route.include_context
                nested_prefix = f"{prefix.rstrip('/')}{getattr(ctx, 'prefix', '') or ''}"
                walk(route.original_router, nested_prefix)
                continue
            nested = getattr(route, "routes", None)
            if nested is not None:
                mount_path = getattr(route, "path", "") or ""
                walk(route, f"{prefix.rstrip('/')}{mount_path}")
                continue
            path = getattr(route, "path", None)
            if isinstance(path, str):
                if prefix:
                    paths.add(f"{prefix.rstrip('/')}{path}")
                else:
                    paths.add(path)

    walk(router)
    return paths
