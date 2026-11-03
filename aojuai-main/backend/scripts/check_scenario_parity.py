#!/usr/bin/env python3
"""三场景终态对账：菜单/权限/授权在三条链路上必须落到同一个终态。

三条链路（`docs/dev/flows/MENUS_PERMS_DUALWRITE.md` 的"三写"）：

1. **fresh**     —— 新库：`alembic upgrade head` + `seed_data`
2. **legacy**    —— 老库：在数据迁移之前的版本上 seed，之后**只** `upgrade head`
3. **bootstrap** —— 新租户：在 fresh 库上走运行时建租户链路

三者的终态必须一致。任何一条掉队，症状都是"某些租户的菜单/按钮/授权莫名其妙少一块"，
而且**只在生产上出现**——因为开发库总是 fresh 的。这类问题这个仓库已经踩过不止一次。

为什么必须真跑数据库：这三条链路的差异全在 SQL 与数据迁移里，纯 mock 测试
（不连库）结构上就看不见。所以它是脚本而不是 pytest 用例。

用法：
    python -m scripts.check_scenario_parity            # 建临时库跑完即销毁
    python -m scripts.check_scenario_parity --keep     # 失败时保留现场
    python -m scripts.check_scenario_parity --modules public_site

前置：本机 PostgreSQL，且当前用户能以超级用户身份执行 psql
（默认 `sudo -u postgres <psql>`，可用 --admin-psql 覆盖）。
临时角色与临时库都由脚本自己创建，不碰任何既有库。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 数据迁移之前的最后一个版本。legacy 场景在这里 seed，然后只 upgrade——
# 数据迁移必须把它补齐到与 fresh 相同的终态。
PRE_RECONCILE_REVISION = "base_20260622_cms_languages"

DEFAULT_ADMIN_PSQL = ("sudo", "-u", "postgres", "/www/server/pgsql/bin/psql")
ROLE_NAME = "aoju_parity_probe"
DB_PREFIX = "aoju_parity_"


# ---------------------------------------------------------------- 管理端操作


def _admin_sql(admin_psql: tuple[str, ...], sql: str) -> str:
    result = subprocess.run(
        [*admin_psql, "-v", "ON_ERROR_STOP=1", "-tAc", sql],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"admin psql failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def provision(admin_psql: tuple[str, ...], databases: list[str], password: str) -> None:
    exists = _admin_sql(admin_psql, f"SELECT 1 FROM pg_roles WHERE rolname = {_quote_literal(ROLE_NAME)}")
    if exists:
        _admin_sql(admin_psql, f"ALTER ROLE {ROLE_NAME} WITH LOGIN PASSWORD {_quote_literal(password)}")
    else:
        _admin_sql(admin_psql, f"CREATE ROLE {ROLE_NAME} LOGIN PASSWORD {_quote_literal(password)}")
    for name in databases:
        _admin_sql(admin_psql, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        _admin_sql(admin_psql, f'CREATE DATABASE "{name}" OWNER {ROLE_NAME}')


def teardown(admin_psql: tuple[str, ...], databases: list[str]) -> None:
    for name in databases:
        try:
            _admin_sql(admin_psql, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        except RuntimeError as exc:  # 清理失败不该盖掉真正的结论
            print(f"warning: cannot drop {name}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------- 子进程阶段


def _configure_settings(database: str, password: str, modules: str) -> None:
    """在**任何**数据库模块被 import 之前改掉连接参数。

    engine 是在 `app.infrastructure.database.session` 导入时建的，所以顺序不能反。
    这也是这三个场景必须各起一个子进程的原因：一个进程里换不掉库。
    """
    from app.core.config import settings

    settings.DB_USER = ROLE_NAME
    settings.DB_PASSWORD = password
    settings.DB_NAME = database
    settings.AOJ_ENABLED_MODULES = modules
    settings.AUTO_INIT_DB = False

    from app.core import feature_switches

    feature_switches.clear_module_install_caches()


def _alembic_upgrade_or_down(target: str, *, downgrade: bool = False) -> None:
    from alembic import command
    from alembic.config import Config

    from app.core.config import settings

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("prepend_sys_path", str(BACKEND_DIR))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)
    (command.downgrade if downgrade else command.upgrade)(config, target)


def _alembic_upgrade(target: str) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("prepend_sys_path", str(BACKEND_DIR))
    from app.core.config import settings

    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)
    command.upgrade(config, target)


async def _snapshot(tenant_code: str | None = None) -> dict:
    """抓一个租户的**用户可见终态**，做成与 id、与租户模型都无关的可比较结构。

    刻意不按 `menus.tenant_id` 取菜单：这个仓库里菜单的归属是矛盾的——
    `MenuService` 把菜单当系统级（读不带租户过滤、写死 tenant_id=1），
    而 `reconcile_menu_declaration` 按租户建行。对账不该押在其中一种解释上。

    真正决定用户看到什么的是 **role_menus**，所以这里从"该租户各角色被授了哪些菜单"
    出发，再顺着 parent 链拼出语义 key。哪种租户模型赢了，这个视角都成立。
    """
    from sqlalchemy import text

    from app.infrastructure.database import get_db_context

    async with get_db_context() as db:
        if tenant_code is None:
            row = await db.execute(
                text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
            )
        else:
            row = await db.execute(
                text("SELECT id FROM tenants WHERE deleted_at IS NULL AND code = :code"),
                {"code": tenant_code},
            )
        tenant_id = row.scalar()
        if tenant_id is None:
            raise RuntimeError(f"no tenant found (code={tenant_code!r})")

        # 全库菜单：key 的计算要顺 parent 链，跨租户也得能解析。
        all_menus = (
            await db.execute(
                text(
                    """
                    SELECT id, tenant_id, parent_id, path, title, perms, menu_type,
                           sort_order, is_visible, is_active, meta
                    FROM menus WHERE deleted_at IS NULL
                    """
                )
            )
        ).mappings().all()
        by_id = {int(item["id"]): item for item in all_menus}

        def key_of(item) -> str:
            parent = by_id.get(int(item["parent_id"])) if item["parent_id"] else None
            parent_key = key_of(parent) if parent is not None else ""
            return f"{parent_key}>{item['menu_type']}:{item['path'] or ''}:{item['perms'] or ''}:{item['title']}"

        grants = (
            await db.execute(
                text(
                    """
                    SELECT r.code AS role_code, rm.menu_id
                    FROM role_menus rm
                    JOIN roles r ON r.id = rm.role_id
                    WHERE r.tenant_id = :tenant_id AND r.deleted_at IS NULL
                    """
                ),
                {"tenant_id": tenant_id},
            )
        ).mappings().all()

        by_role: dict[str, set[str]] = {}
        visible: dict[str, dict] = {}
        for grant in grants:
            menu = by_id.get(int(grant["menu_id"]))
            if menu is None:
                continue
            key = key_of(menu)
            by_role.setdefault(str(grant["role_code"]), set()).add(key)
            visible[key] = {
                "key": key,
                "sortOrder": int(menu["sort_order"]),
                "isVisible": bool(menu["is_visible"]),
                "isActive": bool(menu["is_active"]),
                # meta 里有 tenantSettingsExtension 这类真会改前端行为的开关，
                # 不比对就等于放过一整类漂移。
                "meta": menu["meta"] or {},
            }

        # 只比 code 会放过"角色建出来了但数据权限字段不对"这类漂移——
        # data_range / data_permissions 直接决定这个角色能看到哪些行。
        role_rows = (
            await db.execute(
                text(
                    "SELECT code, name, description, sort_order, data_range, data_permissions,"
                    " is_active, is_system"
                    " FROM roles WHERE tenant_id = :tenant_id AND deleted_at IS NULL"
                ),
                {"tenant_id": tenant_id},
            )
        ).mappings().all()
        roles = {
            str(row["code"]): {
                "name": row["name"],
                "description": row["description"] or "",
                "sortOrder": int(row["sort_order"] or 0),
                "dataRange": int(row["data_range"] or 0),
                "dataPermissions": int(row["data_permissions"] or 0),
                "isActive": bool(row["is_active"]),
                "isSystem": bool(row["is_system"]),
            }
            for row in role_rows
        }

        # **租户内**重复才是问题：同一个租户下同一个语义 key 有两行，说明 seed 或
        # reconciler 建重了，前端会看到两条一模一样的菜单。
        #
        # 跨租户重复是**正常的**——菜单行本来就逐租户一份（reconciler 按 tenant_id
        # 读写）。2026-08-09 之前 `/menus/routes` 的查询不带租户过滤，跨租户副本会
        # 一起冒出来，那时候这里确实该报警；过滤补上之后，跨租户重复不再是缺陷。
        within: dict[tuple[int, str], int] = {}
        for item in all_menus:
            marker = (int(item["tenant_id"]), key_of(item))
            within[marker] = within.get(marker, 0) + 1
        duplicated = sorted(key for (_tenant, key), count in within.items() if count > 1)

        return {
            "roles": roles,
            "menus": sorted(visible.values(), key=lambda item: item["key"]),
            "grants": {role: sorted(keys) for role, keys in sorted(by_role.items())},
            "duplicatedWithinTenant": duplicated,
        }


async def _run_stage(stage: str, database: str, password: str, modules: str) -> dict:
    _configure_settings(database, password, modules)
    from sqlalchemy import text as text_clause  # noqa: F401  (oldtenant 阶段用)

    if stage == "fresh":
        _alembic_upgrade("head")
        from scripts.seed_data import seed_initial_data

        await seed_initial_data()
        return await _snapshot()

    if stage == "legacy":
        # 老库：先停在数据迁移之前 seed，再只 upgrade——数据迁移负责补齐。
        _alembic_upgrade(PRE_RECONCILE_REVISION)
        from scripts.seed_data import seed_initial_data

        await seed_initial_data()
        _alembic_upgrade("head")
        return await _snapshot()

    if stage == "bootstrap":
        # 复用 fresh 库，走运行时建租户链路，再抓**新租户**的终态。
        from app.domain.auth.service import TenantService
        from app.domain.auth.schemas import TenantCreateWithAdmin
        from app.infrastructure.database import get_db_context

        async with get_db_context() as db:
            service = TenantService(db)
            await service.create_tenant_with_admin(
                TenantCreateWithAdmin(name="Parity Probe", code="parity_probe")
            )
            await db.commit()
        return await _snapshot(tenant_code="parity_probe")

    if stage == "oldtenant":
        # 模拟"这条迁移发布之前建出来的租户"：只有 CMS 菜单，没有系统菜单。
        # 然后回退一格再升级，让 backfill 迁移真的跑一次——否则这条迁移
        # 在对账里永远只在"已经是对的"库上空转，等于没验证过。
        from app.domain.auth.schemas import TenantCreateWithAdmin
        from app.domain.auth.service import TenantService
        from app.infrastructure.database import get_db_context

        async with get_db_context() as db:
            service = TenantService(db)
            await service.create_tenant_with_admin(
                TenantCreateWithAdmin(name="Old Tenant", code="old_tenant")
            )
            await db.commit()

        async with get_db_context() as db:
            tenant_id = await db.scalar(
                text_clause("SELECT id FROM tenants WHERE code='old_tenant'")
            )
            # 退回到迁移之前的样子：**只**抹掉系统菜单及其授权，CMS 原样保留
            # （CMS 有自己的数据迁移，不归这条 backfill 管）。
            cms_subtree = (
                "WITH RECURSIVE cms AS ("
                " SELECT id FROM menus WHERE tenant_id=:t AND deleted_at IS NULL"
                "   AND path LIKE '/cms%'"
                " UNION ALL"
                " SELECT m.id FROM menus m JOIN cms ON m.parent_id = cms.id"
                "   WHERE m.tenant_id=:t AND m.deleted_at IS NULL"
                ")"
            )
            await db.execute(
                text_clause(
                    cms_subtree
                    + " DELETE FROM role_menus WHERE tenant_id=:t"
                    " AND menu_id NOT IN (SELECT id FROM cms)"
                ),
                {"t": tenant_id},
            )
            await db.execute(
                text_clause(
                    cms_subtree
                    + " DELETE FROM menus WHERE tenant_id=:t"
                    " AND id NOT IN (SELECT id FROM cms)"
                ),
                {"t": tenant_id},
            )
            await db.commit()

        _alembic_upgrade_or_down("base_20260808_merge_v2_heads", downgrade=True)
        _alembic_upgrade("head")
        return await _snapshot(tenant_code="old_tenant")

    raise SystemExit(f"unknown stage {stage!r}")


# ---------------------------------------------------------------- 编排


def _child(stage: str, database: str, secret_file: Path, modules: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_scenario_parity",
            "--stage",
            stage,
            "--database",
            database,
            "--secret-file",
            str(secret_file),
            "--modules",
            modules,
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if result.returncode != 0:
        raise RuntimeError(f"stage {stage} failed:\n{result.stdout[-4000:]}\n{result.stderr[-4000:]}")
    marker = "@@PARITY@@"
    for line in reversed(result.stdout.splitlines()):
        if line.startswith(marker):
            return json.loads(line[len(marker) :])
    raise RuntimeError(f"stage {stage} produced no snapshot:\n{result.stdout[-4000:]}")


def _diff(label_a: str, snap_a: dict, label_b: str, snap_b: dict) -> list[str]:
    problems: list[str] = []

    roles_a, roles_b = set(snap_a["roles"]), set(snap_b["roles"])
    for missing in sorted(roles_a - roles_b):
        problems.append(f"{label_b} 缺少角色：{missing}")
    for extra in sorted(roles_b - roles_a):
        problems.append(f"{label_b} 多出角色：{extra}")
    for code in sorted(roles_a & roles_b):
        fields_a, fields_b = snap_a["roles"][code], snap_b["roles"][code]
        for field in sorted(set(fields_a) | set(fields_b)):
            if fields_a.get(field) != fields_b.get(field):
                problems.append(
                    f"角色 {code} 的 {field} 不一致：{label_a}={fields_a.get(field)!r} "
                    f"{label_b}={fields_b.get(field)!r}"
                )

    keys_a = {item["key"] for item in snap_a["menus"]}
    keys_b = {item["key"] for item in snap_b["menus"]}
    for missing in sorted(keys_a - keys_b):
        problems.append(f"{label_b} 缺少菜单：{missing}")
    for extra in sorted(keys_b - keys_a):
        problems.append(f"{label_b} 多出菜单：{extra}")

    attrs_a = {item["key"]: item for item in snap_a["menus"]}
    attrs_b = {item["key"]: item for item in snap_b["menus"]}
    for key in sorted(keys_a & keys_b):
        if attrs_a[key] != attrs_b[key]:
            problems.append(f"菜单属性不一致 {key}: {label_a}={attrs_a[key]} {label_b}={attrs_b[key]}")

    for role in sorted(set(snap_a["grants"]) | set(snap_b["grants"])):
        grants_a = set(snap_a["grants"].get(role, []))
        grants_b = set(snap_b["grants"].get(role, []))
        for missing in sorted(grants_a - grants_b):
            problems.append(f"{label_b} 角色 {role} 缺少授权：{missing}")
        for extra in sorted(grants_b - grants_a):
            problems.append(f"{label_b} 角色 {role} 多出授权：{extra}")

    return problems


def _check_ancestor_closure(label: str, snapshot: dict) -> list[str]:
    """授权必须满足祖先闭包：授了子菜单却没授父菜单，前端就渲染不出这条路由。"""
    problems: list[str] = []
    for role, keys in snapshot["grants"].items():
        granted = set(keys)
        for key in sorted(granted):
            parent = key.rsplit(">", 1)[0]
            if parent and parent not in granted:
                problems.append(f"{label} 角色 {role} 授权断层：有 {key} 却没有父级 {parent}")
    return problems


def orchestrate(admin_psql: tuple[str, ...], modules: str, keep: bool) -> int:
    fresh_db = f"{DB_PREFIX}fresh"
    legacy_db = f"{DB_PREFIX}legacy"
    databases = [fresh_db, legacy_db]
    password = secrets.token_urlsafe(24)

    try:
        _admin_sql(admin_psql, "SELECT 1")
    except Exception as exc:  # noqa: BLE001 - 环境不具备时要给出可操作的说明
        print(
            "无法以超级用户执行 psql，跳过对账。\n"
            f"  命令：{' '.join(admin_psql)}\n"
            f"  错误：{exc}\n"
            "  用 --admin-psql 指定可用的管理连接。",
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        secret_file = Path(tmp) / "secret"
        secret_file.write_text(password, encoding="utf-8")
        secret_file.chmod(0o600)

        provision(admin_psql, databases, password)
        try:
            print("[1/4] fresh：upgrade head + seed")
            fresh = _child("fresh", fresh_db, secret_file, modules)
            print("[2/4] legacy：老版本 seed 后只 upgrade")
            legacy = _child("legacy", legacy_db, secret_file, modules)
            print("[3/4] bootstrap：在 fresh 库上建新租户")
            bootstrap = _child("bootstrap", fresh_db, secret_file, modules)
            print("[4/4] oldtenant：模拟旧租户（只有 CMS 菜单），验证 backfill 迁移能补齐")
            oldtenant = _child("oldtenant", legacy_db, secret_file, modules)

            problems = _diff("fresh", fresh, "legacy", legacy)
            problems += _diff("fresh", fresh, "bootstrap", bootstrap)
            problems += _diff("fresh", fresh, "oldtenant", oldtenant)
            for label, snapshot in (
                ("fresh", fresh),
                ("legacy", legacy),
                ("bootstrap", bootstrap),
                ("oldtenant", oldtenant),
            ):
                problems += _check_ancestor_closure(label, snapshot)
                for key in snapshot["duplicatedWithinTenant"]:
                    problems.append(f"{label} 同一租户内菜单重复（seed 或 reconciler 建重了）：{key}")
        finally:
            if not keep:
                teardown(admin_psql, databases)
            else:
                print(f"保留现场：{', '.join(databases)}（角色 {ROLE_NAME}）")

    if problems:
        print(f"\n✗ 四场景终态不一致，共 {len(problems)} 处：", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(
        f"\n✓ 四场景终态一致（菜单 {len(fresh['menus'])} 项，"
        f"角色 {len(fresh['grants'])} 个，模块集 {modules or 'all'}）"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=["fresh", "legacy", "bootstrap", "oldtenant"],
        help="internal: run one stage",
    )
    parser.add_argument("--database")
    parser.add_argument("--secret-file")
    parser.add_argument("--modules", default="public_site", help="AOJ_ENABLED_MODULES for every stage")
    parser.add_argument("--admin-psql", help="superuser psql command, space separated")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway databases on exit")
    options = parser.parse_args()

    if options.stage:
        if not options.database or not options.secret_file:
            raise SystemExit("--stage requires --database and --secret-file")
        password = Path(options.secret_file).read_text(encoding="utf-8")
        snapshot = asyncio.run(_run_stage(options.stage, options.database, password, options.modules))
        print("@@PARITY@@" + json.dumps(snapshot, ensure_ascii=False, sort_keys=True))
        return 0

    admin_psql = tuple(options.admin_psql.split()) if options.admin_psql else DEFAULT_ADMIN_PSQL
    return orchestrate(admin_psql, options.modules, options.keep)


if __name__ == "__main__":
    raise SystemExit(main())
