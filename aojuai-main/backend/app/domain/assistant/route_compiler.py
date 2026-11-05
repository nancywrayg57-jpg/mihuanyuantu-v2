from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, get_args, get_origin

from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.domain.assistant.tool_schema import (
    AssistantToolFieldSchema,
    AssistantToolSchema,
    assistant_tool,
    assistant_tool_field,
    assistant_tool_from_model,
    assistant_tool_internal_contract,
    build_tool_definition,
)


def _normalize_string(value: Any) -> str:
    return str(value or "").strip()


def _normalize_string_tuple(
    values: list[Any] | tuple[Any, ...] | set[Any] | None,
) -> tuple[str, ...]:
    return tuple(
        normalized
        for raw in (values or ())
        if (normalized := _normalize_string(raw))
    )


def _camelize_field_name(value: str) -> str:
    head, *tail = str(value or "").split("_")
    return head + "".join(part.capitalize() for part in tail if part)


_SPECIAL_PATH_RESOURCES: dict[tuple[str, str], str] = {
    ("forms", "templates"): "form_template",
    ("forms", "share-links"): "form_share",
    ("courses", "materials"): "course_material",
    ("courses", "chapters"): "course_chapter",
    ("courses", "lessons"): "course_lesson",
    ("courses", "categories"): "course_category",
    ("teachers", "categories"): "teacher_category",
}


def _singularize_resource_segment(value: str) -> str:
    normalized = _normalize_string(value)
    if normalized.endswith("ies") and len(normalized) > 3:
        return f"{normalized[:-3]}y"
    if normalized.endswith("s") and len(normalized) > 1:
        return normalized[:-1]
    return normalized


def _normalize_value_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is not None:
        non_none_args = [item for item in get_args(annotation) if item is not type(None)]
        if origin in {list, tuple, set, frozenset}:
            item_type = _normalize_value_type(non_none_args[0] if non_none_args else str)
            return f"{item_type}[]"
        if origin in {dict}:
            return "json"
        if len(non_none_args) == 1:
            return _normalize_value_type(non_none_args[0])
    if annotation in {int, float}:
        return "number"
    if annotation is bool:
        return "boolean"
    if annotation is datetime:
        return "datetime"
    if annotation is date:
        return "date"
    return "string"


def _extract_examples(field_info: Any) -> list[str]:
    raw_examples = getattr(field_info, "examples", None)
    if isinstance(raw_examples, (list, tuple, set)):
        return [_normalize_string(item) for item in raw_examples if _normalize_string(item)]
    json_schema_extra = getattr(field_info, "json_schema_extra", None)
    if isinstance(json_schema_extra, dict):
        nested_examples = json_schema_extra.get("examples")
        if isinstance(nested_examples, (list, tuple, set)):
            return [_normalize_string(item) for item in nested_examples if _normalize_string(item)]
    return []


