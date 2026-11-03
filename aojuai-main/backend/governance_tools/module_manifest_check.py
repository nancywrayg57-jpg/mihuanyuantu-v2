"""GOV-18: 每个内置能力都必须声明硬安装边界。

"不安装就不加载"要成立，得有人说清楚这个模块的代码住在哪、模型在哪、表叫什么。
少一条就漏一层：
- 缺 `code_paths` → 删了代码目录，开关项还在，前端照样给用户看一个点不开的模块
- 缺 `model_modules` → 模型仍写死在 `app/domain/__init__.py`，删代码 = 进程起不来
- 缺 `table_prefixes` → 硬卸载后第一次 autogenerate 生成 DROP TABLE，把残留数据删了

这条检查是静态解析（AST），不 import 应用代码——门禁不该依赖运行环境。
清单文件：`app/core/module_manifest.py`；目录文件：`app/core/feature_switches.py`。

能力包（`app/capabilities/<code>/`）不在这条的管辖内：它们靠目录扫描发现，
删目录就整条消失，迁移链和表也随包走，边界天然成立。
"""

from __future__ import annotations

import ast
from pathlib import Path

from .common import ScanResult, Violation, require_discovered, validate_allowlist

MODULE_MANIFEST_ALLOWLIST: dict[str, str] = {}

_CATALOG_FILE = "app/core/feature_switches.py"
_MANIFEST_FILE = "app/core/module_manifest.py"
_REQUIRED_MANIFEST_FIELDS = ("code_paths", "model_modules", "table_prefixes")


def _string_keyword(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            value = keyword.value.value
            if isinstance(value, str):
                return value
    return None


def _nonempty_tuple_keyword(call: ast.Call, name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg != name:
            continue
        node = keyword.value
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return bool(node.elts)
        return True  # 非字面量（变量/推导式）不在这条的判断范围内
    return False


def _assigned_calls(tree: ast.AST, target_name: str, call_name: str) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        if not any(isinstance(t, ast.Name) and t.id == target_name for t in targets):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == call_name
            ):
                calls.append(inner)
    return calls


def discover_builtin_module_codes(backend_root: Path) -> tuple[str, ...]:
    path = backend_root / _CATALOG_FILE
    if not path.is_file():
        return ()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    codes = [
        code
        for call in _assigned_calls(tree, "_BUILTIN_MODULE_CATALOG", "ModuleCatalogItem")
        if (code := _string_keyword(call, "code"))
    ]
    return tuple(codes)


def scan_module_manifests(
    backend_root: Path,
    *,
    allowlist: dict[str, str] | None = None,
) -> ScanResult:
    allowed = MODULE_MANIFEST_ALLOWLIST if allowlist is None else allowlist
    validate_allowlist("GOV-18", allowed)

    discovered = discover_builtin_module_codes(backend_root)
    require_discovered("GOV-18", discovered, "builtin module catalog entries")

    violations: list[Violation] = []
    manifest_path = backend_root / _MANIFEST_FILE
    if not manifest_path.is_file():
        return ScanResult(
            rule="GOV-18",
            discovered=discovered,
            violations=(
                Violation("GOV-18", _MANIFEST_FILE, 0, "module manifest file is missing"),
            ),
        )

    manifest_tree = ast.parse(manifest_path.read_text(encoding="utf-8"))
    manifest_calls = _assigned_calls(manifest_tree, "BUILTIN_MODULE_MANIFESTS", "BuiltinModuleManifest")
    by_code = {
        code: call for call in manifest_calls if (code := _string_keyword(call, "code"))
    }

    for code in discovered:
        if code in allowed:
            continue
        call = by_code.get(code)
        if call is None:
            violations.append(
                Violation(
                    "GOV-18",
                    _MANIFEST_FILE,
                    0,
                    f"builtin module '{code}' has no BuiltinModuleManifest; "
                    "declare code_paths / model_modules / table_prefixes so it can be hard-uninstalled",
                )
            )
            continue
        for field in _REQUIRED_MANIFEST_FIELDS:
            if not _nonempty_tuple_keyword(call, field):
                violations.append(
                    Violation(
                        "GOV-18",
                        _MANIFEST_FILE,
                        call.lineno,
                        f"builtin module '{code}' declares no {field}",
                    )
                )

    for code, call in by_code.items():
        if code not in discovered:
            violations.append(
                Violation(
                    "GOV-18",
                    _MANIFEST_FILE,
                    call.lineno,
                    f"manifest declares '{code}', which is not in the builtin module catalog",
                )
            )

    return ScanResult(rule="GOV-18", discovered=discovered, violations=tuple(violations))
