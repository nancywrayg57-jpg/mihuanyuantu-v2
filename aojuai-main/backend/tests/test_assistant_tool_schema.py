from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.assistant.tool_schema import (
    assistant_tool,
    assistant_tool_field,
    assistant_tool_fields_from_pydantic_model,
    assistant_tool_from_model,
    assistant_tool_option,
    assistant_tool_required_when,
    assistant_tool_scope_binding,
    build_tool_definition,
    build_tool_executor_coverage,
)


def test_assistant_tool_schema_renders_field_metadata_for_follow_up_collection() -> None:
    tool = assistant_tool(
        "example.widget.create",
        "新增组件",
        "创建一个组件。",
        scope_ids=["example-admin"],
        required_permissions=["example:widget:create"],
        confirmation_required=True,
        params=[
            assistant_tool_field(
                "name",
                "名称",
                "string",
                required=True,
                description="组件名称。",
                examples=["演示组件"],
            ),
            assistant_tool_field(
                "visibilityType",
                "可见范围",
                "enum",
                description="组件可见范围。",
                enum_options=[
                    assistant_tool_option("private", "私有"),
                    assistant_tool_option("team", "团队可见"),
                ],
                importance="high",
                downstream_effects=["permissions", "collaboration_scope"],
                follow_up_hint="建议继续确认组件对哪些团队开放。",
            ),
            assistant_tool_field(
                "visibleTeamIds",
                "可见团队ID列表",
                "number[]",
                description="visibilityType=team 时必填。",
                required_when=assistant_tool_required_when(
                    "visibilityType",
                    equals="team",
                    description="当 visibilityType=team 时必须填写可见团队。",
                ),
            ),
        ],
    )

    definition = build_tool_definition(tool)
    field_map = {item["key"]: item for item in definition["params"]}

    assert definition["toolType"] == "mutation"
    assert definition["accessMode"] == "write"
    assert field_map["visibilityType"]["importance"] == "high"
    assert field_map["visibilityType"]["downstreamEffects"] == ["permissions", "collaboration_scope"]
    assert field_map["visibilityType"]["followUpHint"] == "建议继续确认组件对哪些团队开放。"
    assert field_map["visibleTeamIds"]["requiredWhen"] == {
        "key": "visibilityType",
        "equals": "team",
        "description": "当 visibilityType=team 时必须填写可见团队。",
    }


def test_assistant_tool_schema_builds_executor_coverage_from_active_tool_ids() -> None:
    coverage = build_tool_executor_coverage(
        [
            {"id": "example.widget.list", "status": "active"},
            {"id": "example.widget.create", "status": "active"},
            {"id": "example.widget.archive", "status": "planned"},
            {"id": "example.widget.preview", "status": "active"},
        ],
        {"example.widget.list", "example.widget.preview"},
    )

    assert coverage["activeToolCount"] == 3
    assert coverage["connectedToolCount"] == 2
    assert coverage["coverageRate"] == 0.6667
    assert coverage["connectedToolIds"] == [
        "example.widget.list",
        "example.widget.preview",
    ]
    assert coverage["missingExecutorToolIds"] == ["example.widget.create"]


def test_assistant_tool_schema_can_discover_fields_from_pydantic_model() -> None:
    class DemoQuery(BaseModel):
        page: int = Field(1, description="分页页码。", examples=["1"])
        organization_id: int | None = Field(None, alias="organizationId", description="限定所属组织。", examples=["3"])
        widget_ids: list[int] = Field(default_factory=list, alias="widgetIds", description="限定组件列表。", examples=["[1,2]"])

    params = assistant_tool_fields_from_pydantic_model(DemoQuery)
    field_map = {item.key: item for item in params}

    assert field_map["page"].description == "分页页码。"
    assert field_map["page"].examples == ("1",)
    assert field_map["page"].value_type == "number"
    assert field_map["organizationId"].description == "限定所属组织。"
    assert field_map["organizationId"].examples == ("3",)
    assert field_map["organizationId"].value_type == "number"
    assert field_map["widgetIds"].value_type == "number[]"


def test_assistant_tool_schema_can_build_model_backed_internal_contract() -> None:
    class DemoQuery(BaseModel):
        keyword: str | None = Field(None, description="关键词。", examples=["上海"])

    tool = assistant_tool_from_model(
        "example.widget.list",
        "查询组件",
        "读取组件列表。",
        model_cls=DemoQuery,
        scope_ids=["example-admin"],
        required_permissions=["example:widget:read"],
        bindings=[
            assistant_tool_scope_binding(
                "example-admin",
                method="POST",
                path="/api/v1/example/widgets",
                summary="示例查询接口",
            )
        ],
    )

    definition = build_tool_definition(tool)

    assert definition["internalContract"]["paramSource"] == "pydantic_model"
    assert definition["internalContract"]["requestModel"] == "DemoQuery"
    assert definition["internalContract"]["bindings"] == [
        {
            "scopeId": "example-admin",
            "kind": "endpoint",
            "method": "POST",
            "path": "/api/v1/example/widgets",
            "summary": "示例查询接口",
        }
    ]
