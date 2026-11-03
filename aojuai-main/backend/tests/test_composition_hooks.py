"""内核组合层扩展点：纯 base 静默跳过；有 app/plugins 包时按阶段调用；translator 坏了不盖住原异常。"""

from __future__ import annotations

import sys
import textwrap
from importlib import invalidate_caches

import pytest

from app.core import composition


def test_pure_base_has_no_composition() -> None:
    assert composition.load_app_wiring() is None
    assert composition.register_scheduler_jobs(object()) == ()
    assert composition.translate_exception(RuntimeError("x")) is None


@pytest.mark.asyncio
async def test_phases_are_dispatched_when_composition_package_exists(tmp_path, monkeypatch) -> None:
    pkg = tmp_path / "fakeapp" / "plugins"
    pkg.mkdir(parents=True)
    (tmp_path / "fakeapp" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app_wiring.py").write_text(
        textwrap.dedent(
            """
            CALLS = []
            async def run_plugin_startup(app): CALLS.append(("startup", app))
            async def run_plugin_shutdown(app): CALLS.append(("shutdown", app))
            def register_plugin_scheduler_jobs(scheduler): CALLS.append(("jobs", scheduler)); return ("demo_job",)
            def install_plugin_routes(app): CALLS.append(("routes", app))
            def translate_plugin_exception(exc): return None if not isinstance(exc, KeyError) else "translated"
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(composition, "COMPOSITION_PACKAGE", "fakeapp.plugins")
    invalidate_caches()
    for name in list(sys.modules):
        if name.startswith("fakeapp"):
            monkeypatch.delitem(sys.modules, name)

    app = object()
    await composition.run_lifecycle_phase("run_plugin_startup", app)
    await composition.run_lifecycle_phase("run_plugin_after_scheduler", app)  # 未实现的阶段：跳过
    assert composition.register_scheduler_jobs("sched") == ("demo_job",)
    composition.install_routes(app)
    assert composition.translate_exception(KeyError("k")) == "translated"
    assert composition.translate_exception(ValueError("v")) is None
    await composition.run_lifecycle_phase("run_plugin_shutdown", app)

    wiring = composition.load_app_wiring()
    assert [c[0] for c in wiring.CALLS] == ["startup", "jobs", "routes", "shutdown"]


def test_broken_composition_package_is_not_mistaken_for_pure_base(tmp_path, monkeypatch) -> None:
    pkg = tmp_path / "brokenapp" / "plugins"
    pkg.mkdir(parents=True)
    (tmp_path / "brokenapp" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "app_wiring.py").write_text("import module_that_does_not_exist_xyz\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(composition, "COMPOSITION_PACKAGE", "brokenapp.plugins")
    invalidate_caches()
    with pytest.raises(ModuleNotFoundError):
        composition.load_app_wiring()  # 父包在 → 故障必须往上抛，不能当成"纯 base"
