"""GOV-23：API 契约的比对必须与 schema **名称**无关。

## 背景

FastAPI 生成的 schema 名称跨进程不稳定：同一份代码连跑三次，
`SessionCreate` / `ChatRequest` / `MessageResponse` / `TaskStatus` 这些短名有冲突的
模型，谁拿到短名、谁被降级成 `app__domain__okr__coaching__schemas__ChatRequest`，
每次都可能不同（固定 `PYTHONHASHSEED` 也压不住）。`operationId` 同理。

实测代价：一次重构后直接 diff openapi.json，报出 11 条路径"内容不同"，
看着像改坏了契约；逐条展开 `$ref` 才确认 894 条路径结构完全一致，差异全在名字上。

`governance_tools/api_contract.py` 把这件事固化下来。这里钉住它真的有效——
**否则它本身就会变成下一个"看起来一致"的假象**。
"""

from __future__ import annotations

import json

from governance_tools.api_contract import build_contract, diff_contracts


def _find_unstable_keys(node, trail=()):
    """定位契约里残留的 `$ref` / `operationId`，返回它们的位置。

    **不要直接 `assert "operationId" not in json.dumps(contract)`。**
    真实契约序列化后是几兆的字符串，断言一旦失败，pytest 渲染这个操作数要跑到
    几分钟——一条要等几分钟才报错的守卫等于没有。（第一版就是这么写的，
    变异验证时卡了 200 秒才发现。）这里只收集少量位置信息。
    """
    hits = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("$ref", "operationId"):
                hits.append("/".join(map(str, trail)) + f" -> {key}")
            hits.extend(_find_unstable_keys(value, trail + (key,)))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            hits.extend(_find_unstable_keys(item, trail + (index,)))
    return hits


def test_contract_carries_no_schema_names():
    """契约里不得残留 `$ref` 或 `operationId`——那正是不稳定的两处。

    留一处，比对就会重新受名字影响，而且失败时看起来像真的契约变更。
    """
    hits = _find_unstable_keys(build_contract())

    assert not hits, f"契约里残留了 {len(hits)} 处不稳定字段，例如：{hits[:5]}"


def test_renaming_a_schema_does_not_change_the_contract():
    """把 schema 改名，契约必须不变——这是本工具存在的全部理由。

    直接 diff openapi.json 在这种情况下会报差异，也正是那次误判的成因。
    """
    document = {
        "paths": {
            "/x": {"post": {"requestBody": {"content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/Short"}}}}}}
        },
        "components": {"schemas": {"Short": {"type": "object", "properties": {"a": {"type": "string"}}}}},
    }
    renamed = {
        "paths": {
            "/x": {"post": {"requestBody": {"content": {"application/json": {
                "schema": {"$ref": "#/components/schemas/app__domain__x__schemas__Short"}}}}}}
        },
        "components": {"schemas": {
            "app__domain__x__schemas__Short": {"type": "object", "properties": {"a": {"type": "string"}}}}},
    }

    assert build_contract(document) == build_contract(renamed)


def test_a_real_field_change_is_still_caught():
    """光"不受名字影响"不够——真的改了字段必须报出来。

    少了这条，一个永远返回"一致"的工具同样能通过上一条测试。
    """
    base = {
        "paths": {"/x": {"post": {"requestBody": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/S"}}}}}}},
        "components": {"schemas": {"S": {"type": "object", "properties": {"a": {"type": "string"}}}}},
    }
    changed = json.loads(json.dumps(base))
    changed["components"]["schemas"]["S"]["properties"]["b"] = {"type": "integer"}

    result = diff_contracts(build_contract(base), build_contract(changed))

    assert result["changed"] == ["/x"], f"字段变化没被抓到：{result}"


def test_recursive_schema_terminates_without_truncating_depth():
    """递归 schema 靠**引用路径判环**，不靠深度截断。

    深度截断会把深层的真实差异一起截掉——那就又是一个"看起来一致"的假象。
    这里构造一个自引用 schema：既要能结束，又要保留到成环那一层为止的内容。
    """
    document = {
        "paths": {"/n": {"get": {"responses": {"200": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/Node"}}}}}}}},
        "components": {"schemas": {"Node": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "child": {"$ref": "#/components/schemas/Node"},
            },
        }}},
    }

    contract = build_contract(document)  # 不得无限递归
    node = contract["/n"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert node["properties"]["name"] == {"type": "string"}
    assert node["properties"]["child"] == "<recursive>"


def test_added_and_removed_paths_are_reported():
    """新增/删除路径要分开报，不能混进 changed。"""
    before = {"/a": {"get": {}}, "/b": {"get": {}}}
    after = {"/b": {"get": {}}, "/c": {"get": {}}}

    assert diff_contracts(before, after) == {
        "removed": ["/a"],
        "added": ["/c"],
        "changed": [],
    }
