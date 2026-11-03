"""模块依赖方向写成测试。

这是回流里最要紧的一条：留言→工单的联动一旦让两个模块互相 import，以后就拆不开，
而"缠在一起"通常不是有意为之，是某次改动顺手 import 了对方。

允许的方向只有一个：
    cms_public（调用方，守卫后延迟 import） ──▶ app.capabilities.support.bridge
反向、以及 support 对任何业务域的依赖，一律判红。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[3] / "app" / "capabilities" / "support"
CMS_PUBLIC = Path(__file__).resolve().parents[3] / "app" / "api" / "v1" / "endpoints" / "cms_public.py"

#: support 允许认识的模块前缀：内核 + 多租户/授权根 + 通知（base 里无条件挂载）。
ALLOWED_PREFIXES = (
    "app.core.",
    "app.api.deps",
    "app.infrastructure.",
    "app.domain.menus",
    "app.domain.roles",
    "app.domain.users",
    "app.domain.notifications",
    "alembic",
    "app.capabilities.support",
)

FORBIDDEN_SUBSTRINGS = ("cms", "public_site", "jisku", "logistics", "ecom")


def _pack_sources() -> list[Path]:
    return sorted(
        path
        for path in PACKAGE_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize("path", _pack_sources(), ids=lambda p: p.name)
def test_pack_never_imports_a_business_domain(path: Path) -> None:
    offenders = [
        module
        for module in _imported_modules(path)
        if module.startswith("app.") and not module.startswith(ALLOWED_PREFIXES)
    ]
    assert not offenders, f"{path.name} imports {offenders}"


def _non_docstring_string_literals(path: Path) -> list[str]:
    """所有**不是 docstring** 的字符串字面量。

    注释和 docstring 里解释联动方向是好事，不该判红；能判红的是代码里的软引用，
    例如 `is_module_installed("cms")`——它是真实依赖，只是编译器抓不到。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


@pytest.mark.parametrize("path", _pack_sources(), ids=lambda p: p.name)
def test_pack_code_carries_no_soft_reference_to_another_module(path: Path) -> None:
    hits = [
        literal
        for literal in _non_docstring_string_literals(path)
        if any(token in literal.lower() for token in FORBIDDEN_SUBSTRINGS)
    ]
    assert not hits, f"{path.name} 的代码里出现了对别的模块的软引用：{hits}"


def test_contact_bridge_is_guarded_and_lazily_imported() -> None:
    """CMS 侧必须先判"装没装"，再延迟 import；模块级 import 会把可选联动变成硬依赖。"""
    source = CMS_PUBLIC.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CMS_PUBLIC))

    module_level = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any(
        module.startswith("app.capabilities.") for module in module_level
    ), "CMS 的模块级 import 里不许出现任何能力包"

    bridge_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_bridge_contact_to_support"
    )
    called = {
        node.func.id
        for node in ast.walk(bridge_fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "is_module_installed" in called
    assert "is_module_enabled_for_tenant" in called
    # 用 ensure_* 就会把"别人的模块关着"变成本接口的 403 —— 留言必须照样落库。
    assert "ensure_module_enabled_for_tenant" not in called

    lazy_imports = {
        node.module
        for node in ast.walk(bridge_fn)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "app.capabilities.support.bridge" in lazy_imports


def test_bridge_signature_takes_no_foreign_types() -> None:
    """桥接函数的入参只能是标量：签名里出现对方的类型就等于硬依赖。"""
    import inspect

    from app.capabilities.support.bridge import create_ticket_from_public_contact

    annotations = [
        str(parameter.annotation)
        for name, parameter in inspect.signature(create_ticket_from_public_contact).parameters.items()
        if name != "db"
    ]
    assert not any("Cms" in annotation or "cms" in annotation for annotation in annotations)
