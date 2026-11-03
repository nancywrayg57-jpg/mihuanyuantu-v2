from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from typing import Any, get_args, get_origin


def _normalize_string(value: Any) -> str:
    return str(value or "").strip()


def _normalize_string_tuple(
    values: list[Any] | tuple[Any, ...] | set[Any] | None,
    *,
    limit: int | None = None,
) -> tuple[str, ...]:
    items: list[str] = []
    for raw in values or ():
        normalized = _normalize_string(raw)
        if not normalized:
            continue
        items.append(normalized)
        if limit is not None and len(items) >= limit:
            break
    return tuple(items)


def _camelize_field_name(value: str) -> str:
    head, *tail = str(value or "").split("_")
    return head + "".join(part.capitalize() for part in tail if part)


def _normalize_pydantic_value_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is not None:
        non_none_args = [item for item in get_args(annotation) if item is not type(None)]
        if origin in {list, tuple, set, frozenset}:
            item_type = _normalize_pydantic_value_type(non_none_args[0] if non_none_args else str)
            return f"{item_type}[]"
        if origin in {dict}:
            return "json"
        if len(non_none_args) == 1:
            return _normalize_pydantic_value_type(non_none_args[0])
    if annotation in {int, float}:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is datetime:
        return "datetime"
    if annotation is date:
        return "date"
    return "string"


def _extract_pydantic_examples(field_info: Any) -> tuple[str, ...]:
    raw_examples = getattr(field_info, "examples", None)
    if isinstance(raw_examples, (list, tuple, set)):
        return _normalize_string_tuple(list(raw_examples), limit=8)
    json_schema_extra = getattr(field_info, "json_schema_extra", None)
    if isinstance(json_schema_extra, dict):
        nested_examples = json_schema_extra.get("examples")
        if isinstance(nested_examples, (list, tuple, set)):
            return _normalize_string_tuple(list(nested_examples), limit=8)
    return ()


@dataclass(frozen=True, slots=True)
class AssistantToolOptionSchema:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class AssistantToolRequiredWhenSchema:
    key: str
    equals: Any | None = None
    in_values: tuple[Any, ...] = dc_field(default_factory=tuple)
    description: str | None = None


@dataclass(frozen=True, slots=True)
class AssistantToolScopeBindingSchema:
    scope_id: str
    binding_kind: str = "endpoint"
    method: str | None = None
    path: str | None = None
    handler: str | None = None
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class AssistantToolInternalContractSchema:
    param_source: str | None = None
    request_model: str | None = None
    request_model_module: str | None = None
    bindings: tuple[AssistantToolScopeBindingSchema, ...] = dc_field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AssistantToolFieldSchema:
    key: str
    label: str
    value_type: str
    required: bool
    description: str
    examples: tuple[str, ...] = dc_field(default_factory=tuple)
    enum_values: tuple[str, ...] = dc_field(default_factory=tuple)
    enum_options: tuple[AssistantToolOptionSchema, ...] = dc_field(default_factory=tuple)
    importance: str | None = None
    downstream_effects: tuple[str, ...] = dc_field(default_factory=tuple)
    follow_up_hint: str | None = None
    required_when: AssistantToolRequiredWhenSchema | None = None


@dataclass(frozen=True, slots=True)
class AssistantToolSchema:
    tool_id: str
    label: str
    summary: str
    status: str = "active"
    scope_ids: tuple[str, ...] = dc_field(default_factory=tuple)
    required_permissions: tuple[str, ...] = dc_field(default_factory=tuple)
    confirmation_required: bool = False
    params: tuple[AssistantToolFieldSchema, ...] = dc_field(default_factory=tuple)
    examples: tuple[str, ...] = dc_field(default_factory=tuple)
    tool_type: str | None = None
    resource: str | None = None
    access_mode: str | None = None
    internal_contract: AssistantToolInternalContractSchema | None = None


