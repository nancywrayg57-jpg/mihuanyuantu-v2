"""与 schema **名称无关**的 API 契约快照，用来跨版本比对。

## 为什么不能直接 diff openapi.json

FastAPI 生成的 schema 名称**跨进程不稳定**。同一份代码连跑三次，
`SessionCreate` / `ChatRequest` / `MessageResponse` / `TaskStatus` 这些短名有冲突的
模型，谁拿到短名、谁被降级成 `app__domain__okr__coaching__schemas__ChatRequest`，
每次都可能不一样（固定 `PYTHONHASHSEED` 也压不住，冲突消歧走的是模型集合的
遍历顺序）。`operationId` 同理：多方法路由会从方法集合里随便取一个做后缀。

实测代价：一次重构后直接 diff openapi.json，报出 11 条路径"内容不同"，
看上去像是改坏了 API 契约。逐条展开 `$ref` 才确认 894 条路径**结构完全一致**，
差异全在名字上。**这份工具就是为了不再浪费那次时间。**

## 做法

把每个 `$ref` 就地展开成它指向的内容，并丢掉 `operationId`。
于是"叫什么名字"这一层被彻底抹掉，剩下的是真正的契约：
路径、方法、参数、请求体结构、响应体结构。

递归 schema 用**引用路径**判环（不是深度截断）：深度截断会把深层差异一起截掉，
那就又成了一个"看起来一致"的假象。

## 用法

    # 在两个 checkout 各跑一次
    .venv/bin/python -m governance_tools.api_contract > /tmp/before.json
    .venv/bin/python -m governance_tools.api_contract > /tmp/after.json
    .venv/bin/python -m governance_tools.api_contract --diff /tmp/before.json /tmp/after.json

注意两边要用**相同的 `.env` 与 `AOJ_ENABLED_MODULES`**：docs 路由受 `DEBUG` 控制，
模块开关会改变挂载哪些路由。实测踩过——旧 checkout 少了 `.env`（被 gitignore），
凭空多出 4 条 docs 路由差异。
"""

from __future__ import annotations

import json
import sys
from typing import Any

_REF_PREFIX = "#/components/schemas/"


def _resolve(document: dict[str, Any], node: Any, seen: frozenset[str] = frozenset()) -> Any:
    """把 `$ref` 展开成内容；`operationId` 丢弃；成环处标记为 `<recursive>`。"""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(_REF_PREFIX):
            name = ref[len(_REF_PREFIX) :]
            if name in seen:
                return "<recursive>"
            target = document.get("components", {}).get("schemas", {}).get(name)
            if target is None:
                # 指向不存在的 schema：这本身就是个问题，如实留下痕迹
                return {"$missing_ref": True}
            return _resolve(document, target, seen | {name})
        return {key: _resolve(document, value, seen) for key, value in node.items() if key != "operationId"}
    if isinstance(node, list):
        return [_resolve(document, item, seen) for item in node]
    return node


def build_contract(document: dict[str, Any] | None = None) -> dict[str, Any]:
    """从 OpenAPI 文档构造名称无关的契约。不传就现场生成。"""
    if document is None:
        from app.main import app

        document = app.openapi()

    return {path: _resolve(document, spec) for path, spec in sorted(document["paths"].items())}


def diff_contracts(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[str]]:
    """返回 {removed, added, changed}，全部按路径排序。"""
    keys_before, keys_after = set(before), set(after)
    return {
        "removed": sorted(keys_before - keys_after),
        "added": sorted(keys_after - keys_before),
        "changed": sorted(k for k in keys_before & keys_after if before[k] != after[k]),
    }


def main() -> int:
    if "--diff" in sys.argv:
        index = sys.argv.index("--diff")
        try:
            before_path, after_path = sys.argv[index + 1], sys.argv[index + 2]
        except IndexError:
            print("用法：--diff <before.json> <after.json>", file=sys.stderr)
            return 2

        with open(before_path, encoding="utf-8") as handle:
            before = json.load(handle)
        with open(after_path, encoding="utf-8") as handle:
            after = json.load(handle)

        result = diff_contracts(before, after)
        total = sum(len(value) for value in result.values())
        if total == 0:
            print(f"  API 契约完全一致（{len(before)} 条路径）")
            return 0
        for label, paths in result.items():
            if paths:
                print(f"  {label}（{len(paths)}）：")
                for path in paths[:20]:
                    print(f"      {path}")
                if len(paths) > 20:
                    print(f"      …… 还有 {len(paths) - 20} 条")
        return 1

    json.dump(build_contract(), sys.stdout, ensure_ascii=False, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
