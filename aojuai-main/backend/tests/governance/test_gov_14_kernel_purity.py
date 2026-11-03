"""GOV-14 的形态判定：模块级 / TYPE_CHECKING / 函数体内延迟 import 三类分别怎么判。

真仓库跑一遍保证现状干净，其余用合成内核文件把"接受"和"仍然拒绝"的形态各钉一遍——
只断言"真仓库干净"是假绿：扫描器判错了形态，真仓库照样是绿的。
"""

from pathlib import Path

import pytest

from governance_tools.common import assert_clean
from governance_tools.kernel_purity import (
    KERNEL_IMPORT_ALLOWLIST,
    KERNEL_LAZY_IMPORT_ALLOWLIST,
    scan_kernel_purity,
)

_FORBIDDEN = "app.domain.assistant.openai_client"


def _write_kernel_file(backend_root: Path, source: str, *, name: str = "probe.py") -> str:
    core = backend_root / "app" / "core"
    core.mkdir(parents=True, exist_ok=True)
    (core / name).write_text(source, encoding="utf-8")
    return f"app/core/{name}"


def _scan(backend_root: Path, *, lazy_allowlist: dict[str, str] | None = None):
    return scan_kernel_purity(backend_root, allowlist={}, lazy_allowlist=lazy_allowlist or {})


def test_gov_14_repository_kernel_is_pure(backend_root: Path) -> None:
    result = scan_kernel_purity(backend_root)
    assert result.discovered
    assert_clean(result)


def test_gov_14_module_level_capability_import_is_rejected(tmp_path: Path) -> None:
    _write_kernel_file(tmp_path, f"from {_FORBIDDEN} import OpenAIClient\n")

    with pytest.raises(AssertionError, match="kernel imports capability domain 'assistant'"):
        assert_clean(_scan(tmp_path))


def test_gov_14_capability_package_import_is_rejected(tmp_path: Path) -> None:
    _write_kernel_file(tmp_path, "import app.capabilities.credits\n")

    with pytest.raises(AssertionError, match="kernel imports capability package"):
        assert_clean(_scan(tmp_path))


def test_gov_14_auth_and_tenancy_roots_stay_allowed(tmp_path: Path) -> None:
    _write_kernel_file(
        tmp_path,
        "from app.domain.users.models import User\nfrom app.domain.roles.models import Role\n",
    )

    assert_clean(_scan(tmp_path))


def test_gov_14_type_checking_block_is_not_a_runtime_dependency(tmp_path: Path) -> None:
    """`if TYPE_CHECKING:` 里的 import 运行期不执行，空基座照样 import 得动内核，不判红。"""
    _write_kernel_file(
        tmp_path,
        "from __future__ import annotations\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        f"    from {_FORBIDDEN} import OpenAIClient\n"
        "def build() -> 'OpenAIClient': ...\n",
    )

    assert_clean(_scan(tmp_path))


def test_gov_14_type_checking_else_branch_is_still_scanned(tmp_path: Path) -> None:
    """只跳过 `if TYPE_CHECKING:` 的主体；else 分支是货真价实的运行期代码。"""
    _write_kernel_file(
        tmp_path,
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    pass\n"
        "else:\n"
        f"    from {_FORBIDDEN} import OpenAIClient\n",
    )

    with pytest.raises(AssertionError, match="kernel imports capability domain 'assistant'"):
        assert_clean(_scan(tmp_path))


def test_gov_14_lazy_import_inside_function_is_still_rejected_by_default(tmp_path: Path) -> None:
    """延迟 import 能打破 import 环，但依赖还在——不写豁免就仍然是层次倒置。"""
    _write_kernel_file(
        tmp_path,
        "def build():\n"
        f"    from {_FORBIDDEN} import OpenAIClient\n"
        "    return OpenAIClient\n",
    )

    with pytest.raises(AssertionError, match="lazy import inside a function only defers"):
        assert_clean(_scan(tmp_path))


def test_gov_14_lazy_import_inside_nested_and_async_function_is_rejected(tmp_path: Path) -> None:
    _write_kernel_file(
        tmp_path,
        "async def build():\n"
        "    def inner():\n"
        f"        import {_FORBIDDEN}\n"
        "    return inner\n",
    )

    with pytest.raises(AssertionError, match="lazy import inside a function only defers"):
        assert_clean(_scan(tmp_path))


def test_gov_14_lazy_import_allowlist_is_scoped_to_one_file_and_one_module(tmp_path: Path) -> None:
    relative = _write_kernel_file(
        tmp_path,
        "def build():\n"
        f"    from {_FORBIDDEN} import OpenAIClient\n"
        "def other():\n"
        "    from app.domain.credits.service import CreditService\n",
    )
    lazy = {f"{relative}::{_FORBIDDEN}": "unit test fixture"}

    result = _scan(tmp_path, lazy_allowlist=lazy)

    messages = [violation.message for violation in result.violations]
    assert len(messages) == 1, messages
    assert "app.domain.credits.service" in messages[0]


def test_gov_14_lazy_allowlist_does_not_cover_the_same_module_at_module_level(tmp_path: Path) -> None:
    """豁免只给"函数体内"的形态；同一个模块提到模块级就是硬违规，必须仍然变红。"""
    relative = _write_kernel_file(tmp_path, f"from {_FORBIDDEN} import OpenAIClient\n")
    lazy = {f"{relative}::{_FORBIDDEN}": "unit test fixture"}

    with pytest.raises(AssertionError, match="kernel imports capability domain 'assistant'"):
        assert_clean(_scan(tmp_path, lazy_allowlist=lazy))


def test_gov_14_shipped_allowlists_carry_reasons_and_point_at_real_files(backend_root: Path) -> None:
    for relative, reason in KERNEL_IMPORT_ALLOWLIST.items():
        assert reason.strip(), relative
        assert (backend_root / relative).is_file(), relative
    for key, reason in KERNEL_LAZY_IMPORT_ALLOWLIST.items():
        assert reason.strip(), key
        relative, separator, module = key.partition("::")
        assert separator == "::", f"lazy allowlist key must be '<path>::<module>': {key}"
        assert module, key
        assert (backend_root / relative).is_file(), key