@dataclass(frozen=True, slots=True)
class AssistantToolExecutionBinding:
    tool_id: str
    executor: Callable[..., Any]
    runtime_options: dict[str, Any] = dc_field(default_factory=dict)


def assistant_tool_option(value: str, label: str) -> AssistantToolOptionSchema:
    return AssistantToolOptionSchema(
        value=_normalize_string(value),
        label=_normalize_string(label),
    )


def assistant_tool_required_when(
    key: str,
    *,
    equals: Any | None = None,
    in_values: list[Any] | tuple[Any, ...] | None = None,
    description: str | None = None,
) -> AssistantToolRequiredWhenSchema:
    return AssistantToolRequiredWhenSchema(
        key=_normalize_string(key),
        equals=equals,
        in_values=tuple(in_values or ()),
        description=_normalize_string(description) or None,
    )


def assistant_tool_scope_binding(
    scope_id: str,
    *,
    kind: str = "endpoint",
    method: str | None = None,
    path: str | None = None,
    handler: str | None = None,
    summary: str | None = None,
) -> AssistantToolScopeBindingSchema:
    return AssistantToolScopeBindingSchema(
        scope_id=_normalize_string(scope_id),
        binding_kind=_normalize_string(kind) or "endpoint",
        method=_normalize_string(method).upper() or None,
        path=_normalize_string(path) or None,
        handler=_normalize_string(handler) or None,
        summary=_normalize_string(summary) or None,
    )


def assistant_tool_internal_contract(
    *,
    param_source: str | None = None,
    request_model: str | None = None,
    request_model_module: str | None = None,
    model_cls: Any | None = None,
    bindings: list[dict[str, Any] | AssistantToolScopeBindingSchema] | tuple[dict[str, Any] | AssistantToolScopeBindingSchema, ...] | None = None,
) -> AssistantToolInternalContractSchema | None:
    normalized_param_source = _normalize_string(param_source) or None
    normalized_request_model = _normalize_string(request_model) or None
    normalized_request_model_module = _normalize_string(request_model_module) or None

    if model_cls is not None:
        normalized_param_source = normalized_param_source or "pydantic_model"
        normalized_request_model = normalized_request_model or _normalize_string(getattr(model_cls, "__name__", None)) or None
        normalized_request_model_module = (
            normalized_request_model_module
            or _normalize_string(getattr(model_cls, "__module__", None))
            or None
        )

    normalized_bindings: list[AssistantToolScopeBindingSchema] = []
    for item in bindings or ():
        if isinstance(item, AssistantToolScopeBindingSchema):
            if item.scope_id:
                normalized_bindings.append(item)
            continue
        if not isinstance(item, dict):
            continue
        binding = assistant_tool_scope_binding(
            str(item.get("scopeId") or item.get("scope_id") or ""),
            kind=str(item.get("kind") or item.get("bindingKind") or item.get("binding_kind") or "endpoint"),
            method=str(item.get("method") or ""),
            path=str(item.get("path") or ""),
            handler=str(item.get("handler") or ""),
            summary=str(item.get("summary") or ""),
        )
        if binding.scope_id:
            normalized_bindings.append(binding)

    if (
        normalized_param_source is None
        and normalized_request_model is None
        and normalized_request_model_module is None
        and not normalized_bindings
    ):
        return None

    return AssistantToolInternalContractSchema(
        param_source=normalized_param_source,
        request_model=normalized_request_model,
        request_model_module=normalized_request_model_module,
        bindings=tuple(normalized_bindings),
    )


