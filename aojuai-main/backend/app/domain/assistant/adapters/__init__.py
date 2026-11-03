"""AOJU Backend - Assistant Adapter Bootstrap"""

from __future__ import annotations

from app.domain.assistant.adapters.base import ActionResult, ModuleAdapterBase
from app.domain.assistant.adapters.registry import AdapterRegistry

_CORE_ADAPTERS_REGISTERED = False


def register_module_adapter(adapter: ModuleAdapterBase, *, priority: int = 100) -> None:
    """Register a module adapter into the assistant foundation."""
    AdapterRegistry.register(adapter, priority=priority)


def ensure_core_adapters_registered() -> None:
    global _CORE_ADAPTERS_REGISTERED
    if _CORE_ADAPTERS_REGISTERED:
        return

    from app.domain.assistant.adapters.default import DefaultAdapter
    from app.domain.assistant.adapters.foundation import CreditsAssistantAdapter, UsersAssistantAdapter

    register_module_adapter(CreditsAssistantAdapter(), priority=100)
    register_module_adapter(UsersAssistantAdapter(), priority=100)
    register_module_adapter(DefaultAdapter(), priority=1000)
    _CORE_ADAPTERS_REGISTERED = True


def __getattr__(name: str):
    if name == "DefaultAdapter":
        from app.domain.assistant.adapters.default import DefaultAdapter

        return DefaultAdapter
    if name == "CreditsAssistantAdapter":
        from app.domain.assistant.adapters.foundation import CreditsAssistantAdapter

        return CreditsAssistantAdapter
    if name == "UsersAssistantAdapter":
        from app.domain.assistant.adapters.foundation import UsersAssistantAdapter

        return UsersAssistantAdapter
    raise AttributeError(name)


AdapterRegistry.set_bootstrap_loader(ensure_core_adapters_registered)

__all__ = [
    "ModuleAdapterBase",
    "ActionResult",
    "AdapterRegistry",
    "register_module_adapter",
    "ensure_core_adapters_registered",
    "DefaultAdapter",
    "CreditsAssistantAdapter",
    "UsersAssistantAdapter",
]