def _normalize_custom_fields(
    items: list[dict[str, Any] | AssistantToolFieldSchema] | tuple[dict[str, Any] | AssistantToolFieldSchema, ...] | None,
) -> tuple[AssistantToolFieldSchema, ...]:
    normalized: list[AssistantToolFieldSchema] = []
    for item in items or ():
        if isinstance(item, AssistantToolFieldSchema):
            normalized.append(item)
            continue
        if not isinstance(item, dict):
            continue
        normalized.append(
            assistant_tool_field(
                str(item.get("key") or ""),
                str(item.get("label") or item.get("key") or ""),
                str(item.get("type") or item.get("valueType") or "string"),
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
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class AssistantPublishedRouteSpec:
    method: str
    path: str
    tool_id: str
    label: str
    scope_ids: tuple[str, ...]
    summary: str | None = None
    status: str = "active"
    tool_type: str | None = None
    resource: str | None = None
    confirmation_required: bool | None = None
    include_fields: tuple[str, ...] = field(default_factory=tuple)
    exclude_fields: tuple[str, ...] = field(default_factory=tuple)
    field_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    params_before: tuple[AssistantToolFieldSchema, ...] = field(default_factory=tuple)
    params_after: tuple[AssistantToolFieldSchema, ...] = field(default_factory=tuple)
    examples: tuple[str, ...] = field(default_factory=tuple)
    bindings: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    include_default_binding: bool = True


@dataclass(frozen=True, slots=True)
class AssistantPublishedRouteManifest:
    module_code: str
    routes: tuple[AssistantPublishedRouteSpec, ...]


@dataclass(frozen=True, slots=True)
class AssistantRouteLintIssue:
    code: str
    level: str
    method: str
    path: str
    tool_id: str
    message: str
    field_key: str | None = None


@dataclass(frozen=True, slots=True)
class AssistantRouteDraft:
    method: str
    path: str
    endpoint: str
    default_tool_id: str
    default_tool_type: str
    default_label: str
    default_summary: str
    default_resource: str | None
    request_model: str | None
    required_permissions: tuple[str, ...]
    field_keys: tuple[str, ...]


def assistant_published_route(
    method: str,
    path: str,
    tool_id: str,
    label: str,
    *,
    scope_ids: list[str] | tuple[str, ...],
    summary: str | None = None,
    status: str = "active",
    tool_type: str | None = None,
    resource: str | None = None,
    confirmation_required: bool | None = None,
    include_fields: list[str] | tuple[str, ...] | None = None,
    exclude_fields: list[str] | tuple[str, ...] | None = None,
    field_overrides: dict[str, dict[str, Any]] | None = None,
    params_before: list[dict[str, Any] | AssistantToolFieldSchema] | tuple[dict[str, Any] | AssistantToolFieldSchema, ...] | None = None,
    params_after: list[dict[str, Any] | AssistantToolFieldSchema] | tuple[dict[str, Any] | AssistantToolFieldSchema, ...] | None = None,
    examples: list[str] | tuple[str, ...] | None = None,
    bindings: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    include_default_binding: bool = True,
) -> AssistantPublishedRouteSpec:
    return AssistantPublishedRouteSpec(
        method=_normalize_string(method).upper(),
        path=_normalize_string(path),
        tool_id=_normalize_string(tool_id),
        label=_normalize_string(label),
        scope_ids=_normalize_string_tuple(scope_ids),
        summary=_normalize_string(summary) or None,
        status=_normalize_string(status) or "active",
        tool_type=_normalize_string(tool_type) or None,
        resource=_normalize_string(resource) or None,
        confirmation_required=confirmation_required,
        include_fields=_normalize_string_tuple(include_fields),
        exclude_fields=_normalize_string_tuple(exclude_fields),
        field_overrides=dict(field_overrides or {}),
        params_before=_normalize_custom_fields(params_before),
        params_after=_normalize_custom_fields(params_after),
        examples=_normalize_string_tuple(examples),
        bindings=tuple(item for item in (bindings or ()) if isinstance(item, dict)),
        include_default_binding=bool(include_default_binding),
    )


def assistant_published_manifest(
    module_code: str,
    routes: list[AssistantPublishedRouteSpec] | tuple[AssistantPublishedRouteSpec, ...],
) -> AssistantPublishedRouteManifest:
    return AssistantPublishedRouteManifest(
        module_code=_normalize_string(module_code),
        routes=tuple(item for item in routes if isinstance(item, AssistantPublishedRouteSpec)),
    )


def _iter_route_dependants(route: APIRoute) -> list[Any]:
    items: list[Any] = []
    stack = [route.dependant]
    while stack:
        dependant = stack.pop()
        items.append(dependant)
        for dependency in getattr(dependant, "dependencies", []) or []:
            sub_dependant = getattr(dependency, "dependant", None)
            if sub_dependant is not None:
                stack.append(sub_dependant)
    return items


def _extract_permission_codes(route: APIRoute) -> tuple[str, ...]:
    permissions: set[str] = set()
    for dependant in _iter_route_dependants(route):
        for dependency in getattr(dependant, "dependencies", []) or []:
            call = getattr(dependency, "call", None)
            raw_permissions = getattr(call, "required_permissions", None)
            if not isinstance(raw_permissions, (set, list, tuple)):
                continue
            permissions.update(
                normalized
                for raw in raw_permissions
                if (normalized := _normalize_string(raw))
            )
    return tuple(sorted(permissions))


def _resolve_route_body_model(route: APIRoute) -> Any | None:
    for param in getattr(route.dependant, "body_params", []) or []:
        annotation = (
            getattr(getattr(param, "field_info", None), "annotation", None)
            or getattr(param, "type_", None)
            or getattr(param, "annotation", None)
        )
        if hasattr(annotation, "model_fields"):
            return annotation
    return None


def _collect_scalar_params(route: APIRoute) -> tuple[Any, ...]:
    params: list[Any] = []
    for collection in (
        getattr(route.dependant, "path_params", []) or [],
        getattr(route.dependant, "query_params", []) or [],
        getattr(route.dependant, "body_params", []) or [],
    ):
        for param in collection:
            annotation = (
                getattr(getattr(param, "field_info", None), "annotation", None)
                or getattr(param, "type_", None)
                or getattr(param, "annotation", None)
            )
            if hasattr(annotation, "model_fields"):
                continue
            params.append(param)
    return tuple(params)


def _field_selected(
    *,
    candidates: tuple[str, ...],
    include_fields: tuple[str, ...],
    exclude_fields: tuple[str, ...],
) -> bool:
    normalized_candidates = {
        normalized
        for raw in candidates
        if (normalized := _normalize_string(raw))
    }
    if exclude_fields and normalized_candidates & set(exclude_fields):
        return False
    return not (include_fields and not normalized_candidates & set(include_fields))


def _build_scalar_param_fields(
    route: APIRoute,
    spec: AssistantPublishedRouteSpec,
) -> tuple[AssistantToolFieldSchema, ...]:
    fields: list[AssistantToolFieldSchema] = []
    for param in _collect_scalar_params(route):
        raw_name = _normalize_string(getattr(param, "name", None))
        field_info = getattr(param, "field_info", None)
        override = dict(spec.field_overrides.get(raw_name) or {})
        if override.get("drop") is True:
            continue
        alias = _normalize_string(getattr(field_info, "alias", None))
        if not alias or alias == raw_name:
            alias = _normalize_string(_camelize_field_name(raw_name) or raw_name)
        override_key = _normalize_string(override.get("key"))
        if not _field_selected(
            candidates=(raw_name, alias, override_key),
            include_fields=spec.include_fields,
            exclude_fields=spec.exclude_fields,
        ):
            continue
        key = override_key or alias or raw_name
        label = _normalize_string(override.get("label")) or key
        description = _normalize_string(override.get("description") or getattr(field_info, "description", None)) or f"{label}。"
        annotation = (
            getattr(field_info, "annotation", None)
            or getattr(param, "type_", None)
            or getattr(param, "annotation", None)
        )
        fields.append(
            assistant_tool_field(
                key=key,
                label=label,
                value_type=_normalize_string(override.get("type") or override.get("valueType") or _normalize_value_type(annotation)),
                required=bool(
                    override["required"]
                    if "required" in override
                    else getattr(param, "required", True)
                ),
                description=description,
                examples=list(override.get("examples") or _extract_examples(field_info)),
                enum_values=list(override.get("enumValues") or []),
                enum_options=list(override.get("enumOptions") or []),
                importance=_normalize_string(override.get("importance")) or None,
                downstream_effects=list(override.get("downstreamEffects") or []),
                follow_up_hint=_normalize_string(override.get("followUpHint")) or None,
                required_when=override.get("requiredWhen"),
            )
        )
    return tuple(fields)


def _infer_tool_type(route: APIRoute, spec: AssistantPublishedRouteSpec) -> str:
    if spec.tool_type:
        return spec.tool_type
    method = spec.method.upper()
    if method in {"PUT", "PATCH", "DELETE"}:
        return "mutation"
    body_model = _resolve_route_body_model(route)
    if method == "POST":
        if body_model is not None and str(getattr(body_model, "__name__", "")).endswith("Query"):
            return "query"
        if spec.path.endswith("/create"):
            return "mutation"
        return "query" if not getattr(route.dependant, "path_params", None) else "mutation"
    if method == "GET":
        return "preview" if getattr(route.dependant, "path_params", None) else "query"
    return "query"


def _default_summary(route: APIRoute) -> str:
    description = _normalize_string(getattr(route, "description", None))
    if description:
        return description
    summary = _normalize_string(getattr(route, "summary", None))
    if summary:
        return summary
    name = _normalize_string(getattr(route, "name", None))
    return name or "助手工具。"


def _default_resource(spec: AssistantPublishedRouteSpec) -> str | None:
    if spec.resource:
        return spec.resource
    parts = [part for part in spec.tool_id.split(".") if part]
    if len(parts) >= 2:
        return parts[1]
    path_parts = [part for part in spec.path.split("/") if part and not part.startswith("{")]
    if not path_parts:
        return None
    return _singularize_resource_segment(path_parts[0])


def _infer_resource_from_path(path: str) -> str | None:
    path_parts = [part for part in str(path or "").split("/") if part and not part.startswith("{")]
    if not path_parts:
        return None
    if len(path_parts) >= 2:
        special = _SPECIAL_PATH_RESOURCES.get((path_parts[0], path_parts[1]))
        if special:
            return special
    return _singularize_resource_segment(path_parts[0])


def _infer_default_action(route: APIRoute, *, tool_type: str) -> str:
    method = next(iter(sorted(route.methods or [])), "")
    normalized_method = _normalize_string(method).upper()
    if normalized_method == "POST" and route.path.endswith("/create"):
        return "create"
    if normalized_method in {"PUT", "PATCH"}:
        return "update"
    if tool_type == "preview":
        return "preview"
    if tool_type == "mutation":
        return "submit"
    return "list"


def _build_default_tool_id(
    *,
    module_code: str,
    resource: str | None,
    action: str,
) -> str:
    normalized_module = _normalize_string(module_code) or "module"
    normalized_resource = _normalize_string(resource) or "item"
    normalized_action = _normalize_string(action) or "query"
    return f"{normalized_module}.{normalized_resource}.{normalized_action}"


def _build_default_label(
    *,
    resource: str | None,
    action: str,
    summary: str,
) -> str:
    normalized_resource = _normalize_string(resource)
    if action == "create":
        return f"新增{normalized_resource}" if normalized_resource else "新增记录"
    if action == "update":
        return f"更新{normalized_resource}" if normalized_resource else "更新记录"
    if action == "preview":
        return f"预览{normalized_resource}详情" if normalized_resource else "预览详情"
    if action == "list":
        return f"查询{normalized_resource}" if normalized_resource else "查询列表"
    return summary or "候选助手工具"


def _build_bindings(
    route: APIRoute,
    spec: AssistantPublishedRouteSpec,
    *,
    summary: str,
    api_prefix: str,
) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    if spec.include_default_binding:
        for scope_id in spec.scope_ids:
            bindings.append(
                {
                    "scopeId": scope_id,
                    "kind": "endpoint",
                    "method": spec.method.upper(),
                    "path": f"{_normalize_string(api_prefix).rstrip('/')}{route.path}",
                    "summary": summary,
                }
            )
    bindings.extend(dict(item) for item in spec.bindings if isinstance(item, dict))
    return bindings


def _index_api_routes(api_router: APIRouter) -> dict[tuple[str, str], APIRoute]:
    indexed: dict[tuple[str, str], APIRoute] = {}
    for route in api_router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or ():
            normalized_method = _normalize_string(method).upper()
            if normalized_method:
                indexed[(normalized_method, route.path)] = route
    return indexed


def scan_api_route_drafts(
    api_router: APIRouter,
    *,
    module_code: str,
    include_path_prefixes: list[str] | tuple[str, ...] | None = None,
    exclude_path_prefixes: list[str] | tuple[str, ...] | None = None,
    exclude_methods: list[str] | tuple[str, ...] | None = None,
) -> list[AssistantRouteDraft]:
    include_prefixes = _normalize_string_tuple(include_path_prefixes)
    excluded_prefixes = _normalize_string_tuple(exclude_path_prefixes)
    excluded_methods = {item.upper() for item in _normalize_string_tuple(exclude_methods or ("DELETE",))}
    drafts: list[AssistantRouteDraft] = []

    for route in api_router.routes:
        if not isinstance(route, APIRoute):
            continue
        if include_prefixes and not any(route.path.startswith(prefix) for prefix in include_prefixes):
            continue
        if excluded_prefixes and any(route.path.startswith(prefix) for prefix in excluded_prefixes):
            continue
        tool_type = _infer_tool_type(
            route,
            AssistantPublishedRouteSpec(
                method=next(iter(sorted(route.methods or [])), "GET"),
                path=route.path,
                tool_id="draft",
                label="draft",
                scope_ids=(),
            ),
        )
        action = _infer_default_action(route, tool_type=tool_type)
        resource = _infer_resource_from_path(route.path)
        summary = _default_summary(route)
        request_model = _resolve_route_body_model(route)
        field_keys = [
            field.key
            for field in _build_scalar_param_fields(
                route,
                AssistantPublishedRouteSpec(
                    method=next(iter(sorted(route.methods or [])), "GET"),
                    path=route.path,
                    tool_id="draft",
                    label="draft",
                    scope_ids=(),
                ),
            )
        ]
        if request_model is not None:
            field_keys.extend(
                field.key
                for field in assistant_tool_from_model(
                    "draft",
                    "draft",
                    summary,
                    model_cls=request_model,
                    scope_ids=[],
                ).params
            )

        for method in sorted(route.methods or []):
            normalized_method = _normalize_string(method).upper()
            if not normalized_method or normalized_method in excluded_methods:
                continue
            drafts.append(
                AssistantRouteDraft(
                    method=normalized_method,
                    path=route.path,
                    endpoint=f"{route.endpoint.__module__}.{route.endpoint.__name__}",
                    default_tool_id=_build_default_tool_id(
                        module_code=module_code,
                        resource=resource,
                        action=action,
                    ),
                    default_tool_type=tool_type,
                    default_label=_build_default_label(
                        resource=resource,
                        action=action,
                        summary=summary,
                    ),
                    default_summary=summary,
                    default_resource=resource,
                    request_model=_normalize_string(getattr(request_model, "__name__", None)) or None,
                    required_permissions=_extract_permission_codes(route),
                    field_keys=tuple(dict.fromkeys(field_keys)),
                )
            )
    return drafts


def resolve_published_api_route(
    api_router: APIRouter,
    spec: AssistantPublishedRouteSpec,
) -> APIRoute:
    route = _index_api_routes(api_router).get((spec.method.upper(), spec.path))
    if route is None:
        raise LookupError(f"assistant published route not found: {spec.method} {spec.path}")
    return route


def compile_published_route_tool(
    api_router: APIRouter,
    spec: AssistantPublishedRouteSpec,
    *,
    api_prefix: str = "/api/v1",
) -> AssistantToolSchema:
    route = resolve_published_api_route(api_router, spec)
    summary = spec.summary or _default_summary(route)
    tool_type = _infer_tool_type(route, spec)
    confirmation_required = (
        spec.confirmation_required if spec.confirmation_required is not None else tool_type == "mutation"
    )
    required_permissions = list(_extract_permission_codes(route))
    scalar_fields = list(_build_scalar_param_fields(route, spec))
    bindings = _build_bindings(route, spec, summary=summary, api_prefix=api_prefix)
    request_model = _resolve_route_body_model(route)

    if request_model is not None:
        return assistant_tool_from_model(
            spec.tool_id,
            spec.label,
            summary,
            model_cls=request_model,
            scope_ids=list(spec.scope_ids),
            required_permissions=required_permissions,
            status=spec.status,
            confirmation_required=confirmation_required,
            params_before=[*spec.params_before, *scalar_fields],
            params_after=list(spec.params_after),
            include_keys=list(spec.include_fields) or None,
            exclude_keys=list(spec.exclude_fields) or None,
            field_overrides=dict(spec.field_overrides),
            examples=list(spec.examples),
            tool_type=tool_type,
            resource=_default_resource(spec),
            bindings=bindings,
        )

    return assistant_tool(
        spec.tool_id,
        spec.label,
        summary,
        status=spec.status,
        scope_ids=list(spec.scope_ids),
        required_permissions=required_permissions,
        confirmation_required=confirmation_required,
        params=[*spec.params_before, *scalar_fields, *spec.params_after],
        examples=list(spec.examples),
        tool_type=tool_type,
        resource=_default_resource(spec),
        internal_contract=assistant_tool_internal_contract(
            param_source="route_params" if scalar_fields else None,
            bindings=bindings,
        ),
    )


def build_published_route_tools(
    api_router: APIRouter,
    manifest: AssistantPublishedRouteManifest,
    *,
    api_prefix: str = "/api/v1",
) -> tuple[AssistantToolSchema, ...]:
    return tuple(
        compile_published_route_tool(
            api_router,
            spec,
            api_prefix=api_prefix,
        )
        for spec in manifest.routes
    )


def lint_published_route_manifest(
    api_router: APIRouter,
    manifest: AssistantPublishedRouteManifest,
    *,
    api_prefix: str = "/api/v1",
) -> list[AssistantRouteLintIssue]:
    issues: list[AssistantRouteLintIssue] = []
    for spec in manifest.routes:
        try:
            tool = compile_published_route_tool(api_router, spec, api_prefix=api_prefix)
        except Exception as exc:  # pragma: no cover
            issues.append(
                AssistantRouteLintIssue(
                    code="compile_error",
                    level="error",
                    method=spec.method,
                    path=spec.path,
                    tool_id=spec.tool_id,
                    message=str(exc),
                )
            )
            continue

        if not tool.required_permissions:
            issues.append(
                AssistantRouteLintIssue(
                    code="missing_permissions",
                    level="warning",
                    method=spec.method,
                    path=spec.path,
                    tool_id=spec.tool_id,
                    message="Published route has no explicit permission dependency.",
                )
            )

        definition = build_tool_definition(tool)
        for field in definition.get("params") or []:
            field_key = _normalize_string(field.get("key"))
            field_label = _normalize_string(field.get("label"))
            description = _normalize_string(field.get("description"))
            if not description:
                issues.append(
                    AssistantRouteLintIssue(
                        code="missing_description",
                        level="error",
                        method=spec.method,
                        path=spec.path,
                        tool_id=spec.tool_id,
                        field_key=field_key or None,
                        message="Field description is missing.",
                    )
                )
            elif description in {field_key, field_label, f"{field_key}。", f"{field_label}。"}:
                issues.append(
                    AssistantRouteLintIssue(
                        code="generic_description",
                        level="warning",
                        method=spec.method,
                        path=spec.path,
                        tool_id=spec.tool_id,
                        field_key=field_key or None,
                        message="Field description is too generic for assistant guidance.",
                    )
                )
            if bool(field.get("required")) and not list(field.get("examples") or []):
                issues.append(
                    AssistantRouteLintIssue(
                        code="missing_examples",
                        level="warning",
                        method=spec.method,
                        path=spec.path,
                        tool_id=spec.tool_id,
                        field_key=field_key or None,
                        message="Required field is missing examples.",
                    )
                )
    return issues