def assistant_tool_field(
    key: str,
    label: str,
    value_type: str,
    *,
    required: bool = False,
    description: str,
    examples: list[str] | None = None,
    enum_values: list[str] | None = None,
    enum_options: list[dict[str, str] | AssistantToolOptionSchema] | None = None,
    importance: str | None = None,
    downstream_effects: list[str] | None = None,
    follow_up_hint: str | None = None,
    required_when: dict[str, Any] | AssistantToolRequiredWhenSchema | None = None,
) -> AssistantToolFieldSchema:
    normalized_options: list[AssistantToolOptionSchema] = []
    for item in enum_options or []:
        if isinstance(item, AssistantToolOptionSchema):
            if item.value and item.label:
                normalized_options.append(item)
            continue
        if not isinstance(item, dict):
            continue
        option = assistant_tool_option(
            str(item.get("value") or ""),
            str(item.get("label") or ""),
        )
        if option.value and option.label:
            normalized_options.append(option)

    normalized_required_when: AssistantToolRequiredWhenSchema | None = None
    if isinstance(required_when, AssistantToolRequiredWhenSchema):
        normalized_required_when = required_when
    elif isinstance(required_when, dict):
        dependency_key = _normalize_string(required_when.get("key"))
        if dependency_key:
            normalized_required_when = assistant_tool_required_when(
                dependency_key,
                equals=required_when.get("equals"),
                in_values=list(required_when.get("in") or [])
                if isinstance(required_when.get("in"), list)
                else None,
                description=str(required_when.get("description") or ""),
            )

    normalized_importance = _normalize_string(importance).lower() or None
    return AssistantToolFieldSchema(
        key=_normalize_string(key),
        label=_normalize_string(label),
        value_type=_normalize_string(value_type),
        required=bool(required),
        description=_normalize_string(description),
        examples=_normalize_string_tuple(examples),
        enum_values=_normalize_string_tuple(enum_values),
        enum_options=tuple(normalized_options),
        importance=normalized_importance,
        downstream_effects=_normalize_string_tuple(downstream_effects, limit=8),
        follow_up_hint=_normalize_string(follow_up_hint) or None,
        required_when=normalized_required_when,
    )


def assistant_tool(
    tool_id: str,
    label: str,
    summary: str,
    *,
    status: str = "active",
    scope_ids: list[str] | tuple[str, ...],
    required_permissions: list[str] | None = None,
    confirmation_required: bool = False,
    params: list[dict[str, Any] | AssistantToolFieldSchema] | tuple[dict[str, Any] | AssistantToolFieldSchema, ...] | None = None,
    examples: list[str] | None = None,
    tool_type: str | None = None,
    resource: str | None = None,
    access_mode: str | None = None,
    internal_contract: dict[str, Any] | AssistantToolInternalContractSchema | None = None,
) -> AssistantToolSchema:
    normalized_params: list[AssistantToolFieldSchema] = []
    for item in params or ():
        if isinstance(item, AssistantToolFieldSchema):
            normalized_params.append(item)
            continue
        if not isinstance(item, dict):
            continue
        normalized_params.append(
            assistant_tool_field(
                str(item.get("key") or ""),
                str(item.get("label") or ""),
                str(item.get("type") or item.get("valueType") or ""),
                required=bool(item.get("required")),
                description=str(item.get("description") or ""),
                examples=list(item.get("examples") or []),
                enum_values=list(item.get("enumValues") or []),
                enum_options=list(item.get("enumOptions") or []),
                importance=str(item.get("importance") or "") or None,
                downstream_effects=list(item.get("downstreamEffects") or []),
                follow_up_hint=str(item.get("followUpHint") or "") or None,
                required_when=item.get("requiredWhen"),
            )
        )

    normalized_internal_contract: AssistantToolInternalContractSchema | None = None
    if isinstance(internal_contract, AssistantToolInternalContractSchema):
        normalized_internal_contract = internal_contract
    elif isinstance(internal_contract, dict):
        normalized_internal_contract = assistant_tool_internal_contract(
            param_source=str(internal_contract.get("paramSource") or internal_contract.get("param_source") or ""),
            request_model=str(internal_contract.get("requestModel") or internal_contract.get("request_model") or ""),
            request_model_module=str(
                internal_contract.get("requestModelModule") or internal_contract.get("request_model_module") or ""
            ),
            bindings=list(internal_contract.get("bindings") or []),
        )

    return AssistantToolSchema(
        tool_id=_normalize_string(tool_id),
        label=_normalize_string(label),
        summary=_normalize_string(summary),
        status=_normalize_string(status) or "active",
        scope_ids=_normalize_string_tuple(list(scope_ids or ())),
        required_permissions=_normalize_string_tuple(required_permissions),
        confirmation_required=bool(confirmation_required),
        params=tuple(normalized_params),
        examples=_normalize_string_tuple(examples),
        tool_type=_normalize_string(tool_type) or None,
        resource=_normalize_string(resource) or None,
        access_mode=_normalize_string(access_mode) or None,
        internal_contract=normalized_internal_contract,
    )


