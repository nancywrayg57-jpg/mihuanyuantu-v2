"""AOJU Backend - Assistant Module Adapter Base"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.assistant.prompt_context import (
    build_generic_prompt_context,
    build_prompt_preferred_tool_ids,
)
from app.domain.assistant.schemas import PresetPrompt


class ActionResult:
    """Normalized assistant action execution result."""

    def __init__(
        self,
        success: bool,
        data: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> None:
        self.success = success
        self.data = data
        self.message = message


class ModuleAdapterBase(ABC):
    """Base contract for assistant-aware modules."""

    module_code: str = ""
    module_name: str = ""
    supported_routes: list[str] = []
    default_chat_prompt: str | None = None
    prefer_inferred_action_on_conflict: bool = False
    allow_user_message_inference: bool = True
    allow_reply_text_inference: bool = True

    def build_prompt_context(
        self,
        *,
        module_code: str,
        module_name: str,
        route: str,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_context = context_data if isinstance(context_data, dict) else {}
        return build_generic_prompt_context(
            module_code=module_code,
            module_name=module_name,
            route_path=route,
            context_data=normalized_context,
            tool_catalog_max_tools=12,
            tool_catalog_include_internal_contract=False,
            tool_catalog_include_params=False,
            tool_catalog_field_detail_level="compact",
            tool_catalog_preferred_ids=build_prompt_preferred_tool_ids(
                current_role_profile=(
                    normalized_context.get("currentRoleProfile")
                    if isinstance(normalized_context.get("currentRoleProfile"), dict)
                    else None
                ),
                capability_manifest=(
                    normalized_context.get("capabilityManifest")
                    if isinstance(normalized_context.get("capabilityManifest"), dict)
                    else None
                ),
                prior_action=None,
            ),
        )

    def matches_route(self, route: str) -> bool:
        for pattern in self.supported_routes:
            if pattern.endswith("*"):
                if route.startswith(pattern[:-1]):
                    return True
                continue
            if route == pattern:
                return True
        return False

    @abstractmethod
    async def get_context(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """Return module context for the current route."""

    @abstractmethod
    async def get_presets(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> list[PresetPrompt]:
        """Return module prompt presets."""

    async def get_capability_source(
        self,
        route: str,
        params: dict[str, Any],
        *,
        context_data: dict[str, Any] | None,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any] | None:
        """Return module-local skill/tool/capability metadata."""
        return None

    def get_governance_skill_catalog(self) -> list[dict[str, Any]]:
        """Return module-local assistant skill catalog for governance."""
        return []

    def get_routing_manifest(self) -> dict[str, Any]:
        """Return lightweight metadata used by text-entry assistant routing."""
        route_prefixes = [
            pattern[:-1] if pattern.endswith("*") else pattern
            for pattern in self.supported_routes
            if str(pattern or "").strip() and pattern != "/*"
        ]
        return {
            "moduleCode": self.module_code,
            "moduleName": self.module_name,
            "routePrefixes": route_prefixes,
            "keywords": [],
            "summary": "",
        }

    def get_execution_manifest(self) -> dict[str, Any]:
        """Return module intents/tools used by the global execution planner."""
        manifest = dict(self.get_routing_manifest() or {})
        try:
            from app.domain.assistant.capability_registry import get_assistant_capability_provider
            from app.domain.assistant.execution_manifest import build_execution_manifest_from_capability_provider

            provider = get_assistant_capability_provider(self.module_code)
            if provider is not None:
                provider_manifest = build_execution_manifest_from_capability_provider(
                    provider=provider,
                    module_name=self.module_name,
                    fallback_route_prefixes=list(manifest.get("routePrefixes") or []),
                )
                if provider_manifest.get("intents"):
                    return {
                        **manifest,
                        **provider_manifest,
                        "keywords": [
                            *list(manifest.get("keywords") or []),
                            *list(provider_manifest.get("keywords") or []),
                        ],
                    }
        except Exception:
            pass
        manifest.setdefault("intents", [])
        return manifest

    @abstractmethod
    async def execute_action(
        self,
        action: str,
        params: dict[str, Any],
        *,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> ActionResult:
        """Execute module action."""

    async def infer_action_from_reply(
        self,
        reply: str,
        route: str,
        params: dict[str, Any],
        *,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Infer action from reply text when a module needs it."""
        return None

    async def canonicalize_action(
        self,
        action: dict[str, Any],
        route: str,
        params: dict[str, Any],
        *,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Normalize module action into a canonical contract."""
        return action if isinstance(action, dict) else None
