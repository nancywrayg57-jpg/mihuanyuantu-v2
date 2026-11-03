#!/usr/bin/env python3
"""Generate a self-registering optional capability without editing central files."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent, indent

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = BACKEND_DIR.parent

SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
KEBAB_ROUTE_RE = re.compile(r"^/[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$")
PERMISSION_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SUPPORTED_PERMISSIONS = ("read", "create", "update", "delete")


@dataclass(frozen=True, slots=True)
class ModuleOptions:
    code: str
    layer: str
    route: str
    entity: str
    permissions: tuple[str, ...]

    @property
    def class_name(self) -> str:
        return "".join(part.capitalize() for part in self.entity.split("_"))

    @property
    def code_kebab(self) -> str:
        return self.code.replace("_", "-")

    @property
    def locale_ns(self) -> str:
        """语言包键前缀：camelCase 的模块 code，避免与别的模块撞键。"""
        head, *rest = self.code.split("_")
        return head + "".join(part.capitalize() for part in rest)

    @property
    def entity_plural(self) -> str:
        if self.entity.endswith("y") and not self.entity.endswith(("ay", "ey", "iy", "oy", "uy")):
            return f"{self.entity[:-1]}ies"
        if self.entity.endswith("s"):
            return f"{self.entity}es"
        return f"{self.entity}s"

    @property
    def table_name(self) -> str:
        suffix = f"_{self.entity_plural}"
        return f"cap_{self.code}" if self.code.endswith(suffix) else f"cap_{self.code}{suffix}"

    @property
    def version_table(self) -> str:
        return f"alembic_version_cap_{self.code}"

    @property
    def revision(self) -> str:
        return f"{self.code}_0001"

    @property
    def tenant_index_name(self) -> str:
        return f"ix_{self.table_name}_tenant_id"

    @property
    def unique_index_name(self) -> str:
        return f"uq_{self.table_name}_tenant_code_active"


def parse_permissions(raw: str) -> tuple[str, ...]:
    permissions = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not permissions:
        raise ValueError("at least one permission is required")
    if len(set(permissions)) != len(permissions):
        raise ValueError("permissions must not contain duplicates")
    invalid = [permission for permission in permissions if not PERMISSION_RE.fullmatch(permission)]
    if invalid:
        raise ValueError(f"invalid permission names: {', '.join(invalid)}")
    unsupported = set(permissions) - set(SUPPORTED_PERMISSIONS)
    if unsupported:
        raise ValueError("the CRUD scaffold supports only: " + ", ".join(SUPPORTED_PERMISSIONS))
    if "read" not in permissions:
        raise ValueError("the generated list page requires the read permission")
    return permissions


def validate_options(options: ModuleOptions) -> None:
    if not SNAKE_CASE_RE.fullmatch(options.code):
        raise ValueError("code must be snake_case (lowercase letters, digits, underscores)")
    if not KEBAB_ROUTE_RE.fullmatch(options.route):
        raise ValueError("route must be an absolute kebab-case path such as /order-items")
    if not SNAKE_CASE_RE.fullmatch(options.entity):
        raise ValueError("entity must be snake_case")
    if options.layer not in {"pack", "sample"}:
        raise ValueError("layer must be pack or sample")
    if not options.table_name.startswith(f"cap_{options.code}"):
        raise ValueError("generated table must use the cap_<module-code> prefix")
    postgres_identifiers = (
        options.table_name,
        options.version_table,
        options.tenant_index_name,
        options.unique_index_name,
    )
    if any(len(identifier) > 63 for identifier in postgres_identifiers):
        raise ValueError("a generated PostgreSQL identifier exceeds 63 characters")
    if len(options.revision) > 32:
        raise ValueError("generated Alembic revision exceeds the default 32-character column")
    for permission in options.permissions:
        code = f"{options.code}:{permission}"
        if not re.fullmatch(r"[a-z][a-z0-9_]*:[a-z][a-z0-9_]*", code):
            raise ValueError(f"invalid generated permission code: {code}")


def _header(options: ModuleOptions) -> str:
    production_blocked = options.layer == "sample"
    return dedent(
        f'''\
        """Self-registering {options.code} capability."""

        from app.core.capability_registry import CapabilityDefinition

        CAPABILITY = CapabilityDefinition(
            code="{options.code}",
            label="{options.code}",
            description="Generated {options.layer} capability for {options.entity_plural}",
            layer="{options.layer}",
            version="0.1.0",
            dependencies=("core",),
            default_enabled=False,
            route_prefixes=("{options.route}",),
            api_prefix="{options.route}",
            permission_prefixes=("{options.code}",),
            router_module="app.capabilities.{options.code}.api",
            seed_module="app.capabilities.{options.code}.seed",
            version_table="{options.version_table}",
            production_blocked={production_blocked},
        )
        '''
    )


def _permissions(options: ModuleOptions) -> str:
    lines = [f'{permission.upper()} = "{options.code}:{permission}"' for permission in options.permissions]
    exports = ", ".join(permission.upper() for permission in options.permissions)
    return '"""Public permission constants."""\n\n' + "\n".join(lines) + f"\n\nALL_PERMISSIONS = ({exports},)\n"


def _models(options: ModuleOptions) -> str:
    return dedent(
        f'''\
        from sqlalchemy import Index, String, Text, text
        from sqlalchemy.orm import Mapped, mapped_column

        from app.infrastructure.database.base import TenantBaseModel


        class {options.class_name}(TenantBaseModel):
            __tablename__ = "{options.table_name}"
            __table_args__ = (
                Index(
                    "{options.unique_index_name}",
                    "tenant_id",
                    "code",
                    unique=True,
                    postgresql_where=text("deleted_at IS NULL"),
                    sqlite_where=text("deleted_at IS NULL"),
                ),
            )

            code: Mapped[str] = mapped_column(String(64), nullable=False)
            name: Mapped[str] = mapped_column(String(120), nullable=False)
            description: Mapped[str | None] = mapped_column(Text, nullable=True)
        '''
    )


def _schemas() -> str:
    return dedent(
        """\
        from datetime import datetime

        from pydantic import BaseModel, ConfigDict, Field


        class Create(BaseModel):
            code: str = Field(min_length=1, max_length=64)
            name: str = Field(min_length=1, max_length=120)
            description: str | None = None


        class Update(BaseModel):
            code: str | None = Field(default=None, min_length=1, max_length=64)
            name: str | None = Field(default=None, min_length=1, max_length=120)
            description: str | None = None


        class ListItem(BaseModel):
            model_config = ConfigDict(from_attributes=True, populate_by_name=True)

            id: int
            code: str
            name: str
            description: str | None
            created_at: datetime = Field(serialization_alias="createdAt")
            updated_at: datetime | None = Field(serialization_alias="updatedAt")


        class Detail(ListItem):
            tenant_id: int = Field(serialization_alias="tenantId")
        """
    )


def _service(options: ModuleOptions) -> str:
    return dedent(
        f'''\
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.core.exceptions import NotFoundError
        from app.infrastructure.repository import RepositoryBase

        from .models import {options.class_name}
        from .schemas import Create, Update


        class {options.class_name}Service(RepositoryBase[{options.class_name}]):
            """继承 RepositoryBase 是基座既定约定（软删除过滤、分页、CRUD 都在基类里）。

            租户过滤不交给基类：基类不知道"当前租户是谁"，
            每个方法必须自己把 tenant_id 条件带上，别让越权变成隐式行为。
            """

            def __init__(self, db: AsyncSession):
                super().__init__(db, {options.class_name})

            async def list(self, *, tenant_id: int) -> list[{options.class_name}]:
                rows = await self.get_list(
                    page=1,
                    page_size=100,
                    where=[{options.class_name}.tenant_id == tenant_id],
                    order_by="id",
                    order_desc=True,
                )
                return list(rows)

            async def get(self, *, tenant_id: int, entity_id: int) -> {options.class_name} | None:
                return await self.get_one(
                    where=[
                        {options.class_name}.id == entity_id,
                        {options.class_name}.tenant_id == tenant_id,
                    ]
                )

            async def require(self, *, tenant_id: int, entity_id: int) -> {options.class_name}:
                entity = await self.get(tenant_id=tenant_id, entity_id=entity_id)
                if entity is None:
                    raise NotFoundError(message="{options.class_name} not found")
                return entity

            async def create_entity(self, *, tenant_id: int, data: Create) -> {options.class_name}:
                return await self.create({{"tenant_id": tenant_id, **data.model_dump()}})

            async def update_entity(self, *, tenant_id: int, entity_id: int, data: Update) -> {options.class_name}:
                entity = await self.require(tenant_id=tenant_id, entity_id=entity_id)
                return await self.update(entity, data.model_dump(exclude_unset=True))

            async def delete_entity(self, *, tenant_id: int, entity_id: int) -> None:
                entity = await self.require(tenant_id=tenant_id, entity_id=entity_id)
                await self.delete(entity)
        '''
    )


def _api(options: ModuleOptions) -> str:
    imports = ", ".join(permission.upper() for permission in options.permissions)
    endpoints: list[str] = []
    if "read" in options.permissions:
        endpoints.append(
            dedent(f"""\
            @router.get("", response_model=ResponseBase[list[ListItem]])
            async def list_entities(
                tenant_ctx: TenantCtx,
                db: DBSession,
                _: None = Depends(PermissionChecker([READ])),
            ):
                entities = await {options.class_name}Service(db).list(tenant_id=tenant_ctx.tenant_id)
                return SuccessResponse(data=[ListItem.model_validate(entity) for entity in entities])
            """)
        )
        endpoints.append(
            dedent(f"""\
            @router.get("/{{entity_id}}", response_model=ResponseBase[Detail])
            async def get_entity(
                entity_id: int,
                tenant_ctx: TenantCtx,
                db: DBSession,
                _: None = Depends(PermissionChecker([READ])),
            ):
                entity = await {options.class_name}Service(db).require(tenant_id=tenant_ctx.tenant_id, entity_id=entity_id)
                return SuccessResponse(data=Detail.model_validate(entity))
            """)
        )
    if "create" in options.permissions:
        endpoints.append(
            dedent(f"""\
            @router.post("", response_model=ResponseBase[Detail], status_code=201)
            async def create_entity(
                data: Create,
                tenant_ctx: TenantCtx,
                db: DBSession,
                _: None = Depends(PermissionChecker([CREATE])),
            ):
                entity = await {options.class_name}Service(db).create_entity(tenant_id=tenant_ctx.tenant_id, data=data)
                return SuccessResponse(data=Detail.model_validate(entity))
            """)
        )
    if "update" in options.permissions:
        endpoints.append(
            dedent(f"""\
            @router.patch("/{{entity_id}}", response_model=ResponseBase[Detail])
            async def update_entity(
                entity_id: int,
                data: Update,
                tenant_ctx: TenantCtx,
                db: DBSession,
                _: None = Depends(PermissionChecker([UPDATE])),
            ):
                entity = await {options.class_name}Service(db).update_entity(tenant_id=tenant_ctx.tenant_id, entity_id=entity_id, data=data)
                return SuccessResponse(data=Detail.model_validate(entity))
            """)
        )
    if "delete" in options.permissions:
        endpoints.append(
            dedent(f"""\
            @router.delete("/{{entity_id}}", response_model=ResponseBase[None])
            async def delete_entity(
                entity_id: int,
                tenant_ctx: TenantCtx,
                db: DBSession,
                _: None = Depends(PermissionChecker([DELETE])),
            ):
                await {options.class_name}Service(db).delete_entity(tenant_id=tenant_ctx.tenant_id, entity_id=entity_id)
                return SuccessResponse(data=None)
            """)
        )
    return dedent(
        f"""\
        from fastapi import APIRouter, Depends

        from app.api.deps import DBSession, PermissionChecker, TenantCtx
        from app.core.response import SuccessResponse
        from app.core.schemas import ResponseBase

        from .permissions import {imports}
        from .schemas import Create, Detail, ListItem, Update
        from .service import {options.class_name}Service

        router = APIRouter()


        """
    ) + "\n\n".join(endpoints)


def _access(options: ModuleOptions) -> str:
    read = "READ"
    permission_imports = ", ".join(permission.upper() for permission in options.permissions)
    buttons = "\n".join(
        indent(
            dedent(
                f'''\
            MenuNodeSpec(
                key="{options.code}-{permission}",
                title="{permission.capitalize()} {options.entity}",
                menu_type="2",
                perms={permission.upper()},
                is_visible=False,
            ),'''
            ),
            " " * 16,
        )
        for permission in options.permissions
        if permission != "read"
    )
    rendered = dedent(
        f'''\
        from app.domain.menus.reconciler import MenuDeclaration, MenuNodeSpec, RoleGrantSpec

        from .permissions import {permission_imports}

        ACCESS = MenuDeclaration(
            roots=(
                MenuNodeSpec(
                    key="{options.code}",
                    title="{options.code}",
                    path="{options.route}",
                    component="views/{options.code_kebab}/index",
                    menu_type="1",
                    perms={read},
                    children=(
        __BUTTONS__
                    ),
                ),
            ),
            roles=(
                RoleGrantSpec(code="admin", grant_all=True),
                RoleGrantSpec(code="tenant_admin", grant_all=True),
            ),
        )
        '''
    )
    return rendered.replace("__BUTTONS__", buttons)


def _seed() -> str:
    return dedent(
        """\
        from collections.abc import Mapping

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.domain.menus.reconciler import ReconcileResult, reconcile_menu_declaration

        from .access import ACCESS


        async def reconcile(db: AsyncSession, *, tenant_id: int, role_id_overrides: Mapping[str, int | None] | None = None) -> ReconcileResult:
            return await reconcile_menu_declaration(db, tenant_id=tenant_id, declaration=ACCESS, role_id_overrides=role_id_overrides)


        async def provision(db: AsyncSession, *, tenant_id: int, role_id_overrides: Mapping[str, int | None] | None = None) -> ReconcileResult:
            return await reconcile(db, tenant_id=tenant_id, role_id_overrides=role_id_overrides)


        async def sync(db: AsyncSession) -> list[tuple[int, ReconcileResult]]:
            rows = await db.execute(text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id"))
            return [(int(tenant_id), await reconcile(db, tenant_id=int(tenant_id))) for tenant_id in rows.scalars().all()]
        """
    )


def _migration_env(options: ModuleOptions) -> str:
    return dedent(
        f"""\
        from logging.config import fileConfig

        from sqlalchemy import engine_from_config, pool
        from alembic import context

        from app.capabilities.{options.code} import CAPABILITY
        from app.capabilities.{options.code}.models import {options.class_name}
        from app.core.config import settings

        config = context.config
        config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)
        if config.config_file_name is not None:
            fileConfig(config.config_file_name)
        target_metadata = {options.class_name}.metadata

        # Alembic env 是迁移边界：render_as_batch 必须跟随实际 connection，
        # 因而这里允许直接读取 connection.dialect.name；应用运行时代码不得照搬。


        def include_object(object_, name, type_, reflected, compare_to):
            if type_ == "table":
                return name == {options.class_name}.__tablename__
            table = getattr(object_, "table", None)
            return table is None or table.name == {options.class_name}.__tablename__


        def run_migrations_offline() -> None:
            context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, version_table=CAPABILITY.version_table, include_object=include_object, render_as_batch=str(config.get_main_option("sqlalchemy.url") or "").startswith("sqlite"))
            with context.begin_transaction():
                context.run_migrations()


        def run_migrations_online() -> None:
            connectable = engine_from_config(config.get_section(config.config_ini_section, {{}}), prefix="sqlalchemy.", poolclass=pool.NullPool)
            with connectable.connect() as connection:
                context.configure(connection=connection, target_metadata=target_metadata, version_table=CAPABILITY.version_table, include_object=include_object, render_as_batch=connection.dialect.name == "sqlite")
                with context.begin_transaction():
                    context.run_migrations()


        if context.is_offline_mode():
            run_migrations_offline()
        else:
            run_migrations_online()
        """
    )


def _migration(options: ModuleOptions) -> str:
    return dedent(
        f'''\
        from alembic import op
        import sqlalchemy as sa

        revision = "{options.revision}"
        down_revision = None
        branch_labels = None
        depends_on = None


        def upgrade() -> None:
            op.create_table(
                "{options.table_name}",
                sa.Column("code", sa.String(64), nullable=False),
                sa.Column("name", sa.String(120), nullable=False),
                sa.Column("description", sa.Text(), nullable=True),
                sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("tenant_id", sa.BigInteger(), nullable=False),
                sa.PrimaryKeyConstraint("id"),
            )
            op.create_index("{options.tenant_index_name}", "{options.table_name}", ["tenant_id"])
            op.create_index(
                "{options.unique_index_name}",
                "{options.table_name}",
                ["tenant_id", "code"],
                unique=True,
                postgresql_where=sa.text("deleted_at IS NULL"),
                sqlite_where=sa.text("deleted_at IS NULL"),
            )


        def downgrade() -> None:
            op.drop_index("{options.unique_index_name}", table_name="{options.table_name}")
            op.drop_index("{options.tenant_index_name}", table_name="{options.table_name}")
            op.drop_table("{options.table_name}")
        '''
    )


SCRIPT_TEMPLATE = '''"""${message}"""\nfrom alembic import op\nimport sqlalchemy as sa\n${imports if imports else ""}\nrevision = ${repr(up_revision)}\ndown_revision = ${repr(down_revision)}\nbranch_labels = ${repr(branch_labels)}\ndepends_on = ${repr(depends_on)}\n\ndef upgrade():\n    ${upgrades if upgrades else "pass"}\n\ndef downgrade():\n    ${downgrades if downgrades else "pass"}\n'''


def _frontend_api(options: ModuleOptions) -> str:
    type_name = f"{options.class_name}Record"
    methods = [
        dedent(f"""\
        list(context: Context) {{
          return apiFetch<{type_name}[]>('/api/v1{options.route}', context)
        }},""")
    ]
    if "create" in options.permissions:
        methods.append(
            dedent(f"""\
        create(input: Pick<{type_name}, 'code' | 'name' | 'description'>, context: Context) {{
          return apiFetch<{type_name}>('/api/v1{options.route}', {{ ...context, method: 'POST', body: JSON.stringify(input) }})
        }},""")
        )
    if "update" in options.permissions:
        methods.append(
            dedent(f"""\
        update(id: number, input: Partial<Pick<{type_name}, 'code' | 'name' | 'description'>>, context: Context) {{
          return apiFetch<{type_name}>(`/api/v1{options.route}/${{id}}`, {{ ...context, method: 'PATCH', body: JSON.stringify(input) }})
        }},""")
        )
    if "delete" in options.permissions:
        methods.append(
            dedent(f"""\
        remove(id: number, context: Context) {{
          return apiFetch<null>(`/api/v1{options.route}/${{id}}`, {{ ...context, method: 'DELETE' }})
        }},""")
        )
    return (
        dedent(
            f"""\
        import {{ apiFetch }} from '@/lib/api'
        import type {{ Session }} from '@/lib/auth'

        export type {type_name} = {{ id: number; code: string; name: string; description: string | null }}
        type Context = {{ session: Session; tenantId?: number | null }}

        export const {options.class_name[0].lower() + options.class_name[1:]}Api = {{
        """
        )
        + "\n".join(methods)
        + "\n}\n"
    )


def _frontend_page(options: ModuleOptions) -> str:
    buttons = "\n".join(
        f"{{hasAnyPermission(session, ['{options.code}:{permission}']) ? <Button>{permission.capitalize()}</Button> : null}}"
        for permission in options.permissions
        if permission != "read"
    )
    rendered = dedent(
        f"""\
        'use client'

        import {{ Button }} from '@/components/ui/button'
        import {{ Card, CardContent, CardDescription, CardHeader, CardTitle }} from '@/components/ui/card'
        import {{ useAuth }} from '@/hooks/useAuth'
        import {{ hasAnyPermission }} from '@/lib/auth'
        import {{ useT }} from '@/lib/i18n'

        export default function {options.class_name}Page() {{
          const t = useT()
          const {{ session }} = useAuth()
          if (!session) return null
          // 文案一律走 t()：语言包在 frontend/src/lib/i18n/locales/{options.code_kebab}.ts，
          // 记得在 frontend/src/lib/i18n/index.tsx 里 import 它一次。
          return (
            <Card>
              <CardHeader>
                <CardTitle>{{t('{options.locale_ns}.title')}}</CardTitle>
                <CardDescription>Generated capability page; wire forms to the generated API client.</CardDescription>
              </CardHeader>
              <CardContent className="flex gap-2">
        __BUTTONS__
              </CardContent>
            </Card>
          )
        }}
        """
    )
    return rendered.replace("__BUTTONS__", indent(buttons, " " * 8))


def _test_files(options: ModuleOptions) -> dict[str, str]:
    package = f"app.capabilities.{options.code}"
    expected_permissions = {f"{options.code}:{permission}" for permission in options.permissions}
    return {
        f"test_{options.code}_install_contract.py": dedent(f'''\
            from {package} import CAPABILITY


            def test_installation_defaults_are_closed() -> None:
                assert CAPABILITY.code == "{options.code}"
                assert CAPABILITY.default_enabled is False
                assert CAPABILITY.version_table == "{options.version_table}"
            '''),
        f"test_{options.code}_service_contract.py": dedent(f'''\
            import inspect

            from app.infrastructure.repository import RepositoryBase

            from {package}.service import {options.class_name}Service


            def test_service_follows_base_conventions() -> None:
                """租户过滤在本层、软删除过滤在基类——两者都不能丢。"""
                # 软删除过滤由基类统一处理；不继承就等于自己重写一套，
                # 这正是基座 14 个域里 12 个都继承它的原因。
                assert issubclass({options.class_name}Service, RepositoryBase)

                # 租户过滤必须显式写在每个查询里：基类不知道"当前租户是谁"。
                source = inspect.getsource({options.class_name}Service)
                assert "tenant_id" in source
            '''),
        f"test_{options.code}_permissions_contract.py": dedent(f"""\
            from {package}.permissions import ALL_PERMISSIONS


            def test_permission_codes_use_module_prefix() -> None:
                assert set(ALL_PERMISSIONS) == {expected_permissions!r}
            """),
        f"test_{options.code}_migration_contract.py": dedent(f'''\
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            from {package} import CAPABILITY


            def test_capability_migration_has_one_independent_head() -> None:
                config = Config()
                config.set_main_option("script_location", str(CAPABILITY.migration_path()))
                script = ScriptDirectory.from_config(config)
                assert script.get_bases() == ["{options.revision}"]
                assert script.get_heads() == ["{options.revision}"]
            '''),
    }


def _frontend_locale(options: ModuleOptions) -> str:
    """模块语言包：模块自己维护三份文案并注册，不改核心语言包。

    缺翻译时回退链是 当前语言 → zh-CN → 键本身（见 registry.ts），
    所以先把 zh-CN 写全，en/es 可以逐步补。
    """
    return dedent(
        f"""\
        import {{ registerLocaleMessages }} from '../registry'

        const zhCN: Record<string, string> = {{
          '{options.locale_ns}.title': '{options.class_name}',
          '{options.locale_ns}.column.name': '名称',
          '{options.locale_ns}.column.actions': '操作',
          '{options.locale_ns}.action.refresh': '刷新',
          '{options.locale_ns}.empty': '暂无数据',
          '{options.locale_ns}.loading': '加载中...',
          '{options.locale_ns}.error.load': '加载失败',
        }}

        const enUS: Record<string, string> = {{
          '{options.locale_ns}.title': '{options.class_name}',
          '{options.locale_ns}.column.name': 'Name',
          '{options.locale_ns}.column.actions': 'Actions',
          '{options.locale_ns}.action.refresh': 'Refresh',
          '{options.locale_ns}.empty': 'No data',
          '{options.locale_ns}.loading': 'Loading...',
          '{options.locale_ns}.error.load': 'Failed to load',
        }}

        const esES: Record<string, string> = {{
          '{options.locale_ns}.title': '{options.class_name}',
          '{options.locale_ns}.column.name': 'Nombre',
          '{options.locale_ns}.column.actions': 'Acciones',
          '{options.locale_ns}.action.refresh': 'Actualizar',
          '{options.locale_ns}.empty': 'Sin datos',
          '{options.locale_ns}.loading': 'Cargando...',
          '{options.locale_ns}.error.load': 'Error al cargar',
        }}

        registerLocaleMessages('zh-CN', zhCN)
        registerLocaleMessages('en-US', enUS)
        registerLocaleMessages('es-ES', esES)
        """
    )


def build_files(options: ModuleOptions) -> dict[Path, str]:
    module_dir = BACKEND_DIR / "app" / "capabilities" / options.code
    frontend_page = REPOSITORY_DIR / "frontend" / "src" / "app" / "(app)" / options.route.lstrip("/") / "page.tsx"
    frontend_api = REPOSITORY_DIR / "frontend" / "src" / "lib" / f"{options.code_kebab}-api.ts"
    frontend_locale = (
        REPOSITORY_DIR / "frontend" / "src" / "lib" / "i18n" / "locales" / f"{options.code_kebab}.ts"
    )
    test_dir = BACKEND_DIR / "tests" / "capabilities" / options.code
    files: dict[Path, str] = {
        module_dir / "__init__.py": _header(options),
        module_dir / "models.py": _models(options),
        module_dir / "schemas.py": _schemas(),
        module_dir / "service.py": _service(options),
        module_dir / "permissions.py": _permissions(options),
        module_dir / "api.py": _api(options),
        module_dir / "access.py": _access(options),
        module_dir / "seed.py": _seed(),
        module_dir
        / "README.md": f"# {options.code}\n\nGenerated from the official capability scaffold. Replace fields and tests before shipping.\n",
        module_dir / "migrations" / "env.py": _migration_env(options),
        module_dir / "migrations" / "script.py.mako": SCRIPT_TEMPLATE,
        module_dir / "migrations" / "versions" / f"{options.revision}_initial.py": _migration(options),
        frontend_page: _frontend_page(options),
        frontend_api: _frontend_api(options),
        frontend_locale: _frontend_locale(options),
    }
    if options.layer == "sample":
        files[module_dir / "PRODUCTION_BLOCKED"] = (
            "Generated sample module. Release tooling must reject it from production.\n"
        )
    files.update({test_dir / name: content for name, content in _test_files(options).items()})
    return files


def generate(options: ModuleOptions) -> tuple[Path, ...]:
    validate_options(options)
    files = build_files(options)
    existing = sorted(path for path in files if path.exists())
    if existing:
        rendered = "\n".join(f"  - {path}" for path in existing)
        raise FileExistsError(f"refusing to overwrite existing scaffold files:\n{rendered}")
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return tuple(sorted(files))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("code")
    parser.add_argument("--layer", choices=("pack", "sample"), required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--entity", required=True)
    parser.add_argument("--permissions", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        options = ModuleOptions(
            code=args.code,
            layer=args.layer,
            route=args.route,
            entity=args.entity,
            permissions=parse_permissions(args.permissions),
        )
        created = generate(options)
    except (ValueError, FileExistsError) as exc:
        print(f"new_module error: {exc}", file=sys.stderr)
        return 2

    print(f"created {len(created)} files for capability {options.code}")
    print("next steps:")
    print("  1. Replace the generated entity fields, labels, access grants, and TODO UI.")
    print(f"  2. Install explicitly with AOJ_ENABLED_MODULES={options.code} (merge with existing values).")
    print("  3. Run python -m scripts.capability heads, db upgrade, then sync.")
    print("  4. Run python -m scripts.export_module_catalog 与 python -m scripts.export_locale_index")
    print("     （前端 catalog 与语言包索引都由后端生成；不刷新，漂移守卫会把门禁打红）。")
    print("  5. Run pytest, python scripts/check_governance.py, and frontend pnpm typecheck.")
    if options.layer == "sample":
        print("  6. PRODUCTION_BLOCKED must remain effective; convert to layer=pack only after release review.")
    print("central router/catalog files were not modified; discovery uses CAPABILITY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