def assistant_tool_from_model(
    tool_id: str,
    label: str,
    summary: str,
    *,
    model_cls: Any,
    scope_ids: list[str] | tuple[str, ...],
    required_permissions: list[str] | None = None,
    status: str = "active",
    confirmation_required: bool = False,
    params_before: list[dict[str, Any] | AssistantToolFieldSchema] | tuple[dict[str, Any] | AssistantToolFieldSchema, ...] | None = None,
    params_after: list[dict[str, Any] | AssistantToolFieldSchema] | tuple[dict[str, Any] | AssistantToolFieldSchema, ...] | None = None,
    include_keys: list[str] | tuple[str, ...] | None = None,
    exclude_keys: list[str] | tuple[str, ...] | None = None,
    field_overrides: dict[str, dict[str, Any]] | None = None,
    examples: list[str] | None = None,
    tool_type: str | None = None,
    resource: str | None = None,
    access_mode: str | None = None,
    bindings: list[dict[str, Any] | AssistantToolScopeBindingSchema] | tuple[dict[str, Any] | AssistantToolScopeBindingSchema, ...] | None = None,
) -> AssistantToolSchema:
    model_params = assistant_tool_fields_from_pydantic_model(
        model_cls,
        include_keys=include_keys,
        exclude_keys=exclude_keys,
        overrides=field_overrides,
    )
    return assistant_tool(
        tool_id,
        label,
        summary,
        status=status,
        scope_ids=scope_ids,
        required_permissions=required_permissions,
        confirmation_required=confirmation_required,
        params=[
            *(list(params_before or [])),
            *list(model_params),
            *(list(params_after or [])),
        ],
        examples=examples,
        tool_type=tool_type,
        resource=resource,
        access_mode=access_mode,
        internal_contract=assistant_tool_internal_contract(
            model_cls=model_cls,
            bindings=bindings,
        ),
    )


def assistant_tool_execution_binding(
    tool: AssistantToolSchema | str,
    executor: Callable[..., Any],
    **runtime_options: Any,
) -> AssistantToolExecutionBinding:
    tool_id = tool.tool_id if isinstance(tool, AssistantToolSchema) else _normalize_string(tool)
    normalized_options = {
        _normalize_string(key): value
        for key, value in runtime_options.items()
        if _normalize_string(key)
    }
    return AssistantToolExecutionBinding(
        tool_id=tool_id,
        executor=executor,
        runtime_options=normalized_options,
    )


