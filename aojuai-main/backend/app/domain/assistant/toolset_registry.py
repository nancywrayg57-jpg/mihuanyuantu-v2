from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from app.domain.assistant.tool_schema import (
    AssistantToolExecutionBinding,
    AssistantToolSchema,
    build_tool_definitions,
    build_tool_execution_binding_map,
)


@dataclass
class AssistantModuleToolsetSpec:
    """Published assistant tools owned by one module."""

    module_code: str
    tool_schemas: tuple[AssistantToolSchema, ...] = field(default_factory=tuple)
    execution_bindings: tuple[AssistantToolExecutionBinding, ...] = field(default_factory=tuple)


_ASSISTANT_MODULE_TOOLSETS: dict[str, AssistantModuleToolsetSpec] = {}


def register_assistant_module_toolset(
    toolset: AssistantModuleToolsetSpec,
) -> AssistantModuleToolsetSpec:
    module_code = str(getattr(toolset, "module_code", "") or "").strip()
    if not module_code:
        raise ValueError("assistant module toolset requires non-empty module_code")
    _ASSISTANT_MODULE_TOOLSETS[module_code] = toolset
    return toolset


def get_assistant_module_toolset(module_code: str) -> AssistantModuleToolsetSpec | None:
    return _ASSISTANT_MODULE_TOOLSETS.get(str(module_code or "").strip())


def list_assistant_module_toolsets() -> list[AssistantModuleToolsetSpec]:
    return [toolset for _, toolset in sorted(_ASSISTANT_MODULE_TOOLSETS.items(), key=lambda item: item[0])]


def build_registered_tool_definitions(
    toolset: AssistantModuleToolsetSpec,
) -> list[dict[str, object]]:
    return build_tool_definitions(list(toolset.tool_schemas))


def build_registered_execution_bindings(
    toolset: AssistantModuleToolsetSpec,
) -> tuple[AssistantToolExecutionBinding, ...]:
    return tuple(toolset.execution_bindings)


def build_registered_execution_binding_map(
    toolset: AssistantModuleToolsetSpec,
) -> dict[str, AssistantToolExecutionBinding]:
    return build_tool_execution_binding_map(toolset.execution_bindings)


def clone_registered_toolset(
    module_code: str,
) -> AssistantModuleToolsetSpec | None:
    toolset = get_assistant_module_toolset(module_code)
    if toolset is None:
        return None
    return AssistantModuleToolsetSpec(
        module_code=toolset.module_code,
        tool_schemas=tuple(deepcopy(item) for item in toolset.tool_schemas),
        execution_bindings=tuple(toolset.execution_bindings),
    )
