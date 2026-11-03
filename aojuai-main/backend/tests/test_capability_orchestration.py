from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from alembic.config import Config

from app.core.capability_registry import CapabilityDefinition, order_capabilities
from app.capabilities.sample_items import CAPABILITY
from scripts import capability


def test_heads_include_core_and_only_installed_packs(capsys: pytest.CaptureFixture[str]) -> None:
    assert capability.show_heads() == 0
    output = capsys.readouterr().out
    # 断言不变量而不是某个具体 revision：写死 revision 的话，每加一条迁移
    # 这个测试就得跟着改一次，而它想守的其实是"core 链恰好一个 head、
    # 未安装的能力包不出现在里面"。
    core_lines = [line for line in output.splitlines() if line.startswith("core: ")]
    assert len(core_lines) == 1, f"core 链必须恰好一个 head：{output!r}"
    assert core_lines[0].removeprefix("core: ").strip(), "core head 不能为空"
    assert core_lines[0].removeprefix("core: ").strip() == capability._static_head(
        capability._core_config(), "core"
    )
    assert "sample_items:" not in output


def test_head_check_detects_two_heads_and_restored_chain_is_green(tmp_path: Path) -> None:
    script_dir = tmp_path / "alembic"
    versions = script_dir / "versions"
    versions.mkdir(parents=True)
    (versions / "one.py").write_text('revision = "one"\ndown_revision = None\n', encoding="utf-8")
    config = Config()
    config.set_main_option("script_location", str(script_dir))
    assert capability._static_head(config, "fixture") == "one"

    second = versions / "two.py"
    second.write_text('revision = "two"\ndown_revision = None\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="exactly one migration head"):
        capability._static_head(config, "fixture")
    second.unlink()
    assert capability._static_head(config, "fixture") == "one"


def test_orchestrator_uses_lock_and_alembic_without_create_all() -> None:
    """迁移是 schema 的唯一真源——但 SQLite 新库是有据可查的例外。

    原来这里断言 `create_all` 一个字都不许出现。轻量部署（SQLite）落地后这条
    过严了：核心链里有一批 PostgreSQL 专有的历史迁移在 SQLite 上不可重放，
    新库只能用 ORM metadata 建表再 stamp 到 head —— 这与 `init_db()` 的
    SQLite 分支是同一套语义，不是绕开迁移。

    所以真正要守的不变量有两条，逐条断言：
    1. PostgreSQL 路径必须仍然走 `command.upgrade`，不许被 create_all 顶替；
    2. create_all 只能出现在带方言判断的 SQLite 引导里。
    """
    source = inspect.getsource(capability)
    assert "pg_advisory_lock" in source
    assert 'command.upgrade(core_config, "head")' in source
    assert CAPABILITY.version_table == "alembic_version_cap_sample_items"

    bootstrap = inspect.getsource(capability._bootstrap_core_on_sqlite)
    # 只看真正的调用点；日志里出现 "create_all" 这几个字不算。
    create_all_sites = [
        line for line in source.splitlines() if ".create_all(" in line
    ]
    assert create_all_sites, "SQLite 引导没了？那新库根本装不上"
    for line in create_all_sites:
        assert line in bootstrap, (
            f"create_all 出现在 SQLite 引导之外：{line.strip()!r}；"
            "迁移仍然是 PostgreSQL 的唯一真源"
        )
    assert "get_dialect().single_writer" in source, "引导必须由方言能力位把守"


def test_destructive_purge_requires_explicit_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert capability.main(["db", "purge", "sample_items"]) == 1
    assert "without explicit --purge" in capsys.readouterr().err


def definition(code: str, dependencies: tuple[str, ...]) -> CapabilityDefinition:
    return CapabilityDefinition(
        code=code,
        label=code,
        description=code,
        layer="pack",
        version="1.0.0",
        dependencies=dependencies,
        api_prefix=f"/{code}",
        router_module=f"app.capabilities.{code}.api",
        seed_module=f"app.capabilities.{code}.seed",
        version_table=f"alembic_version_cap_{code}",
    )


def test_dependency_order_rejects_mutation_and_restores_green() -> None:
    parent = definition("parent_pack", ("core",))
    child = definition("child_pack", ("parent_pack",))
    assert [item.code for item in order_capabilities((child, parent))] == [
        "parent_pack",
        "child_pack",
    ]

    with pytest.raises(ValueError, match="missing installed dependency"):
        order_capabilities((child,))
    cyclic_parent = definition("parent_pack", ("child_pack",))
    with pytest.raises(ValueError, match="cyclic capability dependency"):
        order_capabilities((child, cyclic_parent))
    assert [item.code for item in order_capabilities((child, parent))] == [
        "parent_pack",
        "child_pack",
    ]
