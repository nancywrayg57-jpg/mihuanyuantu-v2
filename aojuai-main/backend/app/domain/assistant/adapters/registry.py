"""AOJU Backend - Assistant Adapter Registry"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.assistant.adapters.base import ModuleAdapterBase


@dataclass
class _RegistryEntry:
    adapter: ModuleAdapterBase
    priority: int
    order: int


class AdapterRegistry:
    """Global assistant adapter registry."""

    _entries: dict[str, _RegistryEntry] = {}
    _order: int = 0
    _bootstrap_loader: Callable[[], None] | None = None
    _bootstrap_loaded: bool = False

    @classmethod
    def set_bootstrap_loader(cls, loader: Callable[[], None] | None) -> None:
        cls._bootstrap_loader = loader

    @classmethod
    def _ensure_bootstrap_loaded(cls) -> None:
        if cls._bootstrap_loaded:
            return
        if cls._bootstrap_loader is None:
            cls._bootstrap_loaded = True
            return
        cls._bootstrap_loader()
        cls._bootstrap_loaded = True

    @classmethod
    def register(cls, adapter: ModuleAdapterBase, priority: int = 100) -> None:
        cls._order += 1
        cls._entries[adapter.module_code] = _RegistryEntry(
            adapter=adapter,
            priority=priority,
            order=cls._order,
        )

    @classmethod
    def get(cls, module_code: str) -> ModuleAdapterBase | None:
        cls._ensure_bootstrap_loaded()
        entry = cls._entries.get(module_code)
        return entry.adapter if entry else None

    @classmethod
    def _score_route_match(cls, adapter: ModuleAdapterBase, route: str) -> int:
        score = -1
        for pattern in adapter.supported_routes:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if route.startswith(prefix):
                    score = max(score, len(prefix))
                continue
            if route == pattern:
                score = max(score, len(pattern) + 10000)
        return score

    @classmethod
    def resolve_by_route(cls, route: str) -> ModuleAdapterBase | None:
        cls._ensure_bootstrap_loaded()
        matched: list[tuple[int, int, int, _RegistryEntry]] = []
        for entry in cls._entries.values():
            if not entry.adapter.matches_route(route):
                continue
            matched.append(
                (
                    entry.priority,
                    -cls._score_route_match(entry.adapter, route),
                    entry.order,
                    entry,
                )
            )
        if not matched:
            return None
        matched.sort()
        return matched[0][3].adapter

    @classmethod
    def list_all(cls) -> list[ModuleAdapterBase]:
        cls._ensure_bootstrap_loaded()
        entries = sorted(cls._entries.values(), key=lambda item: (item.priority, item.order))
        return [item.adapter for item in entries]
