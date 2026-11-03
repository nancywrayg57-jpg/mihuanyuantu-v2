from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.domain.assistant.route_compiler import (
    assistant_published_manifest,
    assistant_published_route,
    build_published_route_tools,
    lint_published_route_manifest,
    scan_api_route_drafts,
)
from app.domain.assistant.tool_schema import build_tool_definition


class DemoWidgetQuery(BaseModel):
    keyword: str | None = Field(None, description="关键词。", examples=["训练营"])
    organization_id: int | None = Field(None, alias="organizationId", description="限定所属组织。", examples=["8"])


class DemoWidgetCreate(BaseModel):
    name: str = Field(..., description="组件名称。", examples=["AI 训练营助手"])
    visibility_type: str = Field("private", alias="visibilityType", description="可见范围。", examples=["team"])
    visible_team_ids: list[int] = Field(default_factory=list, alias="visibleTeamIds", description="可见团队。", examples=["[1,2]"])


class DemoWidgetUpdate(BaseModel):
    name: str | None = Field(None, description="组件名称。", examples=["新名称"])


def require_permissions(*permissions: str):
    async def _dependency() -> None:
        return None

    _dependency.required_permissions = set(permissions)
    return _dependency


router = APIRouter()


@router.post(
    "/widgets",
    summary="查询组件列表",
    dependencies=[Depends(require_permissions("example:widget:read"))],
)
async def list_widgets(payload: DemoWidgetQuery) -> dict[str, object]:
    return {"items": [], "query": payload.model_dump(by_alias=True)}


@router.post(
    "/widgets/create",
    summary="创建组件",
    dependencies=[Depends(require_permissions("example:widget:create"))],
)
async def create_widget(payload: DemoWidgetCreate) -> dict[str, object]:
    return {"id": 1, "payload": payload.model_dump(by_alias=True)}


@router.put(
    "/widgets/{widget_id}",
    summary="更新组件",
    dependencies=[Depends(require_permissions("example:widget:update"))],
)
async def update_widget(
    widget_id: int,
    payload: DemoWidgetUpdate,
) -> dict[str, object]:
    return {"id": widget_id, "payload": payload.model_dump(by_alias=True)}


@router.get(
    "/forms/templates/{template_id}",
    summary="查看模板详情",
    dependencies=[Depends(require_permissions("example:form_template:read"))],
)
async def preview_form_template(template_id: int) -> dict[str, int]:
    return {"id": template_id}


@router.get(
    "/widgets/report",
    summary="查询报表",
    dependencies=[Depends(require_permissions("example:report:read"))],
)
async def report_widgets(
    date_from: str = Query(..., alias="dateFrom", description="开始日期。", examples=["2026-04-01"]),
) -> dict[str, str]:
    return {"dateFrom": date_from}


@router.delete(
    "/widgets/{widget_id}",
    summary="删除组件",
    dependencies=[Depends(require_permissions("example:widget:delete"))],
)
async def delete_widget(widget_id: int) -> dict[str, int]:
    return {"id": widget_id}


def test_route_scanner_discovers_candidates_before_publish() -> None:
    drafts = scan_api_route_drafts(
        router,
        module_code="example",
        include_path_prefixes=["/widgets", "/forms/templates"],
        exclude_path_prefixes=["/widgets/report"],
    )
    draft_map = {(item.method, item.path): item for item in drafts}

    assert ("POST", "/widgets/create") in draft_map
    assert draft_map[("POST", "/widgets/create")].default_tool_id == "example.widget.create"
    assert draft_map[("POST", "/widgets")].default_tool_id == "example.widget.list"
    assert draft_map[("GET", "/forms/templates/{template_id}")].default_tool_id == "example.form_template.preview"
    assert draft_map[("POST", "/widgets")].request_model == "DemoWidgetQuery"
    assert "organizationId" in draft_map[("POST", "/widgets")].field_keys
    assert "widgetId" in draft_map[("PUT", "/widgets/{widget_id}")].field_keys
    assert all(item.method != "DELETE" for item in drafts)


def test_published_route_compiler_extracts_path_params_and_bindings() -> None:
    manifest = assistant_published_manifest(
        "example",
        [
            assistant_published_route(
                "PUT",
                "/widgets/{widget_id}",
                "example.widget.update",
                "更新组件",
                scope_ids=["example-admin"],
                field_overrides={
                    "widget_id": {
                        "key": "widgetId",
                        "label": "组件ID",
                        "description": "要更新的组件ID。",
                        "examples": ["18"],
                    }
                },
            ),
            assistant_published_route(
                "GET",
                "/forms/templates/{template_id}",
                "example.form_template.preview",
                "预览表单模板",
                scope_ids=["example-admin"],
                field_overrides={
                    "template_id": {
                        "key": "templateId",
                        "label": "模板ID",
                        "description": "要查看的模板ID。",
                        "examples": ["12"],
                    }
                },
            ),
        ],
    )

    tool_map = {
        item.tool_id: item
        for item in build_published_route_tools(router, manifest)
    }

    widget_update = build_tool_definition(tool_map["example.widget.update"])
    assert widget_update["params"][0] == {
        "key": "widgetId",
        "label": "组件ID",
        "type": "number",
        "required": True,
        "description": "要更新的组件ID。",
        "examples": ["18"],
        "enumValues": [],
        "enumOptions": [],
    }
    assert widget_update["internalContract"]["requestModel"] == "DemoWidgetUpdate"
    assert widget_update["internalContract"]["bindings"] == [
        {
            "scopeId": "example-admin",
            "kind": "endpoint",
            "method": "PUT",
            "path": "/api/v1/widgets/{widget_id}",
            "summary": "更新组件",
        }
    ]

    template_preview = build_tool_definition(tool_map["example.form_template.preview"])
    assert template_preview["toolType"] == "preview"
    assert template_preview["resource"] == "form_template"
    assert template_preview["params"][0]["key"] == "templateId"
    assert template_preview["requiredPermissions"] == ["example:form_template:read"]


def test_published_route_manifest_lint_flags_generic_descriptions() -> None:
    manifest = assistant_published_manifest(
        "example",
        [
            assistant_published_route(
                "GET",
                "/widgets/report",
                "example.report.list",
                "查询报表",
                scope_ids=["example-admin"],
                field_overrides={
                    "date_from": {
                        "key": "dateFrom",
                        "label": "dateFrom",
                        "description": "dateFrom。",
                        "examples": ["2026-04-01"],
                    }
                },
            )
        ],
    )

    issues = lint_published_route_manifest(router, manifest)

    assert any(item.code == "generic_description" for item in issues)
    assert not [item for item in issues if item.level == "error"]
