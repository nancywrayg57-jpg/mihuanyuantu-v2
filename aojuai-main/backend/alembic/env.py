"""
Alembic Environment Configuration
"""
from logging.config import fileConfig

from alembic.script import ScriptDirectory
from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import settings
from app.core.module_manifest import import_present_model_modules, is_unmanaged_table

# Import all models to ensure they are registered with SQLAlchemy
from app.domain.auth.models import Tenant  # noqa: F401
from app.domain.credits.models import CreditAccount, CreditRule, CreditTransaction  # noqa: F401
from app.domain.invitations.models import InviteCode, InviteRegistration  # noqa: F401
from app.domain.menus.models import Menu  # noqa: F401
from app.domain.notifications.gateway_models import MessageGatewayAccount  # noqa: F401
from app.domain.notifications.models import Notification, UserMessageChannel  # noqa: F401
from app.domain.operation_logs.models import OperationLog  # noqa: F401
from app.domain.organizations.models import Organization  # noqa: F401
from app.domain.roles.models import Role, RoleMenu, RoleTeam  # noqa: F401
from app.domain.teams.models import Team  # noqa: F401
from app.domain.user_groups.models import UserGroup, UserGroupMember  # noqa: F401
from app.domain.users.models import User, UserRole  # noqa: F401
from app.domain.verification.models import VerificationCode  # noqa: F401
from app.infrastructure.database.session import Base

# 可硬卸载的内置能力（assistant / speech / cms）的模型按代码存在与否注册：
# 删掉 app/domain/speech/ 之后，迁移环境也要能起来，否则"不安装就不加载"
# 在迁移这一层就断了。清单见 app/core/module_manifest.py。
REGISTERED_MODULE_MODELS = import_present_model_modules()

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with our settings (sync URL for migrations)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model's MetaData object for 'autogenerate'
target_metadata = Base.metadata

# Alembic env 是迁移边界：这里必须以实际 connection 的方言配置 DDL/render 行为，
# 因而允许直接读取 connection.dialect.name；应用运行时代码一律走 database dialect registry。


def _include_object(object_, name, type_, reflected, compare_to):
    """把不归核心链管的表挡在 autogenerate 之外。

    两类：能力包自管的 cap_*（它们有独立迁移链与独立 version_table），
    以及被硬卸载的内置模块留下的残留表。没有这道过滤，卸载语音之后
    第一次 autogenerate 就会生成 DROP TABLE speech_*——把数据顺手删了。
    """
    if type_ == "table" and is_unmanaged_table(name):
        return False
    return True


def _get_existing_public_table_names(connection) -> set[str]:
    rows = connection.exec_driver_sql(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        """
    ).all()
    return {str(row[0]) for row in rows if row and row[0]}


def _target_metadata_table_names() -> set[str]:
    return {
        table.name
        for table in target_metadata.sorted_tables
        if table.schema in (None, "public")
    }


def _has_full_target_schema(connection) -> bool:
    target_tables = _target_metadata_table_names()
    if not target_tables:
        return False
    existing_tables = _get_existing_public_table_names(connection)
    return target_tables.issubset(existing_tables)


def _ensure_alembic_version_table(connection) -> None:
    """
    Ensure alembic_version.version_num can store long revision IDs.
    """
    if connection.dialect.name != "postgresql":
        return

    connection.exec_driver_sql(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'alembic_version'
          ) THEN
            CREATE TABLE alembic_version (
              version_num VARCHAR(255) NOT NULL PRIMARY KEY
            );
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'alembic_version'
              AND column_name = 'version_num'
              AND data_type = 'character varying'
              AND (character_maximum_length IS NULL OR character_maximum_length < 255)
          ) THEN
            ALTER TABLE alembic_version
              ALTER COLUMN version_num TYPE VARCHAR(255);
          END IF;
        END $$;
        """
    )


def _bootstrap_legacy_schema_alembic_version(connection) -> bool:
    """
    Stamp fully initialized legacy schemas that were created outside Alembic.
    """
    if connection.dialect.name != "postgresql":
        # SQLite 轻量档：新库由 init_db 走 create_all + stamp；information_schema 探测是 PG 专有
        return False
    existing = connection.exec_driver_sql("SELECT version_num FROM alembic_version LIMIT 1").scalar()
    if existing:
        return False

    if not _has_full_target_schema(connection):
        return False

    script = ScriptDirectory.from_config(config)
    heads = tuple(script.get_heads())
    if not heads:
        return False

    inserted = False
    for head in heads:
        connection.exec_driver_sql(
            """
            INSERT INTO alembic_version (version_num)
            VALUES (%(version_num)s)
            ON CONFLICT (version_num) DO NOTHING
            """,
            {"version_num": head},
        )
        inserted = True

    return inserted


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=_include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=str(url or "").startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def _bootstrap_empty_sqlite(connection) -> bool:
    """SQLite 空库：`alembic upgrade head` 与 `init_db()` 同一语义——ORM metadata 建全表后 stamp 到 head。

    核心链里的 PG 专有历史迁移不在 SQLite 上重放；只有"空库"（没有 alembic_version、也没有任何业务表）才走这里，
    已被管理过的 SQLite 库照常按后续双方言迁移升级。返回 True 表示已引导完成，调用方直接结束。
    """
    if connection.dialect.name != "sqlite":
        return False
    from sqlalchemy import inspect as sa_inspect

    insp = sa_inspect(connection)
    if insp.has_table("alembic_version") or [t for t in insp.get_table_names() if not t.startswith("sqlite_")]:
        return False
    import app.domain  # noqa: F401  # 注册全部核心模型
    from app.infrastructure.database.session import Base

    Base.metadata.create_all(bind=connection)
    head = ScriptDirectory.from_config(config).get_current_head()
    connection.exec_driver_sql("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(255) NOT NULL PRIMARY KEY)")
    connection.exec_driver_sql("DELETE FROM alembic_version")
    connection.exec_driver_sql("INSERT INTO alembic_version (version_num) VALUES (?)", (head,))
    print(f"sqlite empty database bootstrapped: create_all + stamp {head}")
    return True


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode with sync engine.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        if _bootstrap_empty_sqlite(connection):
            connection.commit()
            return
        _ensure_alembic_version_table(connection)
        _bootstrap_legacy_schema_alembic_version(connection)
        connection.commit()
        context.configure(
            connection=connection,
            render_as_batch=connection.dialect.name == "sqlite",
            target_metadata=target_metadata,
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