def assistant_tool_fields_from_pydantic_model(
    model_cls: Any,
    *,
    include_keys: list[str] | tuple[str, ...] | None = None,
    exclude_keys: list[str] | tuple[str, ...] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> tuple[AssistantToolFieldSchema, ...]:
    include = {
        _normalize_string(item)
        for item in (include_keys or ())
        if _normalize_string(item)
    }
    exclude = {
        _normalize_string(item)
        for item in (exclude_keys or ())
        if _normalize_string(item)
    }
    field_overrides = dict(overrides or {})
    fields: list[AssistantToolFieldSchema] = []
    for field_name, field_info in getattr(model_cls, "model_fields", {}).items():
        key = _normalize_string(getattr(field_info, "alias", None) or _camelize_field_name(field_name) or field_name)
        if include and field_name not in include and key not in include:
            continue
        if field_name in exclude or key in exclude:
            continue
        meta = dict(field_overrides.get(key) or field_overrides.get(field_name) or {})
        description = _normalize_string(meta.pop("description", None) or getattr(field_info, "description", None))
        fields.append(
            assistant_tool_field(
                key=key,
                label=_normalize_string(meta.pop("label", None) or key) or key,
                value_type=_normalize_string(meta.pop("type", None) or _normalize_pydantic_value_type(getattr(field_info, "annotation", None))) or "string",
                required=bool(
                    meta.pop("required", None)
                    if "required" in meta
                    else getattr(field_info, "is_required", lambda: False)()
                ),
                description=description or f"{key}。",
                examples=list(meta.pop("examples", None) or _extract_pydantic_examples(field_info)),
                enum_values=list(meta.pop("enum_values", meta.pop("enumValues", [])) or []),
                enum_options=list(meta.pop("enum_options", meta.pop("enumOptions", [])) or []),
                importance=_normalize_string(meta.pop("importance", None)) or None,
                downstream_effects=list(meta.pop("downstream_effects", meta.pop("downstreamEffects", [])) or []),
                follow_up_hint=_normalize_string(meta.pop("follow_up_hint", meta.pop("followUpHint", None))) or None,
                required_when=meta.pop("required_when", meta.pop("requiredWhen", None)),
            )
        )
    return tuple(fields)


def build_tool_required_when_definition(
    required_when: AssistantToolRequiredWhenSchema | None,
) -> dict[str, Any] | None:
    if required_when is None or not required_when.key:
        return None
    payload: dict[str, Any] = {
        "key": required_when.key,
    }
    if required_when.equals is not None:
        payload["equals"] = required_when.equals
    if required_when.in_values:
        payload["in"] = list(required_when.in_values[:8])
    if required_when.description:
        payload["description"] = required_when.description
    return payload


def build_tool_scope_binding_definition(
    binding_schema: AssistantToolScopeBindingSchema,
) -> dict[str, Any]:
    payload = {
        "scopeId": binding_schema.scope_id,
        "kind": binding_schema.binding_kind,
    }
    if binding_schema.method:
        payload["method"] = binding_schema.method
    if binding_schema.path:
        payload["path"] = binding_schema.path
    if binding_schema.handler:
        payload["handler"] = binding_schema.handler
    if binding_schema.summary:
        payload["summary"] = binding_schema.summary
    return payload


def build_tool_internal_contract_definition(
    internal_contract: AssistantToolInternalContractSchema | None,
) -> dict[str, Any] | None:
    if internal_contract is None:
        return None
    payload: dict[str, Any] = {}
    if internal_contract.param_source:
        payload["paramSource"] = internal_contract.param_source
    if internal_contract.request_model:
        payload["requestModel"] = internal_contract.request_model
    if internal_contract.request_model_module:
        payload["requestModelModule"] = internal_contract.request_model_module
    if internal_contract.bindings:
        payload["bindings"] = [
            build_tool_scope_binding_definition(item)
            for item in internal_contract.bindings
            if item.scope_id
        ]
    return payload or None


def build_tool_field_definition(field_schema: AssistantToolFieldSchema) -> dict[str, Any]:
    payload = {
        "key": field_schema.key,
        "label": field_schema.label,
        "type": field_schema.value_type,
        "required": bool(field_schema.required),
        "description": field_schema.description,
        "examples": list(field_schema.examples),
        "enumValues": list(field_schema.enum_values),
        "enumOptions": [
            {
                "value": item.value,
                "label": item.label,
            }
            for item in field_schema.enum_options
            if item.value and item.label
        ],
    }
    if field_schema.importance:
        payload["importance"] = field_schema.importance
    if field_schema.downstream_effects:
        payload["downstreamEffects"] = list(field_schema.downstream_effects)
    if field_schema.follow_up_hint:
        payload["followUpHint"] = field_schema.follow_up_hint
    required_when = build_tool_required_when_definition(field_schema.required_when)
    if required_when:
        payload["requiredWhen"] = required_when
    return payload


def build_tool_definition(tool_schema: AssistantToolSchema) -> dict[str, Any]:
    normalized_tool_type = tool_schema.tool_type or ("mutation" if tool_schema.confirmation_required else "query")
    normalized_access_mode = tool_schema.access_mode or ("write" if tool_schema.confirmation_required else "read")
    payload = {
        "id": tool_schema.tool_id,
        "label": tool_schema.label,
        "summary": tool_schema.summary,
        "status": tool_schema.status,
        "toolType": normalized_tool_type,
        "resource": tool_schema.resource or "misc",
        "accessMode": normalized_access_mode,
        "scopeIds": list(tool_schema.scope_ids),
        "requiredPermissions": list(tool_schema.required_permissions),
        "confirmationRequired": bool(tool_schema.confirmation_required),
        "params": [build_tool_field_definition(item) for item in tool_schema.params],
        "examples": list(tool_schema.examples),
    }
    internal_contract = build_tool_internal_contract_definition(tool_schema.internal_contract)
    if internal_contract:
        payload["internalContract"] = internal_contract
    return payload


def build_tool_definitions(tool_schemas: list[AssistantToolSchema] | tuple[AssistantToolSchema, ...]) -> list[dict[str, Any]]:
    return [build_tool_definition(item) for item in tool_schemas]


def build_tool_execution_binding_map(
    bindings: list[AssistantToolExecutionBinding] | tuple[AssistantToolExecutionBinding, ...],
) -> dict[str, AssistantToolExecutionBinding]:
    items: dict[str, AssistantToolExecutionBinding] = {}
    for binding in bindings:
        tool_id = _normalize_string(getattr(binding, "tool_id", ""))
        if not tool_id:
            continue
        items[tool_id] = binding
    return items


def list_bound_tool_ids(
    bindings: list[AssistantToolExecutionBinding] | tuple[AssistantToolExecutionBinding, ...] | set[str] | list[str] | tuple[str, ...],
) -> set[str]:
    if isinstance(bindings, set):
        return {_normalize_string(item) for item in bindings if _normalize_string(item)}

    bound_ids: set[str] = set()
    for item in bindings:
        if isinstance(item, AssistantToolExecutionBinding):
            tool_id = _normalize_string(item.tool_id)
        else:
            tool_id = _normalize_string(item)
        if tool_id:
            bound_ids.add(tool_id)
    return bound_ids


def build_tool_executor_coverage(
    tool_definitions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    connected_tool_ids: list[AssistantToolExecutionBinding] | tuple[AssistantToolExecutionBinding, ...] | set[str] | list[str] | tuple[str, ...],
) -> dict[str, Any]:
    active_tool_ids = sorted(
        {
            _normalize_string(item.get("id"))
            for item in tool_definitions
            if isinstance(item, dict)
            and _normalize_string(item.get("id"))
            and _normalize_string(item.get("status")) == "active"
        }
    )
    connected = list_bound_tool_ids(connected_tool_ids)
    connected_tool_id_list = sorted(tool_id for tool_id in active_tool_ids if tool_id in connected)
    missing_executor_tool_ids = sorted(tool_id for tool_id in active_tool_ids if tool_id not in connected)
    coverage_rate = 1.0 if not active_tool_ids else round(len(connected_tool_id_list) / len(active_tool_ids), 4)
    return {
        "activeToolCount": len(active_tool_ids),
        "connectedToolCount": len(connected_tool_id_list),
        "coverageRate": coverage_rate,
        "connectedToolIds": connected_tool_id_list,
        "missingExecutorToolIds": missing_executor_tool_ids,
    }
